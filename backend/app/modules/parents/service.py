"""Parent accounts and the parent portal.

A parent account belongs to one mobile number (the child's primary contact)
and is linked to each of their children, so siblings — even in different
schools on the platform — share one login.
"""

import json
import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Literal

import aiomysql
from fastapi import status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser
from app.core.errors import AppError
from app.core.secrets import decrypt_secret, encrypt_secret, is_encrypted
from app.core.phone import normalize_indian_mobile
from app.core.security import hash_password, parent_login_id
from app.db.database import db
from app.db.helpers import execute, fetch_all, fetch_one
from app.core.config import get_settings
from app.integrations import cashfree, gateways
from app.modules.alerts import service as alerts
from app.modules.fees import claims
from app.modules.fees import service as fees
from app.modules.fees.claims import ClaimOut
from app.modules.fees.schemas import ReceiptOut, StudentFeeAccount
from app.modules.students import accounts as student_accounts
from app.modules.students import service as students
from app.modules.teaching.service import CATEGORY_LABELS


class ParentLoginOut(BaseModel):
    student_id: str
    student_name: str
    parent_name: str
    phone: str
    password: str | None  # None when the parent already had an account (just linked)
    already_had_account: bool


class ChildSummary(BaseModel):
    student_id: str
    full_name: str
    admission_number: str
    class_name: str
    section: str
    school_name: str
    has_photo: bool
    balance: float
    overdue: float


class AttendanceDay(BaseModel):
    date: str
    status: str


class ChildRemark(BaseModel):
    category_label: str
    subject_name: str | None
    note: str
    remark_date: str
    author_name: str


class ChildAlert(BaseModel):
    kind: str
    message: str
    created_at: str


class ChildOverview(BaseModel):
    child: ChildSummary
    attendance_days: int
    present: int
    absent: int
    late: int
    recent_attendance: list[AttendanceDay]
    remarks: list[ChildRemark]
    alerts: list[ChildAlert]
    fees: StudentFeeAccount
    online_payment_enabled: bool
    offline_instructions: str = ""  # where to pay the school directly (UPI ID, bank account, office hours)
    offline_payments: list[ClaimOut] = []  # payments this family reported, and whether the school confirmed them


class OnlineOrderOut(BaseModel):
    payment_id: str  # our order id, sent back to confirm the payment
    provider: str = "cashfree"  # which checkout to open: "cashfree", "razorpay" or "phonepe"
    payment_session_id: str = ""  # Cashfree Checkout
    key_id: str = ""  # Razorpay Checkout (the school's public Key ID)
    gateway_order_id: str = ""  # Razorpay's order id
    checkout_url: str = ""  # PhonePe checkout page
    environment: str  # "production" or "sandbox", for the checkout script
    amount: float
    school_name: str
    description: str


# --- Staff side: creating parent logins -----------------------------------------


async def _primary_contact(student_id: str) -> dict | None:
    return await fetch_one(
        """
        SELECT g.full_name, g.phone FROM students s
        JOIN student_guardians g ON g.student_id = s.id AND g.relation = s.primary_contact
        WHERE s.id = %s
        """,
        (student_id,),
    )


async def _link_parent(conn, student: dict, reset_password: bool) -> ParentLoginOut:
    contact = await _primary_contact(student["id"])
    mobile = normalize_indian_mobile(contact["phone"]) if contact else None
    if mobile is None:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            "no_parent_mobile",
            f"{student['full_name']} has no valid mobile number for their primary contact. Add one first.",
        )
    login_id = parent_login_id(mobile)
    async with conn.cursor() as cur:
        await cur.execute("SELECT id, role FROM users WHERE login_id = %s", (login_id,))
        existing = await cur.fetchone()
        password = None
        if existing is None:
            user_id, password = str(uuid.uuid4()), student_accounts.generate_password()
            await cur.execute(
                """
                INSERT INTO users (id, school_id, email, login_id, password_hash, must_change_password, role, full_name, status)
                VALUES (%s, NULL, NULL, %s, %s, 1, 'parent', %s, 'active')
                """,
                (user_id, login_id, hash_password(password), contact["full_name"]),
            )
        else:
            if existing["role"] != "parent":
                raise AppError(status.HTTP_409_CONFLICT, "login_taken", "This mobile number is already used by another account.")
            user_id = existing["id"]
            if reset_password:
                password = student_accounts.generate_password()
                await cur.execute(
                    "UPDATE users SET password_hash = %s, must_change_password = 1, status = 'active' WHERE id = %s",
                    (hash_password(password), user_id),
                )
        await cur.execute(
            """
            INSERT INTO parent_students (parent_user_id, student_id, school_id) VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE school_id = VALUES(school_id)
            """,
            (user_id, student["id"], student["school_id"]),
        )
    return ParentLoginOut(
        student_id=student["id"],
        student_name=student["full_name"],
        parent_name=contact["full_name"],
        phone=mobile[2:],
        password=password,
        already_had_account=existing is not None,
    )


async def enable_parent_login(user: CurrentUser, student_id: str, reset_password: bool) -> ParentLoginOut:
    student = await students.get_student_row(user, student_id)
    if student["status"] != "active":
        raise AppError(status.HTTP_409_CONFLICT, "student_left", "This student has left.")
    return await link_parent(student, reset_password=reset_password)


async def link_parent(student: dict, reset_password: bool = False) -> ParentLoginOut:
    """Makes the student's primary contact a parent login, or links the student to their existing one."""
    async with db.pool.acquire() as conn:
        await conn.begin()
        try:
            result = await _link_parent(conn, student, reset_password)
        except (AppError, aiomysql.IntegrityError):
            await conn.rollback()
            raise
        await conn.commit()
    return result


async def enable_class_parent_logins(user: CurrentUser, class_id: str) -> tuple[list[ParentLoginOut], list[str]]:
    """Links every student in the class (without a linked parent yet) to a parent login.

    Returns the logins made or linked, and the names of students skipped for lack of a mobile number.
    """
    allowed = await students.managed_class_ids(user)
    if allowed is not None and class_id not in allowed:
        raise AppError(status.HTTP_403_FORBIDDEN, "forbidden", "Only this class's class teacher or an admin can do that.")
    rows = await fetch_all(
        """
        SELECT * FROM students s
        WHERE s.school_id = %s AND s.class_id = %s AND s.status = 'active'
          AND NOT EXISTS (SELECT 1 FROM parent_students ps JOIN users pu ON pu.id = ps.parent_user_id
                          WHERE ps.student_id = s.id AND pu.role = 'parent')
        ORDER BY s.full_name
        """,
        (user.school_id, class_id),
    )
    results, skipped = [], []
    async with db.pool.acquire() as conn:
        await conn.begin()
        for student in rows:
            try:
                results.append(await _link_parent(conn, student, reset_password=False))
            except AppError as exc:
                if exc.code == "no_parent_mobile":
                    skipped.append(student["full_name"])
                else:
                    await conn.rollback()
                    raise
        await conn.commit()
    return results, skipped


# --- Parent portal ---------------------------------------------------------------


async def _child_row(parent: CurrentUser, student_id: str) -> dict:
    row = await fetch_one(
        """
        SELECT s.*, c.name AS class_name, c.section, sc.name AS school_name
        FROM parent_students ps
        JOIN students s ON s.id = ps.student_id
        JOIN classes c ON c.id = s.class_id
        JOIN schools sc ON sc.id = s.school_id
        WHERE ps.parent_user_id = %s AND ps.student_id = %s AND s.status = 'active'
          AND sc.status = 'active' AND sc.billing_status <> 'suspended'
        """,
        (parent.id, student_id),
    )
    if row is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "child_not_found", "Child not found.")
    return row


async def _summary(row: dict) -> ChildSummary:
    account = await fees.student_account(row["school_id"], row["id"])
    return ChildSummary(
        student_id=row["id"],
        full_name=row["full_name"],
        admission_number=row["admission_number"],
        class_name=row["class_name"],
        section=row["section"],
        school_name=row["school_name"],
        has_photo=bool(row["photo_path"]),
        balance=account.balance,
        overdue=account.overdue,
    )


async def list_children(parent: CurrentUser) -> list[ChildSummary]:
    rows = await fetch_all(
        """
        SELECT s.id FROM parent_students ps JOIN students s ON s.id = ps.student_id
        WHERE ps.parent_user_id = %s ORDER BY s.full_name
        """,
        (parent.id,),
    )
    children = []
    for row in rows:
        try:
            children.append(await _summary(await _child_row(parent, row["id"])))
        except AppError:
            continue  # left the school, or the school is inactive
    return children


async def allowed_gateways(school_id: str) -> list[str]:
    """The gateways the super admin lets this school use."""
    school = await fetch_one("SELECT payment_gateways FROM schools WHERE id = %s", (school_id,))
    try:
        chosen = json.loads(school["payment_gateways"]) if school else []
    except (TypeError, ValueError):
        chosen = []
    return [p for p in gateways.PROVIDERS if p in chosen]


async def online_settings(school_id: str) -> dict | None:
    """The school's payment gateway settings, or None while online payment is off."""
    row = await fetch_one("SELECT * FROM school_payment_settings WHERE school_id = %s", (school_id,))
    if not row or not row["enabled"] or row["provider"] not in await allowed_gateways(school_id):
        return None
    if row["provider"] not in gateways.NEEDS_KEYS or (row["key_id"] and row["key_secret"]):
        return row
    return None


async def child_overview(parent: CurrentUser, student_id: str) -> ChildOverview:
    row = await _child_row(parent, student_id)
    since = alerts.today_ist() - timedelta(days=30)
    attendance = await fetch_all(
        "SELECT attendance_date, status FROM attendance WHERE student_id = %s AND attendance_date >= %s ORDER BY attendance_date DESC",
        (student_id, since),
    )
    counts = {s: sum(1 for a in attendance if a["status"] == s) for s in ("present", "absent", "late")}
    remarks = await fetch_all(
        """
        SELECT r.category, r.note, r.remark_date, sub.name AS subject_name, u.full_name AS author_name
        FROM student_remarks r LEFT JOIN subjects sub ON sub.id = r.subject_id LEFT JOIN users u ON u.id = r.author_id
        WHERE r.student_id = %s AND r.notify_parent = 1 ORDER BY r.remark_date DESC, r.created_at DESC LIMIT 50
        """,
        (student_id,),
    )
    alert_rows = await fetch_all(
        "SELECT kind, message, created_at FROM parent_alerts WHERE student_id = %s ORDER BY created_at DESC LIMIT 50",
        (student_id,),
    )
    return ChildOverview(
        child=await _summary(row),
        attendance_days=len(attendance),
        present=counts["present"],
        absent=counts["absent"],
        late=counts["late"],
        recent_attendance=[AttendanceDay(date=a["attendance_date"].isoformat(), status=a["status"]) for a in attendance[:14]],
        remarks=[
            ChildRemark(
                category_label=CATEGORY_LABELS[r["category"]],
                subject_name=r["subject_name"],
                note=r["note"],
                remark_date=r["remark_date"].isoformat(),
                author_name=r["author_name"] or "",
            )
            for r in remarks
        ],
        alerts=[ChildAlert(kind=a["kind"], message=a["message"], created_at=a["created_at"].isoformat()) for a in alert_rows],
        fees=await fees.student_account(row["school_id"], student_id),
        online_payment_enabled=await online_settings(row["school_id"]) is not None,
        offline_instructions=await claims.instructions(row["school_id"]),
        offline_payments=await claims.list_for_student(row["school_id"], student_id),
    )


async def child_row(parent: CurrentUser, student_id: str) -> dict:
    return await _child_row(parent, student_id)


async def child_photo_row(parent: CurrentUser, student_id: str) -> dict:
    return await _child_row(parent, student_id)


async def child_receipt(parent: CurrentUser, student_id: str, payment_id: str) -> ReceiptOut:
    row = await _child_row(parent, student_id)
    payment = await fetch_one("SELECT student_id FROM fee_payments WHERE id = %s", (payment_id,))
    if payment is None or payment["student_id"] != student_id:
        raise AppError(status.HTTP_404_NOT_FOUND, "receipt_not_found", "Receipt not found.")
    return await fees.receipt(row["school_id"], payment_id)


# --- Online payment (the school's own gateway) --------------------------------------

_ONLINE_OFF = AppError(
    status.HTTP_409_CONFLICT,
    "online_payment_unavailable",
    "Online payment isn't available for this school yet. Please pay at the school office.",
)


def secret_of(settings: dict) -> str:
    return decrypt_secret(settings["key_secret"]) if settings["key_secret"] else ""


def return_url() -> str:
    """Where PhonePe sends the payer back to (the app; the page itself checks the payment)."""
    origins = get_settings().cors_origin_list
    return (origins[0] if origins else "https://college.anvsoftsolutions.com").rstrip("/") + "/"


def gateway_failed(exc: gateways.GatewayError) -> AppError:
    return AppError(status.HTTP_502_BAD_GATEWAY, "payment_gateway_error", str(exc))


def pending_message(settings: dict, what: str) -> str:
    return f"{gateways.label(settings['provider'])} hasn't confirmed this payment yet. If money was taken, {what} within a few minutes."


def order_out(checkout: gateways.Checkout, payment_id: str, amount: Decimal, school_name: str, description: str) -> OnlineOrderOut:
    return OnlineOrderOut(
        payment_id=payment_id, provider=checkout.provider, payment_session_id=checkout.payment_session_id, key_id=checkout.key_id,
        gateway_order_id=checkout.gateway_ref if checkout.provider in ("razorpay", "demo") else "", checkout_url=checkout.checkout_url,
        environment=checkout.environment, amount=float(amount), school_name=school_name, description=description,
    )


async def _parent_phone(parent: CurrentUser) -> str:
    # Gateways want the payer's mobile; a parent's login is their mobile ("parent:91XXXXXXXXXX").
    if parent.role == "student":
        # A student's login is their roll number: use their own mobile, else their primary contact's.
        row = await fetch_one(
            """
            SELECT s.phone, g.phone AS contact_phone FROM students s
            LEFT JOIN student_guardians g ON g.student_id = s.id AND g.relation = s.primary_contact
            WHERE s.user_id = %s
            """,
            (parent.id,),
        )
        mobile = normalize_indian_mobile((row and (row["phone"] or row["contact_phone"])) or "")
        return mobile[-10:] if mobile else ""
    login = await fetch_one("SELECT login_id FROM users WHERE id = %s", (parent.id,))
    return (login["login_id"] or "").rsplit(":", 1)[-1][-10:]


async def start_online_payment(parent: CurrentUser, student_id: str, student_fee_id: str) -> OnlineOrderOut:
    row = await _child_row(parent, student_id)
    settings = await online_settings(row["school_id"])
    if settings is None:
        raise _ONLINE_OFF
    fee = await fees.get_student_fee(row["school_id"], student_fee_id)
    if fee["student_id"] != student_id:
        raise AppError(status.HTTP_404_NOT_FOUND, "student_fee_not_found", "Fee not found.")
    if fee["balance"] <= 0:
        raise AppError(status.HTTP_409_CONFLICT, "already_paid", "This fee is already paid.")

    payment_id = str(uuid.uuid4())
    item = await fetch_one("SELECT name FROM fee_items WHERE id = %s", (fee["fee_item_id"],))
    description = f"{item['name']} — {row['full_name']} ({row['admission_number']})"
    try:
        checkout = await gateways.create_order(
            settings, secret_of(settings), order_id=payment_id, amount=fee["balance"], customer_id=parent.id.replace("-", ""),
            customer_phone=await _parent_phone(parent), customer_name=parent.full_name, note=description, redirect_url=return_url(),
        )
    except gateways.GatewayError as exc:
        raise gateway_failed(exc) from exc

    await execute(
        """
        INSERT INTO fee_payments (id, school_id, student_id, student_fee_id, amount, method, paid_on, status, gateway_order_id, gateway, gateway_ref)
        VALUES (%s, %s, %s, %s, %s, 'online', %s, 'pending', %s, %s, %s)
        """,
        (payment_id, row["school_id"], student_id, student_fee_id, fee["balance"], alerts.today_ist(), payment_id, checkout.provider, checkout.gateway_ref),
    )
    return order_out(checkout, payment_id, fee["balance"], row["school_name"], description)


async def _check(payment: dict, settings: dict) -> gateways.OrderState:
    """Asks the gateway that took this payment about its order."""
    if (payment["gateway"] or "cashfree") != settings["provider"]:
        return gateways.OrderState("pending", None)  # the school switched gateways since; the old one can't be asked
    try:
        return await gateways.check_order(settings, secret_of(settings), payment["gateway_ref"] or payment["gateway_order_id"])
    except gateways.GatewayError as exc:
        raise gateway_failed(exc) from exc


async def _finalize(payment_id: str, settings: dict) -> str:
    """Asks the gateway about the order and records the result: 'paid', 'failed' or 'pending'.

    Used by the parent's confirm call and by the webhook. The payment row is locked,
    so the two can't both record it (and receipt numbers never skip).
    """
    payment = await fetch_one("SELECT * FROM fee_payments WHERE id = %s", (payment_id,))
    state = await _check(payment, settings)
    if state.status == "failed":
        await execute("UPDATE fee_payments SET status = 'failed' WHERE id = %s AND status = 'pending'", (payment_id,))
        return "failed"
    if state.status != "paid":
        return "pending"

    async with db.pool.acquire() as conn:
        await conn.begin()
        try:
            async with conn.cursor() as cur:
                await cur.execute("SELECT * FROM fee_payments WHERE id = %s FOR UPDATE", (payment_id,))
                payment = await cur.fetchone()
                if payment["status"] == "success":
                    await conn.commit()
                    return "paid"
                if state.amount != Decimal(payment["amount"]):
                    await cur.execute("UPDATE fee_payments SET status = 'failed' WHERE id = %s", (payment_id,))
                    await conn.commit()
                    return "failed"
                receipt_number = await fees.next_receipt_number(cur, payment["school_id"], alerts.today_ist().year)
                await cur.execute(
                    "UPDATE fee_payments SET status = 'success', gateway_payment_id = %s, receipt_number = %s, paid_on = %s WHERE id = %s",
                    (state.payment_ref or None, receipt_number, alerts.today_ist(), payment_id),
                )
        except Exception:
            await conn.rollback()
            raise
        await conn.commit()
    return "paid"


async def confirm_online_payment(parent: CurrentUser, student_id: str, payment_id: str) -> ReceiptOut:
    row = await _child_row(parent, student_id)
    payment = await fetch_one(
        "SELECT * FROM fee_payments WHERE id = %s AND student_id = %s AND method = 'online'", (payment_id, student_id)
    )
    if payment is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "payment_not_found", "Payment not found.")
    if payment["status"] == "success":
        return await fees.receipt(row["school_id"], payment_id)
    settings = await online_settings(row["school_id"])
    if settings is None:
        raise _ONLINE_OFF
    result = await _finalize(payment_id, settings)
    if result == "paid":
        return await fees.receipt(row["school_id"], payment_id)
    if result == "pending":
        raise AppError(status.HTTP_409_CONFLICT, "payment_pending", pending_message(settings, "the receipt appears here"))
    raise AppError(status.HTTP_400_BAD_REQUEST, "payment_not_verified", "This payment didn't go through. No money was recorded.")


# --- Paying all due fees in one go -------------------------------------------------
# One gateway order (our id "all_…") covers every fee with a balance. Each fee gets its
# own pending payment row sharing the order as gateway_batch_id, and its own receipt
# once the gateway confirms the whole order.


class PaidAllOut(BaseModel):
    receipts: list[ReceiptOut]


async def start_pay_all(parent: CurrentUser, student_id: str) -> OnlineOrderOut:
    row = await _child_row(parent, student_id)
    settings = await online_settings(row["school_id"])
    if settings is None:
        raise _ONLINE_OFF
    account = await fees.student_account(row["school_id"], student_id)
    due = [await fees.get_student_fee(row["school_id"], line.id) for line in account.lines if line.balance > 0]
    if not due:
        raise AppError(status.HTTP_409_CONFLICT, "already_paid", "All fees are already paid.")
    total = sum((fee["balance"] for fee in due), Decimal("0"))

    batch_id = f"all_{uuid.uuid4().hex}"  # gateway order ids are at most 40 characters (Razorpay)
    description = f"{len(due)} fees — {row['full_name']} ({row['admission_number']})"
    try:
        checkout = await gateways.create_order(
            settings, secret_of(settings), order_id=batch_id, amount=total, customer_id=parent.id.replace("-", ""),
            customer_phone=await _parent_phone(parent), customer_name=parent.full_name, note=description, redirect_url=return_url(),
        )
    except gateways.GatewayError as exc:
        raise gateway_failed(exc) from exc

    async with db.pool.acquire() as conn:
        await conn.begin()
        try:
            async with conn.cursor() as cur:
                for fee in due:
                    payment_id = str(uuid.uuid4())
                    await cur.execute(
                        """
                        INSERT INTO fee_payments (id, school_id, student_id, student_fee_id, amount, method, paid_on, status,
                                                  gateway_order_id, gateway_batch_id, gateway, gateway_ref)
                        VALUES (%s, %s, %s, %s, %s, 'online', %s, 'pending', %s, %s, %s, %s)
                        """,
                        (payment_id, row["school_id"], student_id, fee["id"], fee["balance"], alerts.today_ist(), payment_id, batch_id,
                         checkout.provider, checkout.gateway_ref),
                    )
        except Exception:
            await conn.rollback()
            raise
        await conn.commit()
    return order_out(checkout, batch_id, total, row["school_name"], description)


async def _finalize_batch(batch_id: str, settings: dict) -> str:
    """Like _finalize, for a pay-all order: every fee in it is recorded, or none."""
    first = await fetch_one("SELECT * FROM fee_payments WHERE gateway_batch_id = %s ORDER BY created_at, id LIMIT 1", (batch_id,))
    state = await _check({**first, "gateway_ref": first["gateway_ref"] or batch_id}, settings)
    if state.status == "failed":
        await execute("UPDATE fee_payments SET status = 'failed' WHERE gateway_batch_id = %s AND status = 'pending'", (batch_id,))
        return "failed"
    if state.status != "paid":
        return "pending"

    async with db.pool.acquire() as conn:
        await conn.begin()
        try:
            async with conn.cursor() as cur:
                await cur.execute("SELECT * FROM fee_payments WHERE gateway_batch_id = %s ORDER BY created_at, id FOR UPDATE", (batch_id,))
                payments = await cur.fetchall()
                if all(p["status"] == "success" for p in payments):
                    await conn.commit()
                    return "paid"
                if state.amount != sum((Decimal(p["amount"]) for p in payments), Decimal("0")):
                    await cur.execute("UPDATE fee_payments SET status = 'failed' WHERE gateway_batch_id = %s AND status = 'pending'", (batch_id,))
                    await conn.commit()
                    return "failed"
                for payment in payments:
                    if payment["status"] != "pending":
                        continue
                    receipt_number = await fees.next_receipt_number(cur, payment["school_id"], alerts.today_ist().year)
                    await cur.execute(
                        "UPDATE fee_payments SET status = 'success', gateway_payment_id = %s, receipt_number = %s, paid_on = %s WHERE id = %s",
                        (state.payment_ref or None, receipt_number, alerts.today_ist(), payment["id"]),
                    )
        except Exception:
            await conn.rollback()
            raise
        await conn.commit()
    return "paid"


async def confirm_pay_all(parent: CurrentUser, student_id: str, batch_id: str) -> PaidAllOut:
    row = await _child_row(parent, student_id)
    payments = await fetch_all(
        "SELECT id, status FROM fee_payments WHERE gateway_batch_id = %s AND student_id = %s ORDER BY created_at, id", (batch_id, student_id)
    )
    if not payments:
        raise AppError(status.HTTP_404_NOT_FOUND, "payment_not_found", "Payment not found.")
    if any(p["status"] != "success" for p in payments):
        settings = await online_settings(row["school_id"])
        if settings is None:
            raise _ONLINE_OFF
        result = await _finalize_batch(batch_id, settings)
        if result == "pending":
            raise AppError(status.HTTP_409_CONFLICT, "payment_pending", pending_message(settings, "the receipts appear here"))
        if result == "failed":
            raise AppError(status.HTTP_400_BAD_REQUEST, "payment_not_verified", "This payment didn't go through. No money was recorded.")
    return PaidAllOut(receipts=[await fees.receipt(row["school_id"], p["id"]) for p in payments])


# --- Webhooks: a gateway telling us an order changed ------------------------------------
# Whatever a webhook says, the order is then checked with the gateway itself (server to
# server), so a forged webhook can at most make us ask. Cashfree's is also signature-checked.


def webhook_order_ref(provider: str, raw_body: bytes) -> str:
    """The gateway's order id from its webhook body."""
    try:
        payload = json.loads(raw_body)
        if provider == "cashfree":
            return str(payload["data"]["order"]["order_id"])
        if provider == "razorpay":
            entities = payload["payload"]
            if "order" in entities:
                return str(entities["order"]["entity"]["id"])
            return str(entities["payment"]["entity"]["order_id"])
        if provider == "phonepe":
            return str(payload["payload"]["merchantOrderId"])
    except (ValueError, KeyError, TypeError) as exc:
        raise AppError(status.HTTP_400_BAD_REQUEST, "invalid_webhook", "Unrecognised webhook.") from exc
    raise AppError(status.HTTP_404_NOT_FOUND, "unknown_gateway", "Unknown payment gateway.")


async def handle_webhook(raw_body: bytes, timestamp: str, signature: str, provider: str = "cashfree") -> None:
    order_ref = webhook_order_ref(provider, raw_body)
    found = await fetch_one(
        "SELECT * FROM fee_payments WHERE gateway_ref = %s AND gateway = %s AND method = 'online' ORDER BY status = 'pending' DESC LIMIT 1",
        (order_ref, provider),
    )
    if found is None:
        from app.modules.admissions import service as admissions  # imported here: admissions imports this module

        # An admission application fee, or not ours: either way acknowledged so the gateway stops retrying.
        await admissions.handle_fee_webhook(provider, order_ref, raw_body, timestamp, signature)
        return
    settings = await fetch_one("SELECT * FROM school_payment_settings WHERE school_id = %s", (found["school_id"],))
    if settings is None or not settings["key_secret"] or settings["provider"] != provider:
        return
    if provider == "cashfree" and not cashfree.verify_webhook_signature(raw_body, timestamp, signature, secret_of(settings)):
        raise AppError(status.HTTP_401_UNAUTHORIZED, "invalid_signature", "Webhook signature doesn't match.")
    if found["status"] == "pending":
        await (_finalize_batch(found["gateway_batch_id"], settings) if found["gateway_batch_id"] else _finalize(found["id"], settings))


# --- Admin: the school's payment gateway connection -------------------------------------


class PaymentSettingsIn(BaseModel):
    provider: Literal["cashfree", "razorpay", "phonepe", "demo"] = "cashfree"
    key_id: str = Field(default="", max_length=100)  # Cashfree App ID, Razorpay Key ID or PhonePe Client ID
    key_secret: str | None = Field(default=None, max_length=200)  # the matching secret; omit to keep the saved one
    client_version: str = Field(default="", max_length=10)  # PhonePe only
    environment: Literal["production", "sandbox"] = "production"  # sandbox = the gateway's test mode
    enabled: bool


class PaymentSettingsOut(BaseModel):
    provider: str
    key_id: str
    has_secret: bool
    environment: str
    enabled: bool
    client_version: str = ""
    allowed_providers: list[str] = []  # the gateways the super admin lets this school use


async def get_payment_settings(school_id: str) -> PaymentSettingsOut:
    row = await fetch_one("SELECT * FROM school_payment_settings WHERE school_id = %s", (school_id,))
    allowed = await allowed_gateways(school_id)
    if row is None:
        return PaymentSettingsOut(
            provider=allowed[0] if allowed else "cashfree", key_id="", has_secret=False, environment="production", enabled=False,
            allowed_providers=allowed,
        )
    return PaymentSettingsOut(
        provider=row["provider"], key_id=row["key_id"], has_secret=bool(row["key_secret"]),
        environment=row["environment"], enabled=bool(row["enabled"]), client_version=row["client_version"], allowed_providers=allowed,
    )


async def save_payment_settings(school_id: str, payload: PaymentSettingsIn) -> PaymentSettingsOut:
    allowed = await allowed_gateways(school_id)
    if payload.provider not in allowed:
        raise AppError(
            status.HTTP_403_FORBIDDEN, "gateway_not_allowed",
            f"{gateways.label(payload.provider)} isn't available for your school. Ask ANV Soft Solutions to switch it on.",
        )
    current = await fetch_one("SELECT provider, key_secret FROM school_payment_settings WHERE school_id = %s", (school_id,))
    if payload.key_secret is not None:
        secret = encrypt_secret(payload.key_secret.strip())
    elif current and current["provider"] != payload.provider:
        secret = ""  # another gateway's secret is no use to this one
    else:
        stored = current["key_secret"] if current else ""
        # An older plain-text secret is encrypted on this save.
        secret = stored if is_encrypted(stored) or not stored else encrypt_secret(stored)
    name = gateways.label(payload.provider)
    if payload.enabled and payload.provider in gateways.NEEDS_KEYS and not (payload.key_id.strip() and secret):
        raise AppError(status.HTTP_400_BAD_REQUEST, "keys_required", f"Enter the {name} ID and secret key before turning online payments on.")
    if payload.enabled and payload.provider == "phonepe" and not payload.client_version.strip():
        raise AppError(status.HTTP_400_BAD_REQUEST, "keys_required", "Enter the PhonePe Client Version before turning online payments on.")
    await execute(
        """
        INSERT INTO school_payment_settings (school_id, provider, key_id, key_secret, client_version, environment, enabled)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE provider = VALUES(provider), key_id = VALUES(key_id), key_secret = VALUES(key_secret),
                                client_version = VALUES(client_version), environment = VALUES(environment), enabled = VALUES(enabled)
        """,
        (school_id, payload.provider, payload.key_id.strip(), secret, payload.client_version.strip(), payload.environment, payload.enabled),
    )
    return await get_payment_settings(school_id)
