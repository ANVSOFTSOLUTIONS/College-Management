from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse
from pydantic import BaseModel, ValidationError

from app.api.deps import CurrentUser, require_roles
from app.core.errors import AppError
from app.integrations import gateways
from app.modules.audit import service as audit
from app.modules.fees import claims
from app.modules.fees.claims import ClaimIn, ClaimOut
from app.modules.fees.schemas import ReceiptOut
from app.modules.parents import service
from app.modules.parents.service import (
    ChildOverview,
    ChildSummary,
    OnlineOrderOut,
    PaidAllOut,
    ParentLoginOut,
    PaymentSettingsIn,
    PaymentSettingsOut,
)
from app.modules.students import accounts
from app.modules.students.router import _private_file as private_file
from app.modules.students.router import photo_response
from app.modules.students.schemas import StudentDocumentOut

staff_router = APIRouter(prefix="/students", tags=["parent logins"])
portal_router = APIRouter(prefix="/me/parent", tags=["parent portal"])
settings_router = APIRouter(prefix="/fees/payment-settings", tags=["fees"])
webhook_router = APIRouter(prefix="/public/payments", tags=["payments"])

_staff = require_roles("admin", "teacher")
_admin_only = require_roles("admin")
_parent_only = require_roles("parent", "student")


class ParentLoginRequest(BaseModel):
    reset_password: bool = False


class BulkParentLoginsRequest(BaseModel):
    class_id: str


class BulkParentLoginsOut(BaseModel):
    logins: list[ParentLoginOut]
    skipped_without_mobile: list[str]


# --- Staff: parent logins --------------------------------------------------------


@staff_router.post("/bulk-parent-logins", response_model=BulkParentLoginsOut)
async def enable_class_parent_logins(
    payload: BulkParentLoginsRequest, current_user: CurrentUser = Depends(_staff)
) -> BulkParentLoginsOut:
    logins, skipped = await service.enable_class_parent_logins(current_user, payload.class_id)
    return BulkParentLoginsOut(logins=logins, skipped_without_mobile=skipped)


@staff_router.post("/{student_id}/parent-login", response_model=ParentLoginOut)
async def enable_parent_login(
    student_id: str, payload: ParentLoginRequest, current_user: CurrentUser = Depends(_staff)
) -> ParentLoginOut:
    """Gives the primary contact a login (or links their existing one). A new password is shown only here."""
    return await service.enable_parent_login(current_user, student_id, payload.reset_password)


# --- Admin: online payment settings ----------------------------------------------


@settings_router.get("", response_model=PaymentSettingsOut)
async def get_payment_settings(current_user: CurrentUser = Depends(_admin_only)) -> PaymentSettingsOut:
    return await service.get_payment_settings(current_user.school_id)


@settings_router.put("", response_model=PaymentSettingsOut)
async def save_payment_settings(
    payload: PaymentSettingsIn, current_user: CurrentUser = Depends(_admin_only)
) -> PaymentSettingsOut:
    saved = await service.save_payment_settings(current_user.school_id, payload)
    await audit.record(
        current_user, "settings.online_payments",
        f"Online payments {'on' if saved.enabled else 'off'} ({gateways.label(saved.provider)}, {saved.environment}, ID {saved.key_id or '—'})"
        + (", secret key changed" if payload.key_secret is not None else ""),
    )
    return saved


# --- Parent portal ---------------------------------------------------------------


@portal_router.get("/children", response_model=list[ChildSummary])
async def my_children(current_user: CurrentUser = Depends(_parent_only)) -> list[ChildSummary]:
    return await service.list_children(current_user)


@portal_router.get("/children/{student_id}", response_model=ChildOverview)
async def child_overview(student_id: str, current_user: CurrentUser = Depends(_parent_only)) -> ChildOverview:
    return await service.child_overview(current_user, student_id)


@portal_router.get("/children/{student_id}/photo", response_class=FileResponse)
async def child_photo(student_id: str, current_user: CurrentUser = Depends(_parent_only)) -> FileResponse:
    return photo_response(await service.child_photo_row(current_user, student_id))


@portal_router.put("/children/{student_id}/photo", status_code=204)
async def upload_child_photo(student_id: str, file: UploadFile = File(...), current_user: CurrentUser = Depends(_parent_only)) -> Response:
    await accounts.set_photo(await service.child_row(current_user, student_id), file)
    return Response(status_code=204)


@portal_router.get("/children/{student_id}/documents", response_model=list[StudentDocumentOut])
async def child_documents(student_id: str, current_user: CurrentUser = Depends(_parent_only)) -> list[StudentDocumentOut]:
    return await accounts.list_documents(await service.child_row(current_user, student_id))


@portal_router.post("/children/{student_id}/documents", response_model=StudentDocumentOut, status_code=201)
async def upload_child_document(
    student_id: str, doc_type: str = Form(...), title: str = Form(""), file: UploadFile = File(...),
    current_user: CurrentUser = Depends(_parent_only),
) -> StudentDocumentOut:
    """A parent's upload waits for the school to review it, like a student's."""
    return await accounts.add_document(await service.child_row(current_user, student_id), current_user, doc_type, title, file)


@portal_router.delete("/children/{student_id}/documents/{document_id}", status_code=204)
async def delete_child_document(student_id: str, document_id: str, current_user: CurrentUser = Depends(_parent_only)) -> Response:
    await accounts.delete_document(await service.child_row(current_user, student_id), current_user, document_id)
    return Response(status_code=204)


@portal_router.get("/children/{student_id}/documents/{document_id}/file", response_class=FileResponse)
async def child_document_file(student_id: str, document_id: str, current_user: CurrentUser = Depends(_parent_only)) -> FileResponse:
    return private_file(*await accounts.document_file(await service.child_row(current_user, student_id), document_id))


@portal_router.post("/children/{student_id}/fees/{student_fee_id}/offline", response_model=ClaimOut, status_code=201)
async def report_offline_payment(
    student_id: str,
    student_fee_id: str,
    amount: Decimal = Form(...),
    method: str = Form(...),
    paid_on: date = Form(...),
    reference: str = Form(""),
    note: str = Form(""),
    proof: UploadFile | None = File(None),
    current_user: CurrentUser = Depends(_parent_only),
) -> ClaimOut:
    """The parent paid the school directly (UPI, bank, cash, cheque); the office checks and confirms it."""
    try:
        payload = ClaimIn(amount=amount, method=method, paid_on=paid_on, reference=reference, note=note)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc
    child = await service.child_row(current_user, student_id)
    return await claims.submit(current_user, child, student_fee_id, payload, proof if proof and proof.filename else None)


@portal_router.get("/children/{student_id}/receipts/{payment_id}", response_model=ReceiptOut)
async def child_receipt(student_id: str, payment_id: str, current_user: CurrentUser = Depends(_parent_only)) -> ReceiptOut:
    return await service.child_receipt(current_user, student_id, payment_id)


@portal_router.post("/children/{student_id}/fees/{student_fee_id}/pay", response_model=OnlineOrderOut)
async def start_online_payment(
    student_id: str, student_fee_id: str, current_user: CurrentUser = Depends(_parent_only)
) -> OnlineOrderOut:
    return await service.start_online_payment(current_user, student_id, student_fee_id)


@portal_router.post("/children/{student_id}/fees/pay-all", response_model=OnlineOrderOut)
async def start_pay_all(student_id: str, current_user: CurrentUser = Depends(_parent_only)) -> OnlineOrderOut:
    """One Cashfree payment for every fee with a balance; each fee gets its own receipt."""
    return await service.start_pay_all(current_user, student_id)


@portal_router.post("/children/{student_id}/pay-all/{batch_id}/confirm", response_model=PaidAllOut)
async def confirm_pay_all(student_id: str, batch_id: str, current_user: CurrentUser = Depends(_parent_only)) -> PaidAllOut:
    return await service.confirm_pay_all(current_user, student_id, batch_id)


@portal_router.post("/children/{student_id}/payments/{payment_id}/confirm", response_model=ReceiptOut)
async def confirm_online_payment(student_id: str, payment_id: str, current_user: CurrentUser = Depends(_parent_only)) -> ReceiptOut:
    """After Cashfree Checkout closes: asks Cashfree whether the order is paid and, if so, returns the receipt."""
    return await service.confirm_online_payment(current_user, student_id, payment_id)


@webhook_router.post("/cashfree/webhook", status_code=204)
async def cashfree_webhook(request: Request) -> Response:
    """Set this URL as the payment webhook in each school's Cashfree dashboard."""
    await service.handle_webhook(
        await request.body(), request.headers.get("x-webhook-timestamp", ""), request.headers.get("x-webhook-signature", "")
    )
    return Response(status_code=204)


@webhook_router.post("/razorpay/webhook", status_code=204)
async def razorpay_webhook(request: Request) -> Response:
    """Set this URL as a webhook (order.paid, payment.captured) in each school's Razorpay dashboard."""
    await service.handle_webhook(await request.body(), "", "", provider="razorpay")
    return Response(status_code=204)


@webhook_router.post("/demo/{ref}/{outcome}", status_code=204)
async def finish_demo_payment(ref: str, outcome: Literal["pay", "fail"]) -> Response:
    """The demo gateway's payment page (no money moves; only schools the super admin gave it to use it)."""
    if not await gateways.finish_demo_order(ref, outcome == "pay"):
        raise AppError(404, "payment_not_found", "This demo payment is already finished or doesn't exist.")
    return Response(status_code=204)


@webhook_router.post("/phonepe/webhook", status_code=204)
async def phonepe_webhook(request: Request) -> Response:
    """Set this URL as the webhook in each school's PhonePe dashboard."""
    await service.handle_webhook(await request.body(), "", "", provider="phonepe")
    return Response(status_code=204)
