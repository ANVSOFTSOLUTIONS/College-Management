from typing import Literal

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, EmailStr, Field, model_validator

from app.core.config import get_settings
from app.core.modules import school_modules
from app.core.errors import AppError
from app.core.rate_limit import is_rate_limited, record_attempt
from app.api.deps import CurrentUser, get_current_user
from app.core.phone import normalize_indian_mobile
from app.core.security import create_access_token, hash_password, parent_login_id, student_login_id, verify_password
from app.db.helpers import execute, fetch_one

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    """Staff sign in with email; parents with their mobile; students with college code and roll number."""

    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=20)
    college_code: str | None = Field(default=None, max_length=30)
    roll_number: str | None = Field(default=None, max_length=50)
    password: str = Field(min_length=1, max_length=72)
    # Which sign-in page: "school" (colleges' staff, students, parents) refuses the super admin,
    # "platform" accepts only the super admin. Omitted: either (older clients).
    portal: Literal["school", "platform"] | None = None

    @model_validator(mode="after")
    def _one_identity(self):
        student = bool(self.college_code and self.college_code.strip()) and bool(self.roll_number and self.roll_number.strip())
        if self.email is None and not self.phone and not student:
            raise ValueError("Give an email, a mobile number, or a college code and roll number.")
        return self

    @property
    def identity(self) -> str:
        if self.email:
            return self.email.lower()
        if self.phone:
            return parent_login_id(normalize_indian_mobile(self.phone) or self.phone.strip())
        return student_login_id(self.college_code, self.roll_number)


class UserSummary(BaseModel):
    id: str
    email: str | None
    full_name: str
    role: str
    school_id: str | None
    must_change_password: bool = False
    enabled_modules: list[str] | None = None  # the school's optional modules; None for parents and the super admin
    is_hod: bool = False  # faculty who head a department (the app shows them the department view)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserSummary


async def _is_hod(user_id: str, role: str) -> bool:
    if role != "teacher":
        return False
    return await fetch_one(
        "SELECT d.id FROM departments d JOIN teachers t ON t.id = d.hod_teacher_id WHERE t.user_id = %s LIMIT 1", (user_id,)
    ) is not None


def _invalid_credentials() -> AppError:
    return AppError(status.HTTP_401_UNAUTHORIZED, "invalid_credentials", "Incorrect email or password.")


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, request: Request) -> LoginResponse:
    settings = get_settings()
    client_host = request.client.host if request.client else "unknown"
    rate_limit_key = f"{client_host}:{payload.identity}"

    if is_rate_limited(
        rate_limit_key,
        max_attempts=settings.login_rate_limit_attempts,
        window_seconds=settings.login_rate_limit_window_seconds,
    ):
        raise AppError(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "too_many_attempts",
            "Too many login attempts. Try again shortly.",
        )

    record_attempt(rate_limit_key)

    column = "email" if payload.email else "login_id"
    user = await fetch_one(f"SELECT * FROM users WHERE {column} = %s", (payload.identity,))
    if user is None or user["status"] != "active":
        raise _invalid_credentials()

    if not verify_password(payload.password, user["password_hash"]):
        raise _invalid_credentials()
    # The wrong page answers like a wrong password, so the school page doesn't reveal the platform account.
    if payload.portal and (user["role"] == "super_admin") != (payload.portal == "platform"):
        raise _invalid_credentials()

    school_id = user["school_id"]

    if school_id is not None:
        school = await fetch_one("SELECT * FROM schools WHERE id = %s", (school_id,))
        if school is None or school["status"] != "active":
            raise AppError(status.HTTP_403_FORBIDDEN, "school_inactive", "This school's account is not active.")
        if school["billing_status"] == "suspended":
            raise AppError(
                status.HTTP_403_FORBIDDEN,
                "school_suspended",
                "This school's access has been suspended. Contact the platform administrator.",
            )

    access_token = create_access_token(user_id=user["id"], school_id=school_id, role=user["role"])

    return LoginResponse(
        access_token=access_token,
        user=UserSummary(
            id=user["id"],
            email=user["email"],
            full_name=user["full_name"],
            role=user["role"],
            school_id=school_id,
            must_change_password=bool(user["must_change_password"]),
            enabled_modules=sorted(await school_modules(school_id)) if school_id else None,
            is_hod=await _is_hod(user["id"], user["role"]),
        ),
    )


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=72)
    new_password: str = Field(min_length=8, max_length=72)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(payload: ChangePasswordRequest, current_user: CurrentUser = Depends(get_current_user)) -> Response:
    user = await fetch_one("SELECT password_hash FROM users WHERE id = %s", (current_user.id,))
    if not verify_password(payload.current_password, user["password_hash"]):
        raise AppError(status.HTTP_400_BAD_REQUEST, "wrong_password", "Your current password is incorrect.")
    if payload.new_password == payload.current_password:
        raise AppError(status.HTTP_400_BAD_REQUEST, "same_password", "Choose a password different from the current one.")
    await execute(
        "UPDATE users SET password_hash = %s, must_change_password = 0 WHERE id = %s",
        (hash_password(payload.new_password), current_user.id),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


class SchoolSummary(BaseModel):
    name: str
    code: str


class MeResponse(BaseModel):
    user: UserSummary
    school: SchoolSummary | None


@router.get("/me", response_model=MeResponse)
async def me(current_user: CurrentUser = Depends(get_current_user)) -> MeResponse:
    """The signed-in user and their school (name and code, e.g. for install links)."""
    user = await fetch_one("SELECT must_change_password FROM users WHERE id = %s", (current_user.id,))
    school = None
    if current_user.school_id:
        row = await fetch_one("SELECT name, code FROM schools WHERE id = %s", (current_user.school_id,))
        school = SchoolSummary(name=row["name"], code=row["code"]) if row else None
    return MeResponse(
        user=UserSummary(
            id=current_user.id,
            email=current_user.email,
            full_name=current_user.full_name,
            role=current_user.role,
            school_id=current_user.school_id,
            must_change_password=bool(user["must_change_password"]),
            enabled_modules=sorted(await school_modules(current_user.school_id)) if current_user.school_id else None,
            is_hod=await _is_hod(current_user.id, current_user.role),
        ),
        school=school,
    )
