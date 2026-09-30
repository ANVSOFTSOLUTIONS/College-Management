"""The platform owner's view: how many schools, how many students, and what the
platform has earned. Schools pay the platform outside the app (bank, UPI,
cash); the super admin records each payment here.
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal

from fastapi import status
from pydantic import BaseModel, Field, field_validator

from app.api.deps import CurrentUser
from app.core.errors import AppError
from app.db.helpers import execute, fetch_all, fetch_one
from app.modules.alerts.service import today_ist

Purpose = Literal["subscription", "pro_templates", "setup", "other"]
PURPOSE_LABELS = {"subscription": "Monthly subscription", "pro_templates": "Pro templates", "setup": "Setup", "other": "Other"}
Method = Literal["bank", "upi", "cash", "cheque"]
MONTHS = 12


class RecordPaymentIn(BaseModel):
    school_id: str
    amount: Decimal = Field(gt=0, le=10_000_000, decimal_places=2)
    paid_on: date
    purpose: Purpose = "subscription"
    method: Method = "bank"
    note: str = Field(default="", max_length=200)

    @field_validator("note", mode="before")
    @classmethod
    def _strip(cls, value):
        return value.strip() if isinstance(value, str) else value


class PlatformPaymentOut(BaseModel):
    id: str
    school_id: str
    school_name: str
    amount: float
    paid_on: date
    purpose: str
    purpose_label: str
    method: str
    note: str


class MonthAmount(BaseModel):
    month: str  # "2026-09"
    amount: float
    new_schools: int


class SchoolStats(BaseModel):
    school_id: str
    name: str
    code: str
    billing_status: str
    status: str
    pro_templates: bool
    monthly_fee: float
    students: int
    teachers: int
    paid_total: float
    last_paid_on: date | None
    joined_on: date


class Analytics(BaseModel):
    schools_total: int
    schools_active: int  # billing active
    schools_trial: int
    schools_suspended: int
    schools_inactive: int  # switched off entirely
    pro_schools: int
    students_total: int
    teachers_total: int
    monthly_recurring: float  # sum of monthly fees of paying, active schools
    earned_total: float
    earned_this_month: float
    earned_this_year: float
    by_month: list[MonthAmount]  # last 12 months, oldest first
    by_purpose: dict[str, float]
    schools: list[SchoolStats]


def _month_starts(today: date, count: int) -> list[date]:
    first, months = today.replace(day=1), []
    for _ in range(count):
        months.append(first)
        first = (first - timedelta(days=1)).replace(day=1)
    return list(reversed(months))


async def analytics() -> Analytics:
    today = today_ist()
    schools = await fetch_all("SELECT * FROM schools ORDER BY name")
    students = {r["school_id"]: r["n"] for r in await fetch_all("SELECT school_id, COUNT(*) AS n FROM students WHERE status = 'active' GROUP BY school_id")}
    teachers = {
        r["school_id"]: r["n"]
        for r in await fetch_all(
            "SELECT t.school_id, COUNT(*) AS n FROM teachers t JOIN users u ON u.id = t.user_id WHERE u.status = 'active' GROUP BY t.school_id"
        )
    }
    paid = {
        r["school_id"]: r
        for r in await fetch_all("SELECT school_id, SUM(amount) AS total, MAX(paid_on) AS last_paid FROM platform_payments GROUP BY school_id")
    }
    months = _month_starts(today, MONTHS)
    by_month = {m: Decimal(0) for m in months}
    for r in await fetch_all(
        "SELECT DATE_FORMAT(paid_on, '%%Y-%%m-01') AS m, SUM(amount) AS total FROM platform_payments WHERE paid_on >= %s GROUP BY m",
        (months[0],),
    ):
        by_month[date.fromisoformat(r["m"])] = Decimal(r["total"])
    joined = {m: 0 for m in months}
    for s in schools:
        start = s["created_at"].date().replace(day=1)
        if start in joined:
            joined[start] += 1
    by_purpose = {
        r["purpose"]: float(r["total"]) for r in await fetch_all("SELECT purpose, SUM(amount) AS total FROM platform_payments GROUP BY purpose")
    }
    earned_year = await fetch_one("SELECT COALESCE(SUM(amount), 0) AS total FROM platform_payments WHERE paid_on >= %s", (today.replace(month=1, day=1),))

    live = [s for s in schools if s["status"] == "active"]
    return Analytics(
        schools_total=len(schools),
        schools_active=sum(1 for s in live if s["billing_status"] == "active"),
        schools_trial=sum(1 for s in live if s["billing_status"] == "trial"),
        schools_suspended=sum(1 for s in live if s["billing_status"] == "suspended"),
        schools_inactive=len(schools) - len(live),
        pro_schools=sum(1 for s in schools if s["pro_templates"]),
        students_total=sum(students.values()),
        teachers_total=sum(teachers.values()),
        monthly_recurring=float(sum(Decimal(s["monthly_fee"]) for s in live if s["billing_status"] == "active")),
        earned_total=float(sum(Decimal(p["total"]) for p in paid.values())),
        earned_this_month=float(by_month[months[-1]]),
        earned_this_year=float(earned_year["total"]),
        by_month=[MonthAmount(month=f"{m:%Y-%m}", amount=float(by_month[m]), new_schools=joined[m]) for m in months],
        by_purpose={p: by_purpose.get(p, 0.0) for p in PURPOSE_LABELS},
        schools=[
            SchoolStats(
                school_id=s["id"], name=s["name"], code=s["code"], billing_status=s["billing_status"], status=s["status"],
                pro_templates=bool(s["pro_templates"]), monthly_fee=float(s["monthly_fee"]), students=students.get(s["id"], 0),
                teachers=teachers.get(s["id"], 0), paid_total=float(paid[s["id"]]["total"]) if s["id"] in paid else 0.0,
                last_paid_on=paid[s["id"]]["last_paid"] if s["id"] in paid else None, joined_on=s["created_at"].date(),
            )
            for s in schools
        ],
    )


def _payment_out(r: dict) -> PlatformPaymentOut:
    return PlatformPaymentOut(
        id=r["id"], school_id=r["school_id"], school_name=r["school_name"], amount=float(r["amount"]), paid_on=r["paid_on"],
        purpose=r["purpose"], purpose_label=PURPOSE_LABELS[r["purpose"]], method=r["method"], note=r["note"],
    )


_SELECT = "SELECT p.*, s.name AS school_name FROM platform_payments p JOIN schools s ON s.id = p.school_id"


async def list_payments(school_id: str | None = None) -> list[PlatformPaymentOut]:
    where, params = ("WHERE p.school_id = %s", (school_id,)) if school_id else ("", ())
    rows = await fetch_all(f"{_SELECT} {where} ORDER BY p.paid_on DESC, p.created_at DESC LIMIT 500", params)
    return [_payment_out(r) for r in rows]


async def record_payment(user: CurrentUser, payload: RecordPaymentIn) -> PlatformPaymentOut:
    if payload.paid_on > today_ist():
        raise AppError(status.HTTP_400_BAD_REQUEST, "invalid_date", "The payment date can't be in the future.")
    if await fetch_one("SELECT id FROM schools WHERE id = %s", (payload.school_id,)) is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "school_not_found", "School not found.")
    payment_id = str(uuid.uuid4())
    await execute(
        "INSERT INTO platform_payments (id, school_id, amount, paid_on, purpose, method, note, recorded_by) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (payment_id, payload.school_id, payload.amount, payload.paid_on, payload.purpose, payload.method, payload.note, user.id),
    )
    return _payment_out(await fetch_one(f"{_SELECT} WHERE p.id = %s", (payment_id,)))


async def delete_payment(payment_id: str) -> None:
    if await fetch_one("SELECT id FROM platform_payments WHERE id = %s", (payment_id,)) is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "payment_not_found", "Payment not found.")
    await execute("DELETE FROM platform_payments WHERE id = %s", (payment_id,))
