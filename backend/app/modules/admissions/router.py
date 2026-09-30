from typing import Literal

from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile, status
from fastapi.responses import FileResponse

from app.api.deps import CurrentUser, require_roles
from app.core.errors import AppError
from app.core.rate_limit import is_rate_limited, record_attempt
from app.modules.admissions import service
from app.modules.admissions.service import (
    AdmissionSettings,
    ApplicationIn,
    ApplicationOut,
    ApproveIn,
    DocType,
    FeeDecisionIn,
    FeeOrderOut,
    FeeStatusOut,
    FeeTokenIn,
    PublicForm,
    RejectIn,
    Submitted,
)

public_router = APIRouter(prefix="/public/schools/{code}/admissions", tags=["admissions (public)"])
router = APIRouter(prefix="/admissions", tags=["admissions"])

_admin = require_roles("admin")
APPLICATIONS_PER_HOUR = 5
UPLOADS_PER_HOUR = 30
PAYMENTS_PER_HOUR = 30


def _limit(request: Request, kind: str, max_attempts: int) -> None:
    key = f"admissions:{kind}:{request.client.host if request.client else 'unknown'}"
    if is_rate_limited(key, max_attempts=max_attempts, window_seconds=3600):
        raise AppError(status.HTTP_429_TOO_MANY_REQUESTS, "too_many_attempts", "Too many attempts from this device. Try again later.")
    record_attempt(key)


# --- Public (no login) ---------------------------------------------------------------------


@public_router.get("", response_model=PublicForm)
async def public_form(code: str) -> PublicForm:
    """What the apply page needs: the school, whether admissions are open, and its classes."""
    return await service.public_form(code)


@public_router.post("", response_model=Submitted, status_code=status.HTTP_201_CREATED)
async def apply(code: str, payload: ApplicationIn, request: Request) -> Submitted:
    """A parent's application. The response's upload_token allows adding documents for two hours."""
    _limit(request, "apply", APPLICATIONS_PER_HOUR)
    return await service.submit_online(code, payload)


@public_router.post("/{application_id}/documents", status_code=status.HTTP_204_NO_CONTENT)
async def upload_document(
    code: str,
    application_id: str,
    request: Request,
    token: str = Form(...),
    doc_type: DocType = Form(...),
    file: UploadFile = File(...),
) -> Response:
    _limit(request, "upload", UPLOADS_PER_HOUR)
    await service.upload_with_token(application_id, token, doc_type, file)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@public_router.post("/{application_id}/fee/pay", response_model=FeeOrderOut)
async def start_fee_payment(code: str, application_id: str, payload: FeeTokenIn, request: Request) -> FeeOrderOut:
    """Starts a Cashfree order for the application fee (the token from applying proves it's the applicant)."""
    _limit(request, "pay", PAYMENTS_PER_HOUR)
    return await service.start_fee_payment(code, application_id, payload.token)


@public_router.post("/{application_id}/fee/confirm", response_model=FeeStatusOut)
async def confirm_fee_payment(code: str, application_id: str, payload: FeeTokenIn, request: Request) -> FeeStatusOut:
    """After Cashfree Checkout closes: asks Cashfree whether the fee is paid."""
    _limit(request, "pay", PAYMENTS_PER_HOUR)
    return await service.confirm_fee_payment(code, application_id, payload.token)


# --- Admin ---------------------------------------------------------------------------------------


@router.get("", response_model=list[ApplicationOut])
async def list_applications(
    status_filter: Literal["new", "approved", "rejected"] | None = None, current_user: CurrentUser = Depends(_admin)
) -> list[ApplicationOut]:
    return await service.list_applications(current_user, status_filter=status_filter)


@router.post("", response_model=ApplicationOut, status_code=status.HTTP_201_CREATED)
async def create_walk_in(payload: ApplicationIn, current_user: CurrentUser = Depends(_admin)) -> ApplicationOut:
    """An enquiry taken at the school office."""
    return await service.create_walk_in(current_user, payload)


@router.get("/settings", response_model=AdmissionSettings)
async def get_settings(current_user: CurrentUser = Depends(_admin)) -> AdmissionSettings:
    return await service.get_settings(current_user.school_id)


@router.put("/settings", response_model=AdmissionSettings)
async def save_settings(payload: AdmissionSettings, current_user: CurrentUser = Depends(_admin)) -> AdmissionSettings:
    """Opens or closes the public apply page, and sets the application fee (0 = none)."""
    return await service.save_settings(current_user, payload)


@router.get("/next-admission-number")
async def next_admission_number(current_user: CurrentUser = Depends(_admin)) -> dict:
    return {"admission_number": await service.suggest_admission_number(current_user)}


@router.get("/{application_id}", response_model=ApplicationOut)
async def get_application(application_id: str, current_user: CurrentUser = Depends(_admin)) -> ApplicationOut:
    return await service.get_application(current_user, application_id)


@router.post("/{application_id}/documents", response_model=ApplicationOut)
async def add_document(
    application_id: str, doc_type: DocType = Form(...), file: UploadFile = File(...), current_user: CurrentUser = Depends(_admin)
) -> ApplicationOut:
    return await service.add_document(current_user, application_id, doc_type, file)


@router.get("/{application_id}/documents/{document_id}", response_class=FileResponse)
async def document_file(application_id: str, document_id: str, current_user: CurrentUser = Depends(_admin)) -> FileResponse:
    path, content_type, name = await service.document_file(current_user, application_id, document_id)
    return FileResponse(
        path, media_type=content_type, filename=name or None, content_disposition_type="inline",
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.post("/{application_id}/approve", response_model=ApplicationOut)
async def approve(application_id: str, payload: ApproveIn, current_user: CurrentUser = Depends(_admin)) -> ApplicationOut:
    """Creates the student (with parents and documents) in the chosen class, and a parent login."""
    return await service.approve(current_user, application_id, payload)


@router.post("/{application_id}/fee", response_model=ApplicationOut)
async def record_fee(application_id: str, payload: FeeDecisionIn, current_user: CurrentUser = Depends(_admin)) -> ApplicationOut:
    """The application fee was paid at the office, or is waived."""
    return await service.record_fee(current_user, application_id, payload)


@router.post("/{application_id}/reject", response_model=ApplicationOut)
async def reject(application_id: str, payload: RejectIn, current_user: CurrentUser = Depends(_admin)) -> ApplicationOut:
    return await service.reject(current_user, application_id, payload)
