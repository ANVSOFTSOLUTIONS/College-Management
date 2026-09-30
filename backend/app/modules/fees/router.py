from typing import Literal

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, require_roles
from app.db.helpers import fetch_one
from app.modules.audit import service as audit
from app.modules.fees import claims, service
from app.modules.fees.claims import ClaimOut, RejectClaimIn
from app.modules.fees.schemas import (
    AddStudentsRequest,
    CancelPaymentRequest,
    CreateFeeItemRequest,
    DiscountRequest,
    FeeItemOut,
    FeeReport,
    PaymentOut,
    ReceiptOut,
    RecordPaymentRequest,
    ReminderRequest,
    ReminderResult,
    StudentFeeAccount,
    UpdateFeeItemRequest,
)

router = APIRouter(prefix="/fees", tags=["fees"])

# Fees are handled by the school office (admins) only.
_admin_only = require_roles("admin")


@router.get("/items", response_model=list[FeeItemOut])
async def list_fee_items(class_id: str | None = None, current_user: CurrentUser = Depends(_admin_only)) -> list[FeeItemOut]:
    return await service.list_fee_items(current_user, class_id=class_id)


@router.post("/items", response_model=list[FeeItemOut], status_code=status.HTTP_201_CREATED)
async def create_fee_items(payload: CreateFeeItemRequest, current_user: CurrentUser = Depends(_admin_only)) -> list[FeeItemOut]:
    """Creates the fee for each chosen class and bills every active student in them."""
    return await service.create_fee_items(current_user, payload)


@router.patch("/items/{item_id}", response_model=FeeItemOut)
async def update_fee_item(
    item_id: str, payload: UpdateFeeItemRequest, current_user: CurrentUser = Depends(_admin_only)
) -> FeeItemOut:
    item = await service.update_fee_item(current_user, item_id, payload)
    changes = payload.model_dump(exclude_unset=True)
    await audit.record(
        current_user, "fees.item_changed", f"Changed fee {item.name} ({item.class_name} - {item.section}): "
        + ", ".join(f"{k.replace('_', ' ')} → {v}" for k, v in changes.items()),
        entity_type="fee_item", entity_id=item_id, details=changes,
    )
    return item


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_fee_item(item_id: str, current_user: CurrentUser = Depends(_admin_only)) -> Response:
    item = await fetch_one(
        "SELECT f.name, f.amount, c.name AS class_name, c.section FROM fee_items f JOIN classes c ON c.id = f.class_id WHERE f.id = %s AND f.school_id = %s",
        (item_id, current_user.school_id),
    )
    await service.delete_fee_item(current_user, item_id)
    if item:
        await audit.record(
            current_user, "fees.item_deleted", f"Deleted fee {item['name']} (₹{item['amount']}, {item['class_name']} - {item['section']})",
            entity_type="fee_item", entity_id=item_id,
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/items/{item_id}/sync", response_model=FeeItemOut)
async def sync_fee_item(item_id: str, current_user: CurrentUser = Depends(_admin_only)) -> FeeItemOut:
    """Bills students who joined the class after the fee was created."""
    return await service.sync_fee_item(current_user, item_id)


@router.post("/items/{item_id}/students", response_model=FeeItemOut)
async def add_students(item_id: str, payload: AddStudentsRequest, current_user: CurrentUser = Depends(_admin_only)) -> FeeItemOut:
    """Bills more chosen students for a fee that is only for chosen students (e.g. a new bus user)."""
    item = await service.add_students(current_user, item_id, payload.student_ids)
    await audit.record(
        current_user, "fees.students_added", f"Added {len(payload.student_ids)} student(s) to fee {item.name} ({item.class_name} - {item.section})",
        entity_type="fee_item", entity_id=item_id, details={"student_ids": payload.student_ids},
    )
    return item


@router.delete("/student-fees/{student_fee_id}", response_model=StudentFeeAccount)
async def remove_student_fee(student_fee_id: str, current_user: CurrentUser = Depends(_admin_only)) -> StudentFeeAccount:
    """Takes a fee off one student; only while nothing was paid on it."""
    row = await fetch_one(
        "SELECT fi.name FROM student_fees sf JOIN fee_items fi ON fi.id = sf.fee_item_id WHERE sf.id = %s AND sf.school_id = %s",
        (student_fee_id, current_user.school_id),
    )
    account = await service.remove_student_fee(current_user, student_fee_id)
    await audit.record(
        current_user, "fees.student_fee_removed", f"Removed fee {row['name'] if row else ''} from {account.full_name} ({account.admission_number})",
        entity_type="student", entity_id=account.student_id,
    )
    return account


@router.get("/claims", response_model=list[ClaimOut])
async def list_claims(
    status_filter: Literal["submitted", "approved", "rejected"] | None = None, current_user: CurrentUser = Depends(_admin_only)
) -> list[ClaimOut]:
    """Offline payments reported by parents, waiting ones first."""
    return await claims.list_claims(current_user, status_filter=status_filter)


@router.get("/claims/{claim_id}/proof", response_class=FileResponse)
async def claim_proof(claim_id: str, current_user: CurrentUser = Depends(_admin_only)) -> FileResponse:
    path, content_type = await claims.proof_file(current_user, claim_id)
    return FileResponse(path, media_type=content_type, content_disposition_type="inline", headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@router.post("/claims/{claim_id}/approve", response_model=ClaimOut)
async def approve_claim(claim_id: str, current_user: CurrentUser = Depends(_admin_only)) -> ClaimOut:
    """The money is in the school's account: records the payment and issues a receipt."""
    claim = await claims.approve(current_user, claim_id)
    await audit.record(
        current_user, "fees.claim_approved",
        f"Confirmed ₹{claim.amount:g} paid by {claim.method_label} for {claim.student_name} ({claim.admission_number}), receipt {claim.receipt_number}",
        entity_type="fee_claim", entity_id=claim_id,
    )
    return claim


@router.post("/claims/{claim_id}/reject", response_model=ClaimOut)
async def reject_claim(claim_id: str, payload: RejectClaimIn, current_user: CurrentUser = Depends(_admin_only)) -> ClaimOut:
    claim = await claims.reject(current_user, claim_id, payload.note)
    await audit.record(
        current_user, "fees.claim_rejected",
        f"Did not confirm ₹{claim.amount:g} reported for {claim.student_name} ({claim.admission_number}): {payload.note.strip()}",
        entity_type="fee_claim", entity_id=claim_id,
    )
    return claim


class OfflineInstructions(BaseModel):
    text: str = Field(default="", max_length=500)


@router.get("/offline-instructions", response_model=OfflineInstructions)
async def get_offline_instructions(current_user: CurrentUser = Depends(_admin_only)) -> OfflineInstructions:
    return OfflineInstructions(text=await claims.instructions(current_user.school_id))


@router.put("/offline-instructions", response_model=OfflineInstructions)
async def save_offline_instructions(payload: OfflineInstructions, current_user: CurrentUser = Depends(_admin_only)) -> OfflineInstructions:
    """What parents see for paying offline: the school's UPI ID, bank account, office hours."""
    saved = await claims.save_instructions(current_user, payload.text)
    await audit.record(current_user, "settings.offline_payments", "Changed the offline payment details shown to parents")
    return OfflineInstructions(text=saved)


@router.get("/students/{student_id}", response_model=StudentFeeAccount)
async def student_account(student_id: str, current_user: CurrentUser = Depends(_admin_only)) -> StudentFeeAccount:
    return await service.student_account(current_user.school_id, student_id)


@router.put("/student-fees/{student_fee_id}/discount", response_model=StudentFeeAccount)
async def set_discount(
    student_fee_id: str, payload: DiscountRequest, current_user: CurrentUser = Depends(_admin_only)
) -> StudentFeeAccount:
    account = await service.set_discount(current_user, student_fee_id, payload.discount, payload.note)
    await audit.record(
        current_user, "fees.concession", f"Set a concession of ₹{payload.discount} for {account.full_name} ({account.admission_number})"
        + (f": {payload.note}" if payload.note else ""),
        entity_type="student", entity_id=account.student_id, details={"student_fee_id": student_fee_id, "discount": str(payload.discount)},
    )
    return account


@router.post("/payments", response_model=PaymentOut, status_code=status.HTTP_201_CREATED)
async def record_payment(payload: RecordPaymentRequest, current_user: CurrentUser = Depends(_admin_only)) -> PaymentOut:
    """Records money received at the office (cash, UPI, cheque, ...) and issues a receipt."""
    payment = await service.record_payment(current_user, payload)
    await audit.record(
        current_user, "fees.payment", f"Received ₹{payment.amount:g} from {await _payer(payment.id)} by {payment.method}, receipt {payment.receipt_number}",
        entity_type="fee_payment", entity_id=payment.id,
    )
    return payment


@router.post("/payments/{payment_id}/cancel", response_model=PaymentOut)
async def cancel_payment(
    payment_id: str, payload: CancelPaymentRequest, current_user: CurrentUser = Depends(_admin_only)
) -> PaymentOut:
    payment = await service.cancel_payment(current_user, payment_id, payload.reason)
    await audit.record(
        current_user, "fees.payment_cancelled",
        f"Cancelled receipt {payment.receipt_number} (₹{payment.amount:g}) of {await _payer(payment.id)}: {payload.reason}",
        entity_type="fee_payment", entity_id=payment.id,
    )
    return payment


async def _payer(payment_id: str) -> str:
    row = await fetch_one(
        "SELECT s.full_name, s.admission_number FROM fee_payments p JOIN students s ON s.id = p.student_id WHERE p.id = %s", (payment_id,)
    )
    return f"{row['full_name']} ({row['admission_number']})" if row else "a student"


@router.get("/payments/{payment_id}/receipt", response_model=ReceiptOut)
async def receipt(payment_id: str, current_user: CurrentUser = Depends(_admin_only)) -> ReceiptOut:
    return await service.receipt(current_user.school_id, payment_id)


@router.get("/report", response_model=FeeReport)
async def fee_report(
    class_id: str | None = None, only_with_dues: bool = False, current_user: CurrentUser = Depends(_admin_only)
) -> FeeReport:
    return await service.fee_report(current_user, class_id=class_id, only_with_dues=only_with_dues)


@router.post("/reminders", response_model=ReminderResult)
async def send_reminders(payload: ReminderRequest, current_user: CurrentUser = Depends(_admin_only)) -> ReminderResult:
    """Alerts the parents of students with unpaid (by default, overdue) fees; at most once a day per student."""
    return await service.send_reminders(current_user, class_id=payload.class_id, only_overdue=payload.only_overdue)
