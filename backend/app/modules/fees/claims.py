"""Offline payments reported by parents.

When online payment fails or a parent prefers to pay another way, they pay the
school directly (UPI to the school, bank transfer, cash or cheque at the
office) and report it here with a reference and, optionally, a screenshot. The
office checks its account and approves the report, which records the payment
with a receipt as if taken at the counter, or rejects it with a reason. The
fee's balance changes only on approval.
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Literal

from fastapi import UploadFile, status
from pydantic import BaseModel, Field, field_validator

from app.api.deps import CurrentUser
from app.core.errors import AppError
from app.db.helpers import execute, fetch_all, fetch_one
from app.modules.alerts.service import today_ist
from app.modules.fees import service as fees
from app.modules.fees.schemas import RecordPaymentRequest
from app.modules.notifications import service as notifications
from app.modules.students.files import DOCUMENT_TYPES, MAX_DOCUMENT_BYTES, private_path, save_private_file

OfflineMethod = Literal["upi", "bank_transfer", "cash", "cheque"]
METHOD_LABELS = {"upi": "UPI", "bank_transfer": "Bank transfer", "cash": "Cash at office", "cheque": "Cheque"}
MAX_DAYS_BACK = 90


class ClaimIn(BaseModel):
    amount: Decimal = Field(gt=0, le=Decimal("10000000"))
    method: OfflineMethod
    reference: str = Field(default="", max_length=100)  # UPI transaction id, cheque number, ...
    paid_on: date
    note: str = Field(default="", max_length=300)

    @field_validator("reference", "note", mode="before")
    @classmethod
    def _strip(cls, value):
        return value.strip() if isinstance(value, str) else value


class ClaimOut(BaseModel):
    id: str
    student_id: str
    student_name: str
    admission_number: str
    class_name: str
    student_fee_id: str
    fee_name: str
    amount: float
    method: str
    method_label: str
    reference: str
    paid_on: date
    note: str
    has_proof: bool
    status: str
    review_note: str
    receipt_number: str | None
    parent_name: str
    created_at: str


class RejectClaimIn(BaseModel):
    note: str = Field(min_length=3, max_length=300)


_SELECT = """
    SELECT cl.*, s.full_name AS student_name, s.admission_number, CONCAT(c.name, ' - ', c.section) AS class_name,
           fi.name AS fee_name, p.receipt_number, u.full_name AS parent_name
    FROM fee_payment_claims cl
    JOIN students s ON s.id = cl.student_id
    JOIN classes c ON c.id = s.class_id
    JOIN student_fees sf ON sf.id = cl.student_fee_id
    JOIN fee_items fi ON fi.id = sf.fee_item_id
    LEFT JOIN fee_payments p ON p.id = cl.payment_id
    LEFT JOIN users u ON u.id = cl.parent_user_id
"""


def _out(r: dict) -> ClaimOut:
    return ClaimOut(
        id=r["id"], student_id=r["student_id"], student_name=r["student_name"], admission_number=r["admission_number"],
        class_name=r["class_name"], student_fee_id=r["student_fee_id"], fee_name=r["fee_name"], amount=float(r["amount"]),
        method=r["method"], method_label=METHOD_LABELS.get(r["method"], r["method"]), reference=r["reference"], paid_on=r["paid_on"],
        note=r["note"], has_proof=bool(r["proof_path"]), status=r["status"], review_note=r["review_note"],
        receipt_number=r["receipt_number"], parent_name=r["parent_name"] or "", created_at=r["created_at"].isoformat(),
    )


# --- Parent side ------------------------------------------------------------------------


async def submit(parent: CurrentUser, child: dict, student_fee_id: str, payload: ClaimIn, proof: UploadFile | None) -> ClaimOut:
    """child: the parent's child row (already checked to be theirs)."""
    fee = await fees.get_student_fee(child["school_id"], student_fee_id)
    if fee["student_id"] != child["id"]:
        raise AppError(status.HTTP_404_NOT_FOUND, "student_fee_not_found", "Fee not found.")
    waiting = await fetch_one(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM fee_payment_claims WHERE student_fee_id = %s AND status = 'submitted'", (student_fee_id,)
    )
    if payload.amount > fee["balance"] - Decimal(waiting["total"]):
        raise AppError(
            status.HTTP_400_BAD_REQUEST, "amount_exceeds_balance",
            f"Only ₹{max(fee['balance'] - Decimal(waiting['total']), Decimal('0')):.2f} of this fee is still due (after payments waiting for the school to check).",
        )
    today = today_ist()
    if not (today - timedelta(days=MAX_DAYS_BACK) <= payload.paid_on <= today):
        raise AppError(status.HTTP_400_BAD_REQUEST, "invalid_date", "Give the date you paid (within the last 3 months).")
    if payload.method in ("upi", "bank_transfer") and not payload.reference and proof is None:
        raise AppError(status.HTTP_400_BAD_REQUEST, "reference_required", "Give the UPI / bank transaction number or attach a screenshot.")

    claim_id = str(uuid.uuid4())
    proof_path = None
    if proof is not None:
        proof_path, _ = await save_private_file(
            folder=Path(child["school_id"]) / "fee_claims" / claim_id, file=proof, allowed_types=DOCUMENT_TYPES, max_bytes=MAX_DOCUMENT_BYTES
        )
    await execute(
        """
        INSERT INTO fee_payment_claims (id, school_id, student_id, student_fee_id, parent_user_id, amount, method, reference, paid_on,
                                        note, proof_path, proof_content_type)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (claim_id, child["school_id"], child["id"], student_fee_id, parent.id, payload.amount, payload.method, payload.reference,
         payload.paid_on, payload.note, proof_path, proof.content_type if proof else None),
    )
    await notifications.notify(
        await notifications.admin_user_ids(child["school_id"]),
        school_id=child["school_id"],
        title=f"Fee paid offline: {child['full_name']}",
        body=f"₹{payload.amount:,.2f} by {METHOD_LABELS[payload.method]}{f', ref {payload.reference}' if payload.reference else ''}. Check and approve.",
        link="fees",
    )
    return await _get(child["school_id"], claim_id)


async def list_for_student(school_id: str, student_id: str) -> list[ClaimOut]:
    rows = await fetch_all(f"{_SELECT} WHERE cl.school_id = %s AND cl.student_id = %s ORDER BY cl.created_at DESC LIMIT 50", (school_id, student_id))
    return [_out(r) for r in rows]


async def instructions(school_id: str) -> str:
    row = await fetch_one("SELECT offline_instructions FROM school_payment_settings WHERE school_id = %s", (school_id,))
    return row["offline_instructions"] if row else ""


# --- Office side ------------------------------------------------------------------------


async def _get(school_id: str, claim_id: str) -> ClaimOut:
    row = await fetch_one(f"{_SELECT} WHERE cl.id = %s AND cl.school_id = %s", (claim_id, school_id))
    if row is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "claim_not_found", "Payment report not found.")
    return _out(row)


async def list_claims(user: CurrentUser, *, status_filter: str | None) -> list[ClaimOut]:
    where, params = ["cl.school_id = %s"], [user.school_id]
    if status_filter:
        where.append("cl.status = %s")
        params.append(status_filter)
    rows = await fetch_all(f"{_SELECT} WHERE {' AND '.join(where)} ORDER BY cl.status = 'submitted' DESC, cl.created_at DESC LIMIT 300", tuple(params))
    return [_out(r) for r in rows]


async def proof_file(user: CurrentUser, claim_id: str) -> tuple[Path, str]:
    row = await fetch_one("SELECT proof_path, proof_content_type FROM fee_payment_claims WHERE id = %s AND school_id = %s", (claim_id, user.school_id))
    if row is None or not row["proof_path"]:
        raise AppError(status.HTTP_404_NOT_FOUND, "file_not_found", "File not found.")
    return private_path(row["proof_path"]), row["proof_content_type"]


async def _submitted(user: CurrentUser, claim_id: str) -> dict:
    row = await fetch_one("SELECT * FROM fee_payment_claims WHERE id = %s AND school_id = %s", (claim_id, user.school_id))
    if row is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "claim_not_found", "Payment report not found.")
    if row["status"] != "submitted":
        raise AppError(status.HTTP_409_CONFLICT, "already_reviewed", "This payment report was already checked.")
    return row


async def approve(user: CurrentUser, claim_id: str) -> ClaimOut:
    """Records the payment (with a receipt) as if taken at the office."""
    claim = await _submitted(user, claim_id)
    # Taken first, so two admins approving at once can't both record the money.
    taken = await execute(
        "UPDATE fee_payment_claims SET status = 'approved', reviewed_by = %s, reviewed_at = %s WHERE id = %s AND status = 'submitted'",
        (user.id, datetime.now(timezone.utc), claim_id),
    )
    if not taken:
        raise AppError(status.HTTP_409_CONFLICT, "already_reviewed", "This payment report was already checked.")
    try:
        payment = await fees.record_payment(
            user,
            RecordPaymentRequest(
                student_fee_id=claim["student_fee_id"], amount=Decimal(claim["amount"]), method=claim["method"],
                reference=claim["reference"], paid_on=claim["paid_on"],
                notes=("Reported by parent: " + claim["note"] if claim["note"] else "Reported by parent")[:300],
            ),
        )
    except AppError:
        # e.g. the fee was meanwhile paid at the counter: the report goes back to the queue.
        await execute("UPDATE fee_payment_claims SET status = 'submitted', reviewed_by = NULL, reviewed_at = NULL WHERE id = %s", (claim_id,))
        raise
    await execute("UPDATE fee_payment_claims SET payment_id = %s WHERE id = %s", (payment.id, claim_id))
    await _tell_parent(claim, "Fee payment confirmed", f"₹{Decimal(claim['amount']):,.2f} received. Receipt {payment.receipt_number}.")
    return await _get(user.school_id, claim_id)


async def reject(user: CurrentUser, claim_id: str, note: str) -> ClaimOut:
    claim = await _submitted(user, claim_id)
    taken = await execute(
        "UPDATE fee_payment_claims SET status = 'rejected', review_note = %s, reviewed_by = %s, reviewed_at = %s WHERE id = %s AND status = 'submitted'",
        (note.strip(), user.id, datetime.now(timezone.utc), claim_id),
    )
    if not taken:
        raise AppError(status.HTTP_409_CONFLICT, "already_reviewed", "This payment report was already checked.")
    await _tell_parent(claim, "Fee payment not confirmed", f"₹{Decimal(claim['amount']):,.2f}: {note.strip()}")
    return await _get(user.school_id, claim_id)


async def _tell_parent(claim: dict, title: str, body: str) -> None:
    if claim["parent_user_id"]:
        await notifications.notify([claim["parent_user_id"]], school_id=claim["school_id"], title=title, body=body, link="parent")


async def save_instructions(user: CurrentUser, text: str) -> str:
    await execute(
        """
        INSERT INTO school_payment_settings (school_id, provider, offline_instructions) VALUES (%s, 'cashfree', %s)
        ON DUPLICATE KEY UPDATE offline_instructions = VALUES(offline_instructions)
        """,
        (user.school_id, text.strip()),
    )
    return await instructions(user.school_id)
