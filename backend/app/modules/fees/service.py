"""Fees: fee items per class, each student's dues, payments, receipts, reminders.

Money is Decimal throughout and only turned into float for responses. A
student fee's balance is amount - discount - successful payments; pending
online payments and cancelled entries never count.
"""

import uuid
from collections import defaultdict
from datetime import date
from decimal import Decimal

from fastapi import status

from app.api.deps import CurrentUser
from app.core.errors import AppError
from app.db.database import db
from app.db.helpers import execute, fetch_all, fetch_one
from app.modules.alerts import service as alerts
from app.modules.fees.schemas import (
    CreateFeeItemRequest,
    FeeItemOut,
    FeeReport,
    PaymentOut,
    ReceiptOut,
    RecordPaymentRequest,
    ReminderResult,
    StudentFeeAccount,
    StudentFeeLine,
    StudentFeeSummary,
    UpdateFeeItemRequest,
)

ZERO = Decimal("0.00")


def _money(value) -> float:
    return float(Decimal(value).quantize(Decimal("0.01")))


def _not_found(what: str) -> AppError:
    return AppError(status.HTTP_404_NOT_FOUND, f"{what.replace(' ', '_')}_not_found", f"{what.capitalize()} not found.")


# --- Fee items ----------------------------------------------------------------


async def _assign_to_class(cur, school_id: str, fee_item_id: str, class_id: str, amount: Decimal) -> int:
    """Gives every active student in the class this fee (skipping ones who already have it)."""
    await cur.execute(
        """
        SELECT s.id FROM students s
        WHERE s.class_id = %s AND s.status = 'active'
          AND NOT EXISTS (SELECT 1 FROM student_fees sf WHERE sf.student_id = s.id AND sf.fee_item_id = %s)
        """,
        (class_id, fee_item_id),
    )
    students = await cur.fetchall()
    for student in students:
        await cur.execute(
            """
            INSERT INTO student_fees (id, school_id, student_id, fee_item_id, amount)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (str(uuid.uuid4()), school_id, student["id"], fee_item_id, amount),
        )
    return len(students)


async def _active_students(school_id: str, student_ids: list[str]) -> list[dict]:
    """The given students (id, class_id), all active and in this school, or a 400."""
    student_ids = list(dict.fromkeys(student_ids))
    placeholders = ", ".join(["%s"] * len(student_ids))
    rows = await fetch_all(
        f"SELECT id, class_id FROM students WHERE school_id = %s AND status = 'active' AND id IN ({placeholders})",
        (school_id, *student_ids),
    )
    if len(rows) != len(student_ids):
        raise AppError(status.HTTP_400_BAD_REQUEST, "invalid_student", "Choose current students of this school.")
    return rows


async def _bill_students(cur, school_id: str, fee_item_id: str, student_ids: list[str], amount: Decimal) -> int:
    """Gives these students the fee, skipping ones who already have it."""
    added = 0
    for student_id in student_ids:
        await cur.execute("SELECT 1 FROM student_fees WHERE student_id = %s AND fee_item_id = %s", (student_id, fee_item_id))
        if await cur.fetchone():
            continue
        await cur.execute(
            "INSERT INTO student_fees (id, school_id, student_id, fee_item_id, amount) VALUES (%s, %s, %s, %s, %s)",
            (str(uuid.uuid4()), school_id, student_id, fee_item_id, amount),
        )
        added += 1
    return added


async def create_fee_items(user: CurrentUser, payload: CreateFeeItemRequest) -> list[FeeItemOut]:
    # A fee item belongs to one class, so chosen students are grouped by their class.
    chosen: dict[str, list[str]] = {}
    if payload.student_ids:
        for student in await _active_students(user.school_id, payload.student_ids):
            chosen.setdefault(student["class_id"], []).append(student["id"])
        class_ids = list(chosen)
    else:
        class_ids = list(dict.fromkeys(payload.class_ids))
        placeholders = ", ".join(["%s"] * len(class_ids))
        found = await fetch_all(
            f"SELECT id FROM classes WHERE school_id = %s AND id IN ({placeholders})", (user.school_id, *class_ids)
        )
        if len(found) != len(class_ids):
            raise AppError(status.HTTP_400_BAD_REQUEST, "invalid_class", "Choose classes from this school.")

    created = []
    async with db.pool.acquire() as conn:
        await conn.begin()
        async with conn.cursor() as cur:
            for class_id in class_ids:
                item_id = str(uuid.uuid4())
                await cur.execute(
                    """
                    INSERT INTO fee_items (id, school_id, class_id, name, category, applies_to, term_label, academic_year, amount, due_date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (item_id, user.school_id, class_id, payload.name, payload.category, "selected" if chosen else "class",
                     payload.term_label, payload.academic_year, payload.amount, payload.due_date),
                )
                if chosen:
                    await _bill_students(cur, user.school_id, item_id, chosen[class_id], payload.amount)
                else:
                    await _assign_to_class(cur, user.school_id, item_id, class_id, payload.amount)
                created.append(item_id)
        await conn.commit()
    items = {item.id: item for item in await list_fee_items(user, class_id=None)}
    return [items[item_id] for item_id in created]


async def list_fee_items(user: CurrentUser, *, class_id: str | None) -> list[FeeItemOut]:
    where, params = ["fi.school_id = %s"], [user.school_id]
    if class_id:
        where.append("fi.class_id = %s")
        params.append(class_id)
    rows = await fetch_all(
        f"""
        SELECT fi.*, c.name AS class_name, c.section,
               (SELECT COUNT(*) FROM student_fees sf WHERE sf.fee_item_id = fi.id) AS student_count,
               (SELECT COALESCE(SUM(sf.amount - sf.discount), 0) FROM student_fees sf WHERE sf.fee_item_id = fi.id) AS billed,
               (SELECT COALESCE(SUM(p.amount), 0) FROM fee_payments p JOIN student_fees sf ON sf.id = p.student_fee_id
                 WHERE sf.fee_item_id = fi.id AND p.status = 'success') AS collected
        FROM fee_items fi JOIN classes c ON c.id = fi.class_id
        WHERE {' AND '.join(where)}
        ORDER BY fi.due_date, fi.name, c.name, c.section
        """,
        tuple(params),
    )
    return [
        FeeItemOut(
            id=r["id"],
            class_id=r["class_id"],
            class_name=r["class_name"],
            section=r["section"],
            name=r["name"],
            category=r["category"],
            applies_to=r["applies_to"],
            term_label=r["term_label"],
            academic_year=r["academic_year"],
            amount=_money(r["amount"]),
            due_date=r["due_date"],
            student_count=r["student_count"],
            collected=_money(r["collected"]),
            pending=_money(max(Decimal(r["billed"]) - Decimal(r["collected"]), ZERO)),
        )
        for r in rows
    ]


async def _get_item(user: CurrentUser, item_id: str) -> dict:
    row = await fetch_one("SELECT * FROM fee_items WHERE id = %s AND school_id = %s", (item_id, user.school_id))
    if row is None:
        raise _not_found("fee item")
    return row


async def _item_has_payments(item_id: str) -> bool:
    return bool(
        await fetch_one(
            """
            SELECT p.id FROM fee_payments p JOIN student_fees sf ON sf.id = p.student_fee_id
            WHERE sf.fee_item_id = %s AND p.status IN ('success', 'pending') LIMIT 1
            """,
            (item_id,),
        )
    )


async def update_fee_item(user: CurrentUser, item_id: str, payload: UpdateFeeItemRequest) -> FeeItemOut:
    item = await _get_item(user, item_id)
    updates = payload.model_dump(exclude_unset=True, exclude_none=True)
    if "amount" in updates and updates["amount"] != item["amount"]:
        if await _item_has_payments(item_id):
            raise AppError(
                status.HTTP_409_CONFLICT,
                "fee_has_payments",
                "Payments were already taken for this fee, so its amount can't change. Give a discount instead.",
            )
    async with db.pool.acquire() as conn:
        await conn.begin()
        async with conn.cursor() as cur:
            if updates:
                sets = ", ".join(f"{field} = %s" for field in updates)
                await cur.execute(f"UPDATE fee_items SET {sets} WHERE id = %s", (*updates.values(), item_id))
            if "amount" in updates:
                await cur.execute(
                    "UPDATE student_fees SET amount = %s, discount = LEAST(discount, %s) WHERE fee_item_id = %s",
                    (updates["amount"], updates["amount"], item_id),
                )
        await conn.commit()
    return next(i for i in await list_fee_items(user, class_id=item["class_id"]) if i.id == item_id)


async def delete_fee_item(user: CurrentUser, item_id: str) -> None:
    await _get_item(user, item_id)
    if await _item_has_payments(item_id):
        raise AppError(
            status.HTTP_409_CONFLICT, "fee_has_payments", "Payments were already taken for this fee, so it can't be deleted."
        )
    await execute("DELETE FROM fee_items WHERE id = %s", (item_id,))


async def sync_fee_item(user: CurrentUser, item_id: str) -> FeeItemOut:
    """Adds the fee to students who joined the class after it was created."""
    item = await _get_item(user, item_id)
    if item["applies_to"] == "selected":
        raise AppError(status.HTTP_409_CONFLICT, "fee_for_selected_students", "This fee is only for chosen students. Add students to it instead.")
    async with db.pool.acquire() as conn:
        await conn.begin()
        async with conn.cursor() as cur:
            await _assign_to_class(cur, user.school_id, item_id, item["class_id"], item["amount"])
        await conn.commit()
    return next(i for i in await list_fee_items(user, class_id=item["class_id"]) if i.id == item_id)


async def add_students(user: CurrentUser, item_id: str, student_ids: list[str]) -> FeeItemOut:
    """Bills more chosen students (of the fee's class) for a fee that is only for chosen students."""
    item = await _get_item(user, item_id)
    if item["applies_to"] != "selected":
        raise AppError(status.HTTP_409_CONFLICT, "fee_for_whole_class", "This fee is for the whole class; every student in it already has it.")
    students = await _active_students(user.school_id, student_ids)
    if any(s["class_id"] != item["class_id"] for s in students):
        raise AppError(status.HTTP_400_BAD_REQUEST, "wrong_class", "Choose students from this fee's class.")
    async with db.pool.acquire() as conn:
        await conn.begin()
        async with conn.cursor() as cur:
            await _bill_students(cur, user.school_id, item_id, [s["id"] for s in students], item["amount"])
        await conn.commit()
    return next(i for i in await list_fee_items(user, class_id=item["class_id"]) if i.id == item_id)


async def remove_student_fee(user: CurrentUser, student_fee_id: str) -> StudentFeeAccount:
    """Takes a fee off one student (e.g. stopped using the bus); only while nothing was paid on it."""
    fee = await get_student_fee(user.school_id, student_fee_id)
    taken = await fetch_one(
        "SELECT id FROM fee_payments WHERE student_fee_id = %s AND status IN ('success', 'pending') LIMIT 1", (student_fee_id,)
    )
    if taken:
        raise AppError(status.HTTP_409_CONFLICT, "fee_has_payments", "Money was already paid on this fee. Give a concession instead.")
    await execute("DELETE FROM student_fees WHERE id = %s", (student_fee_id,))
    return await student_account(user.school_id, fee["student_id"])


# --- Student accounts ---------------------------------------------------------


def _line_status(balance: Decimal, paid: Decimal, due: date, today: date) -> str:
    if balance <= 0:
        return "paid"
    if due < today:
        return "overdue"
    return "partial" if paid > 0 else "due"


def _payment_out(row: dict) -> PaymentOut:
    return PaymentOut(
        id=row["id"],
        amount=_money(row["amount"]),
        method=row["method"],
        reference=row["reference"],
        paid_on=row["paid_on"],
        status=row["status"],
        receipt_number=row["receipt_number"],
        notes=row["notes"],
        cancel_reason=row["cancel_reason"],
        received_by_name=row.get("received_by_name") or "",
    )


async def student_account(school_id: str, student_id: str) -> StudentFeeAccount:
    student = await fetch_one(
        """
        SELECT s.id, s.full_name, s.admission_number, c.name AS class_name, c.section
        FROM students s JOIN classes c ON c.id = s.class_id WHERE s.id = %s AND s.school_id = %s
        """,
        (student_id, school_id),
    )
    if student is None:
        raise _not_found("student")
    fees = await fetch_all(
        """
        SELECT sf.*, fi.name, fi.category, fi.term_label, fi.academic_year, fi.due_date
        FROM student_fees sf JOIN fee_items fi ON fi.id = sf.fee_item_id
        WHERE sf.student_id = %s ORDER BY fi.due_date, fi.name
        """,
        (student_id,),
    )
    payments = await fetch_all(
        """
        SELECT p.*, u.full_name AS received_by_name FROM fee_payments p LEFT JOIN users u ON u.id = p.received_by
        WHERE p.student_id = %s ORDER BY p.paid_on DESC, p.created_at DESC
        """,
        (student_id,),
    )
    by_fee = defaultdict(list)
    for payment in payments:
        by_fee[payment["student_fee_id"]].append(payment)

    today = alerts.today_ist()
    lines, total, paid_total, balance_total, overdue = [], ZERO, ZERO, ZERO, ZERO
    for fee in fees:
        payable = Decimal(fee["amount"]) - Decimal(fee["discount"])
        paid = sum((Decimal(p["amount"]) for p in by_fee[fee["id"]] if p["status"] == "success"), ZERO)
        balance = max(payable - paid, ZERO)
        line_status = _line_status(balance, paid, fee["due_date"], today)
        total, paid_total, balance_total = total + payable, paid_total + paid, balance_total + balance
        if line_status == "overdue":
            overdue += balance
        lines.append(
            StudentFeeLine(
                id=fee["id"],
                fee_item_id=fee["fee_item_id"],
                name=fee["name"],
                category=fee["category"],
                term_label=fee["term_label"],
                academic_year=fee["academic_year"],
                due_date=fee["due_date"],
                amount=_money(fee["amount"]),
                discount=_money(fee["discount"]),
                discount_note=fee["discount_note"],
                paid=_money(paid),
                balance=_money(balance),
                status=line_status,
                payments=[_payment_out(p) for p in by_fee[fee["id"]]],
            )
        )
    return StudentFeeAccount(
        student_id=student["id"],
        full_name=student["full_name"],
        admission_number=student["admission_number"],
        class_name=student["class_name"],
        section=student["section"],
        total=_money(total),
        paid=_money(paid_total),
        balance=_money(balance_total),
        overdue=_money(overdue),
        lines=lines,
    )


async def get_student_fee(school_id: str, student_fee_id: str) -> dict:
    row = await fetch_one(
        """
        SELECT sf.*, fi.due_date,
               (SELECT COALESCE(SUM(p.amount), 0) FROM fee_payments p WHERE p.student_fee_id = sf.id AND p.status = 'success') AS paid
        FROM student_fees sf JOIN fee_items fi ON fi.id = sf.fee_item_id
        WHERE sf.id = %s AND sf.school_id = %s
        """,
        (student_fee_id, school_id),
    )
    if row is None:
        raise _not_found("student fee")
    row["balance"] = max(Decimal(row["amount"]) - Decimal(row["discount"]) - Decimal(row["paid"]), ZERO)
    return row


async def set_discount(user: CurrentUser, student_fee_id: str, discount: Decimal, note: str) -> StudentFeeAccount:
    fee = await get_student_fee(user.school_id, student_fee_id)
    if discount > Decimal(fee["amount"]) - Decimal(fee["paid"]):
        raise AppError(
            status.HTTP_400_BAD_REQUEST, "discount_too_large", "The discount can't be more than what is still unpaid."
        )
    await execute(
        "UPDATE student_fees SET discount = %s, discount_note = %s WHERE id = %s", (discount, note, student_fee_id)
    )
    return await student_account(user.school_id, fee["student_id"])


# --- Payments and receipts ----------------------------------------------------


async def next_receipt_number(cur, school_id: str, year: int) -> str:
    # LAST_INSERT_ID(expr) makes the new counter value readable on this connection only,
    # so concurrent payments never get the same number.
    await cur.execute(
        """
        INSERT INTO fee_receipt_counters (school_id, last_number) VALUES (%s, LAST_INSERT_ID(1))
        ON DUPLICATE KEY UPDATE last_number = LAST_INSERT_ID(last_number + 1)
        """,
        (school_id,),
    )
    await cur.execute("SELECT LAST_INSERT_ID() AS n")
    number = (await cur.fetchone())["n"]
    return f"RCPT-{year}-{number:05d}"


async def record_payment(user: CurrentUser, payload: RecordPaymentRequest) -> PaymentOut:
    fee = await get_student_fee(user.school_id, payload.student_fee_id)
    if payload.amount > fee["balance"]:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            "amount_exceeds_balance",
            f"Only ₹{fee['balance']:.2f} is still due on this fee.",
        )
    paid_on = payload.paid_on or alerts.today_ist()
    payment_id = str(uuid.uuid4())
    async with db.pool.acquire() as conn:
        await conn.begin()
        async with conn.cursor() as cur:
            receipt = await next_receipt_number(cur, user.school_id, paid_on.year)
            await cur.execute(
                """
                INSERT INTO fee_payments (id, school_id, student_id, student_fee_id, amount, method, reference, paid_on,
                                          status, receipt_number, notes, received_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'success', %s, %s, %s)
                """,
                (payment_id, user.school_id, fee["student_id"], fee["id"], payload.amount, payload.method,
                 payload.reference, paid_on, receipt, payload.notes, user.id),
            )
        await conn.commit()
    return await get_payment(user.school_id, payment_id)


async def get_payment(school_id: str, payment_id: str) -> PaymentOut:
    row = await fetch_one(
        """
        SELECT p.*, u.full_name AS received_by_name FROM fee_payments p LEFT JOIN users u ON u.id = p.received_by
        WHERE p.id = %s AND p.school_id = %s
        """,
        (payment_id, school_id),
    )
    if row is None:
        raise _not_found("payment")
    return _payment_out(row)


async def cancel_payment(user: CurrentUser, payment_id: str, reason: str) -> PaymentOut:
    payment = await get_payment(user.school_id, payment_id)
    if payment.status != "success":
        raise AppError(status.HTTP_409_CONFLICT, "payment_not_cancellable", "Only a completed payment can be cancelled.")
    await execute(
        "UPDATE fee_payments SET status = 'cancelled', cancel_reason = %s WHERE id = %s", (reason, payment_id)
    )
    return await get_payment(user.school_id, payment_id)


async def receipt(school_id: str, payment_id: str) -> ReceiptOut:
    row = await fetch_one(
        """
        SELECT p.*, u.full_name AS received_by_name, s.full_name AS student_name, s.admission_number,
               c.name AS class_name, c.section, fi.name AS fee_name, fi.term_label, fi.academic_year,
               sc.name AS school_name, sc.code AS school_code, site.contact_address, site.contact_phone
        FROM fee_payments p
        JOIN students s ON s.id = p.student_id
        JOIN classes c ON c.id = s.class_id
        JOIN student_fees sf ON sf.id = p.student_fee_id
        JOIN fee_items fi ON fi.id = sf.fee_item_id
        JOIN schools sc ON sc.id = p.school_id
        LEFT JOIN school_sites site ON site.school_id = p.school_id
        LEFT JOIN users u ON u.id = p.received_by
        WHERE p.id = %s AND p.school_id = %s
        """,
        (payment_id, school_id),
    )
    if row is None or row["receipt_number"] is None:
        raise _not_found("receipt")
    fee = await get_student_fee(school_id, row["student_fee_id"])
    return ReceiptOut(
        receipt_number=row["receipt_number"],
        paid_on=row["paid_on"],
        school_name=row["school_name"],
        school_code=row["school_code"],
        school_address=row["contact_address"] or "",
        school_phone=row["contact_phone"] or "",
        student_name=row["student_name"],
        admission_number=row["admission_number"],
        class_name=row["class_name"],
        section=row["section"],
        fee_name=row["fee_name"],
        term_label=row["term_label"],
        academic_year=row["academic_year"],
        amount=_money(row["amount"]),
        method=row["method"],
        reference=row["reference"],
        received_by_name=row["received_by_name"] or ("Online payment" if row["method"] == "online" else ""),
        balance_after=_money(fee["balance"]),
        status=row["status"],
    )


# --- Reports and reminders ----------------------------------------------------


async def fee_report(user: CurrentUser, *, class_id: str | None, only_with_dues: bool) -> FeeReport:
    where, params = ["s.school_id = %s", "s.status = 'active'"], [user.school_id]
    if class_id:
        where.append("s.class_id = %s")
        params.append(class_id)
    rows = await fetch_all(
        f"""
        SELECT s.id, s.full_name, s.admission_number, c.name AS class_name, c.section, g.phone,
               sf.amount - sf.discount AS payable, fi.due_date,
               (SELECT COALESCE(SUM(p.amount), 0) FROM fee_payments p WHERE p.student_fee_id = sf.id AND p.status = 'success') AS paid
        FROM students s
        JOIN classes c ON c.id = s.class_id
        JOIN student_fees sf ON sf.student_id = s.id
        JOIN fee_items fi ON fi.id = sf.fee_item_id
        LEFT JOIN student_guardians g ON g.student_id = s.id AND g.relation = s.primary_contact
        WHERE {' AND '.join(where)}
        ORDER BY c.name, c.section, s.full_name
        """,
        tuple(params),
    )
    today = alerts.today_ist()
    students: dict[str, dict] = {}
    for r in rows:
        entry = students.setdefault(
            r["id"],
            {"row": r, "total": ZERO, "paid": ZERO, "balance": ZERO, "overdue": ZERO, "next_due": None},
        )
        payable, paid = Decimal(r["payable"]), Decimal(r["paid"])
        balance = max(payable - paid, ZERO)
        entry["total"] += payable
        entry["paid"] += paid
        entry["balance"] += balance
        if balance > 0:
            if r["due_date"] < today:
                entry["overdue"] += balance
            elif entry["next_due"] is None or r["due_date"] < entry["next_due"]:
                entry["next_due"] = r["due_date"]

    summaries = [
        StudentFeeSummary(
            student_id=student_id,
            full_name=e["row"]["full_name"],
            admission_number=e["row"]["admission_number"],
            class_name=e["row"]["class_name"],
            section=e["row"]["section"],
            total=_money(e["total"]),
            paid=_money(e["paid"]),
            balance=_money(e["balance"]),
            overdue=_money(e["overdue"]),
            next_due_date=e["next_due"],
            primary_contact_phone=e["row"]["phone"] or "",
        )
        for student_id, e in students.items()
        if not only_with_dues or e["balance"] > 0
    ]
    return FeeReport(
        total=_money(sum((e["total"] for e in students.values()), ZERO)),
        collected=_money(sum((e["paid"] for e in students.values()), ZERO)),
        balance=_money(sum((e["balance"] for e in students.values()), ZERO)),
        overdue=_money(sum((e["overdue"] for e in students.values()), ZERO)),
        students=summaries,
    )


async def send_reminders(user: CurrentUser, *, class_id: str | None, only_overdue: bool) -> ReminderResult:
    report = await fee_report(user, class_id=class_id, only_with_dues=True)
    targets = [s for s in report.students if (s.overdue > 0 if only_overdue else s.balance > 0)]
    today = alerts.today_ist()
    created = 0
    for summary in targets:
        amount = summary.overdue if only_overdue else summary.balance

        def build(ctx: dict, amount=amount, summary=summary):
            due = "overdue" if summary.overdue > 0 else f"due by {summary.next_due_date:%d %b %Y}" if summary.next_due_date else "due"
            variables = {
                "student": ctx["full_name"],
                "class": f"{ctx['class_name']} {ctx['section']}",
                "date": today.strftime("%d %b %Y"),
                "school": ctx["school_name"],
                "amount": f"{amount:.2f}",
                "due_date": f"{summary.next_due_date:%d %b %Y}" if summary.next_due_date else "",
            }
            text = f"Dear Parent, fee of Rs.{amount:,.2f} for {ctx['full_name']} is {due}. Please pay at the college office. - {ctx['school_name']}"
            return text, variables

        if await alerts.create_alert(
            student_id=summary.student_id,
            kind="fee",
            dedupe_key=f"fee:{summary.student_id}:{today.isoformat()}",
            build_message=build,
            created_by=user.id,
        ):
            created += 1
    return ReminderResult(students_with_dues=len(targets), alerts_created=created)
