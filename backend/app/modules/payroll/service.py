"""Staff salaries and monthly payslips.

The admin sets each teacher's salary once. "Generate" builds that month's
draft payslips from staff attendance and the holiday calendar:

- working days: Monday–Saturday, minus holidays
- present or late, and approved leave, are paid
- days marked absent are loss of pay (LOP), at gross / working days per day
- working days with nothing marked are shown so the admin can check them

The admin can adjust LOP days on a draft, then marks it paid; the teacher is
notified and can see and print it. Paid payslips never change (revert to
draft first to correct one).
"""

import uuid
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from fastapi import status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser
from app.core.errors import AppError
from app.core.words import rupees_in_words
from app.db.helpers import execute, fetch_all, fetch_one
from app.modules.alerts.service import today_ist
from app.modules.board import audience
from app.modules.notifications import service as notifications
from app.modules.timetable import calendar

PaymentMode = Literal["bank", "cash", "upi", "cheque"]
PAYMENT_LABELS = {"bank": "Bank transfer", "cash": "Cash", "upi": "UPI", "cheque": "Cheque"}
_PAISE = Decimal("0.01")


def _money(value) -> Decimal:
    return Decimal(value).quantize(_PAISE, rounding=ROUND_HALF_UP)


class SalaryIn(BaseModel):
    basic: Decimal = Field(ge=0, le=10_000_000, decimal_places=2)
    allowances: Decimal = Field(default=Decimal(0), ge=0, le=10_000_000, decimal_places=2)
    deductions: Decimal = Field(default=Decimal(0), ge=0, le=10_000_000, decimal_places=2)


class SalaryOut(BaseModel):
    teacher_id: str
    full_name: str
    department: str
    basic: float | None  # None: salary not set yet
    allowances: float | None
    deductions: float | None
    gross: float | None


class SlipAdjustIn(BaseModel):
    lop_days: Decimal = Field(ge=0, le=31, decimal_places=1)
    note: str = Field(default="", max_length=200)


class PayIn(BaseModel):
    paid_on: date | None = None
    payment_mode: PaymentMode = "bank"
    note: str = Field(default="", max_length=200)


class SlipOut(BaseModel):
    id: str
    teacher_id: str
    full_name: str
    department: str
    employee_code: str
    month: str  # "2026-09"
    working_days: int
    days_present: int
    days_leave: int
    days_absent: int
    days_unmarked: int
    lop_days: float
    basic: float
    allowances: float
    gross: float
    lop_amount: float
    deductions: float
    net: float
    net_in_words: str
    status: str
    paid_on: date | None
    payment_mode: str
    payment_mode_label: str
    note: str
    school: dict | None = None  # filled for a single payslip (printing)


class PayrollMonth(BaseModel):
    month: str
    slips: list[SlipOut]
    without_salary: list[str]  # active teachers with no salary set
    total_net: float
    total_paid: float


def _first_of_month(value: date) -> date:
    return value.replace(day=1)


def _last_of_month(first: date) -> date:
    return (first + timedelta(days=32)).replace(day=1) - timedelta(days=1)


# --- Salaries ------------------------------------------------------------------------


async def list_salaries(user: CurrentUser) -> list[SalaryOut]:
    rows = await fetch_all(
        """
        SELECT t.id, u.full_name, t.department, ts.basic, ts.allowances, ts.deductions
        FROM teachers t JOIN users u ON u.id = t.user_id
        LEFT JOIN teacher_salaries ts ON ts.teacher_id = t.id
        WHERE t.school_id = %s AND u.status = 'active' ORDER BY u.full_name
        """,
        (user.school_id,),
    )
    return [
        SalaryOut(
            teacher_id=r["id"], full_name=r["full_name"], department=r["department"],
            basic=float(r["basic"]) if r["basic"] is not None else None,
            allowances=float(r["allowances"]) if r["allowances"] is not None else None,
            deductions=float(r["deductions"]) if r["deductions"] is not None else None,
            gross=float(r["basic"] + r["allowances"]) if r["basic"] is not None else None,
        )
        for r in rows
    ]


async def save_salary(user: CurrentUser, teacher_id: str, payload: SalaryIn) -> SalaryOut:
    teacher = await fetch_one("SELECT id FROM teachers WHERE id = %s AND school_id = %s", (teacher_id, user.school_id))
    if teacher is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "teacher_not_found", "Teacher not found.")
    if payload.deductions > payload.basic + payload.allowances:
        raise AppError(status.HTTP_400_BAD_REQUEST, "deductions_too_high", "Deductions can't be more than the salary.")
    await execute(
        """
        INSERT INTO teacher_salaries (teacher_id, school_id, basic, allowances, deductions) VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE basic = VALUES(basic), allowances = VALUES(allowances), deductions = VALUES(deductions)
        """,
        (teacher_id, user.school_id, payload.basic, payload.allowances, payload.deductions),
    )
    return next(s for s in await list_salaries(user) if s.teacher_id == teacher_id)


# --- Payslips --------------------------------------------------------------------------


def _amounts(basic: Decimal, allowances: Decimal, deductions: Decimal, working_days: int, lop_days: Decimal) -> dict:
    gross = _money(basic + allowances)
    lop_amount = _money(gross * lop_days / working_days) if working_days else Decimal(0)
    lop_amount = min(lop_amount, gross)
    net = max(gross - lop_amount - _money(deductions), Decimal(0))
    return {"gross": gross, "lop_amount": lop_amount, "net": _money(net)}


async def _month_days(school_id: str, first: date) -> list[date]:
    """Monday–Saturday of the whole month, minus holidays. (Days not reached yet just show as not marked.)"""
    last = _last_of_month(first)
    holidays = await calendar.holidays_between(school_id, first, last)
    days, day = [], first
    while day <= last:
        if day.weekday() != 6 and day not in holidays:
            days.append(day)
        day += timedelta(days=1)
    return days


_SLIP_SELECT = """
    SELECT ss.*, u.full_name, t.department, t.employee_code
    FROM salary_slips ss JOIN teachers t ON t.id = ss.teacher_id JOIN users u ON u.id = t.user_id
"""


def _slip_out(r: dict, school: dict | None = None) -> SlipOut:
    return SlipOut(
        id=r["id"], teacher_id=r["teacher_id"], full_name=r["full_name"], department=r["department"],
        employee_code=r["employee_code"] or "", month=f"{r['month']:%Y-%m}", working_days=r["working_days"],
        days_present=r["days_present"], days_leave=r["days_leave"], days_absent=r["days_absent"], days_unmarked=r["days_unmarked"],
        lop_days=float(r["lop_days"]), basic=float(r["basic"]), allowances=float(r["allowances"]), gross=float(r["gross"]),
        lop_amount=float(r["lop_amount"]), deductions=float(r["deductions"]), net=float(r["net"]), net_in_words=rupees_in_words(r["net"]),
        status=r["status"], paid_on=r["paid_on"], payment_mode=r["payment_mode"], payment_mode_label=PAYMENT_LABELS.get(r["payment_mode"], ""),
        note=r["note"], school=school,
    )


async def generate(user: CurrentUser, month: date) -> PayrollMonth:
    """Creates or refreshes draft payslips for every teacher with a salary. Paid ones are left alone."""
    first = _first_of_month(month)
    if first > _first_of_month(today_ist()):
        raise AppError(status.HTTP_400_BAD_REQUEST, "future_month", "Payslips can't be made for a future month.")
    days = await _month_days(user.school_id, first)
    teachers = await fetch_all(
        """
        SELECT t.id, ts.basic, ts.allowances, ts.deductions FROM teachers t
        JOIN users u ON u.id = t.user_id JOIN teacher_salaries ts ON ts.teacher_id = t.id
        WHERE t.school_id = %s AND u.status = 'active'
        """,
        (user.school_id,),
    )
    existing = {
        r["teacher_id"]: r
        for r in await fetch_all("SELECT id, teacher_id, status FROM salary_slips WHERE school_id = %s AND month = %s", (user.school_id, first))
    }
    marks = {}
    if days:
        for r in await fetch_all(
            "SELECT teacher_id, attendance_date, status FROM staff_attendance WHERE school_id = %s AND attendance_date BETWEEN %s AND %s",
            (user.school_id, days[0], days[-1]),
        ):
            marks[(r["teacher_id"], r["attendance_date"])] = r["status"]

    working = set(days)
    for t in teachers:
        slip = existing.get(t["id"])
        if slip and slip["status"] == "paid":
            continue
        statuses = [marks.get((t["id"], d)) for d in days]
        present = sum(1 for s in statuses if s in ("present", "late"))
        leave = sum(1 for s in statuses if s == "leave")
        absent = sum(1 for s in statuses if s == "absent")
        unmarked = sum(1 for s in statuses if s is None)
        lop = Decimal(absent)
        amounts = _amounts(t["basic"], t["allowances"], t["deductions"], len(working), lop)
        values = (len(working), present, leave, absent, unmarked, lop, t["basic"], t["allowances"], amounts["gross"], amounts["lop_amount"], t["deductions"], amounts["net"])
        if slip:
            await execute(
                """
                UPDATE salary_slips SET working_days = %s, days_present = %s, days_leave = %s, days_absent = %s, days_unmarked = %s,
                       lop_days = %s, basic = %s, allowances = %s, gross = %s, lop_amount = %s, deductions = %s, net = %s
                WHERE id = %s
                """,
                (*values, slip["id"]),
            )
        else:
            await execute(
                """
                INSERT INTO salary_slips (id, school_id, teacher_id, month, working_days, days_present, days_leave, days_absent, days_unmarked,
                                          lop_days, basic, allowances, gross, lop_amount, deductions, net)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (str(uuid.uuid4()), user.school_id, t["id"], first, *values),
            )
    return await month_payroll(user, first)


async def month_payroll(user: CurrentUser, month: date) -> PayrollMonth:
    first = _first_of_month(month)
    rows = await fetch_all(f"{_SLIP_SELECT} WHERE ss.school_id = %s AND ss.month = %s ORDER BY u.full_name", (user.school_id, first))
    slips = [_slip_out(r) for r in rows]
    missing = await fetch_all(
        """
        SELECT u.full_name FROM teachers t JOIN users u ON u.id = t.user_id
        LEFT JOIN teacher_salaries ts ON ts.teacher_id = t.id
        WHERE t.school_id = %s AND u.status = 'active' AND ts.teacher_id IS NULL ORDER BY u.full_name
        """,
        (user.school_id,),
    )
    return PayrollMonth(
        month=f"{first:%Y-%m}",
        slips=slips,
        without_salary=[r["full_name"] for r in missing],
        total_net=round(sum(s.net for s in slips), 2),
        total_paid=round(sum(s.net for s in slips if s.status == "paid"), 2),
    )


async def _slip_row(user: CurrentUser, slip_id: str) -> dict:
    row = await fetch_one(f"{_SLIP_SELECT} WHERE ss.id = %s AND ss.school_id = %s", (slip_id, user.school_id))
    if row is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "payslip_not_found", "Payslip not found.")
    if user.role != "admin":
        # Teachers see only their own paid payslips.
        if row["teacher_id"] != await audience.teacher_id(user) or row["status"] != "paid":
            raise AppError(status.HTTP_404_NOT_FOUND, "payslip_not_found", "Payslip not found.")
    return row


async def _school(school_id: str) -> dict:
    row = await fetch_one(
        "SELECT s.name, ss.logo_url, ss.contact_address, ss.contact_phone FROM schools s LEFT JOIN school_sites ss ON ss.school_id = s.id WHERE s.id = %s",
        (school_id,),
    )
    return {"name": row["name"], "logo_url": row["logo_url"], "address": row["contact_address"] or "", "phone": row["contact_phone"] or ""}


async def get_slip(user: CurrentUser, slip_id: str) -> SlipOut:
    return _slip_out(await _slip_row(user, slip_id), await _school(user.school_id))


async def adjust(user: CurrentUser, slip_id: str, payload: SlipAdjustIn) -> SlipOut:
    row = await _slip_row(user, slip_id)
    if row["status"] != "draft":
        raise AppError(status.HTTP_409_CONFLICT, "payslip_paid", "This payslip is paid. Revert it to draft to change it.")
    if payload.lop_days > row["working_days"]:
        raise AppError(status.HTTP_400_BAD_REQUEST, "too_many_lop_days", "Loss-of-pay days can't be more than the working days.")
    amounts = _amounts(row["basic"], row["allowances"], row["deductions"], row["working_days"], payload.lop_days)
    await execute(
        "UPDATE salary_slips SET lop_days = %s, lop_amount = %s, net = %s, note = %s WHERE id = %s",
        (payload.lop_days, amounts["lop_amount"], amounts["net"], payload.note.strip(), slip_id),
    )
    return await get_slip(user, slip_id)


async def pay(user: CurrentUser, slip_id: str, payload: PayIn) -> SlipOut:
    row = await _slip_row(user, slip_id)
    if row["status"] == "paid":
        raise AppError(status.HTTP_409_CONFLICT, "already_paid", "This payslip is already marked paid.")
    paid_on = payload.paid_on or today_ist()
    if paid_on > today_ist():
        raise AppError(status.HTTP_400_BAD_REQUEST, "invalid_date", "The payment date can't be in the future.")
    await execute(
        "UPDATE salary_slips SET status = 'paid', paid_on = %s, payment_mode = %s, note = %s WHERE id = %s",
        (paid_on, payload.payment_mode, payload.note.strip() or row["note"], slip_id),
    )
    teacher = await fetch_one("SELECT user_id FROM teachers WHERE id = %s", (row["teacher_id"],))
    await notifications.notify(
        [teacher["user_id"]],
        school_id=user.school_id,
        title=f"Salary for {row['month']:%B %Y} paid",
        body=f"Net pay ₹{_money(row['net']):,} by {PAYMENT_LABELS[payload.payment_mode].lower()}. Your payslip is under My payslips.",
        link="my-payslips",
    )
    return await get_slip(user, slip_id)


async def revert(user: CurrentUser, slip_id: str) -> SlipOut:
    row = await _slip_row(user, slip_id)
    if row["status"] != "paid":
        raise AppError(status.HTTP_409_CONFLICT, "not_paid", "Only a paid payslip can be reverted.")
    await execute("UPDATE salary_slips SET status = 'draft', paid_on = NULL, payment_mode = '' WHERE id = %s", (slip_id,))
    return await get_slip(user, slip_id)


async def my_slips(user: CurrentUser) -> list[SlipOut]:
    teacher_id = await audience.teacher_id(user)
    if teacher_id is None:
        return []
    rows = await fetch_all(f"{_SLIP_SELECT} WHERE ss.teacher_id = %s AND ss.status = 'paid' ORDER BY ss.month DESC", (teacher_id,))
    return [_slip_out(r) for r in rows]
