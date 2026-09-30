from dataclasses import dataclass

from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError

from app.core.errors import AppError
from app.core.security import decode_access_token
from app.db.helpers import fetch_one

_bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    id: str
    school_id: str | None
    role: str
    email: str | None
    full_name: str


def _unauthorized(message: str = "Invalid or expired credentials.") -> AppError:
    return AppError(status.HTTP_401_UNAUTHORIZED, "unauthorized", message)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> CurrentUser:
    if credentials is None:
        raise _unauthorized("Authentication credentials were not provided.")

    try:
        payload = decode_access_token(credentials.credentials)
    except InvalidTokenError as exc:
        raise _unauthorized() from exc

    user_id = payload.get("sub")
    if not user_id:
        raise _unauthorized()

    user = await fetch_one("SELECT * FROM users WHERE id = %s", (user_id,))
    if user is None or user["status"] != "active":
        raise _unauthorized("This account is no longer active.")

    return CurrentUser(
        id=user["id"],
        school_id=user["school_id"],
        role=user["role"],
        email=user["email"],
        full_name=user["full_name"],
    )


def require_roles(*allowed_roles: str):
    async def _check(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current_user.role not in allowed_roles:
            raise AppError(
                status.HTTP_403_FORBIDDEN,
                "forbidden",
                "You do not have permission to perform this action.",
            )
        return current_user

    return _check
