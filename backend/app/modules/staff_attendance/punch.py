"""Teachers punch in and out from their own login; admins see who came, when.

A punch in also marks the day's staff attendance: present, or late when it is
after the school's start time plus grace minutes. Days are IST days.
"""

import uuid
from datetime import date, datetime, time, timedelta, timezone

from fastapi import status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser
from app.core.errors import AppError
from app.db.helpers import execute, fetch_all, fetch_one
from app.modules.alerts.service import IST, today_ist


class SchoolSettingsIn(BaseModel):
    day_starts_at: time
    late_grace_minutes: int = Field(ge=0, le=240)


class SchoolSettingsOut(BaseModel):
    day_starts_at: str  # "HH:MM"
    late_grace_minutes: int


class PunchOut(BaseModel):
    date: date
    punch_in_at: str | None
    punch_out_at: str | None
    is_late: bool
    worked_minutes: int | None


class MyPunches(BaseModel):
    today: PunchOut
    day_starts_at: str
    late_grace_minutes: int
    recent: list[PunchOut]


class StaffPunchRow(BaseModel):
    teacher_id: str
    full_name: str
    department: str
    punch: PunchOut | None
    on_leave: bool


def _utc_iso(value: datetime | None) -> str | None:
    return value.replace(tzinfo=timezone.utc).isoformat() if value else None


def _punch_out(row: dict | None, day: date) -> PunchOut:
    if row is None:
        return PunchOut(date=day, punch_in_at=None, punch_out_at=None, is_late=False, worked_minutes=None)
    worked = int((row["punch_out_at"] - row["punch_in_at"]).total_seconds() // 60) if row["punch_out_at"] else None
    return PunchOut(
        date=row["punch_date"],
        punch_in_at=_utc_iso(row["punch_in_at"]),
        punch_out_at=_utc_iso(row["punch_out_at"]),
        is_late=bool(row["is_late"]),
        worked_minutes=worked,
    )


def _td_to_time(value) -> time:
    # MySQL TIME columns come back as timedelta.
    if isinstance(value, timedelta):
        seconds = int(value.total_seconds())
        return time(seconds // 3600, (seconds % 3600) // 60)
    return value


async def get_settings(school_id: str) -> SchoolSettingsOut:
    row = await fetch_one("SELECT * FROM school_settings WHERE school_id = %s", (school_id,))
    start = _td_to_time(row["day_starts_at"]) if row else time(9, 0)
    grace = row["late_grace_minutes"] if row else 15
    return SchoolSettingsOut(day_starts_at=start.strftime("%H:%M"), late_grace_minutes=grace)


async def save_settings(school_id: str, payload: SchoolSettingsIn) -> SchoolSettingsOut:
    await execute(
        """
        INSERT INTO school_settings (school_id, day_starts_at, late_grace_minutes) VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE day_starts_at = VALUES(day_starts_at), late_grace_minutes = VALUES(late_grace_minutes)
        """,
        (school_id, payload.day_starts_at.strftime("%H:%M:%S"), payload.late_grace_minutes),
    )
    return await get_settings(school_id)


async def _my_teacher_id(user: CurrentUser) -> str:
    row = await fetch_one("SELECT id FROM teachers WHERE user_id = %s AND school_id = %s", (user.id, user.school_id))
    if row is None:
        raise AppError(status.HTTP_403_FORBIDDEN, "not_staff", "Only teaching staff punch in and out.")
    return row["id"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def punch_in(user: CurrentUser) -> PunchOut:
    teacher_id = await _my_teacher_id(user)
    now = _now()
    day = now.astimezone(IST).date()
    if await fetch_one("SELECT id FROM staff_punches WHERE teacher_id = %s AND punch_date = %s", (teacher_id, day)):
        raise AppError(status.HTTP_409_CONFLICT, "already_punched_in", "You already punched in today.")

    settings = await get_settings(user.school_id)
    start = datetime.combine(day, time.fromisoformat(settings.day_starts_at), tzinfo=IST)
    is_late = now.astimezone(IST) > start + timedelta(minutes=settings.late_grace_minutes)
    await execute(
        "INSERT INTO staff_punches (id, school_id, teacher_id, punch_date, punch_in_at, is_late) VALUES (%s, %s, %s, %s, %s, %s)",
        (str(uuid.uuid4()), user.school_id, teacher_id, day, now.replace(tzinfo=None), is_late),
    )
    await execute(
        """
        INSERT INTO staff_attendance (id, school_id, teacher_id, attendance_date, status, marked_by)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE status = VALUES(status), marked_by = VALUES(marked_by), marked_at = CURRENT_TIMESTAMP
        """,
        (str(uuid.uuid4()), user.school_id, teacher_id, day, "late" if is_late else "present", user.id),
    )
    return _punch_out(await fetch_one("SELECT * FROM staff_punches WHERE teacher_id = %s AND punch_date = %s", (teacher_id, day)), day)


async def punch_out(user: CurrentUser) -> PunchOut:
    teacher_id = await _my_teacher_id(user)
    now = _now()
    day = now.astimezone(IST).date()
    row = await fetch_one("SELECT * FROM staff_punches WHERE teacher_id = %s AND punch_date = %s", (teacher_id, day))
    if row is None:
        raise AppError(status.HTTP_409_CONFLICT, "not_punched_in", "Punch in first.")
    if row["punch_out_at"]:
        raise AppError(status.HTTP_409_CONFLICT, "already_punched_out", "You already punched out today.")
    await execute("UPDATE staff_punches SET punch_out_at = %s WHERE id = %s", (now.replace(tzinfo=None), row["id"]))
    return _punch_out(await fetch_one("SELECT * FROM staff_punches WHERE id = %s", (row["id"],)), day)


async def my_punches(user: CurrentUser) -> MyPunches:
    teacher_id = await _my_teacher_id(user)
    day = today_ist()
    rows = await fetch_all(
        "SELECT * FROM staff_punches WHERE teacher_id = %s AND punch_date >= %s ORDER BY punch_date DESC",
        (teacher_id, day - timedelta(days=30)),
    )
    today_row = next((r for r in rows if r["punch_date"] == day), None)
    settings = await get_settings(user.school_id)
    return MyPunches(
        today=_punch_out(today_row, day),
        day_starts_at=settings.day_starts_at,
        late_grace_minutes=settings.late_grace_minutes,
        recent=[_punch_out(r, r["punch_date"]) for r in rows if r["punch_date"] != day],
    )


async def punches_for_day(user: CurrentUser, day: date) -> list[StaffPunchRow]:
    teachers = await fetch_all(
        """
        SELECT t.id, t.department, u.full_name FROM teachers t JOIN users u ON u.id = t.user_id
        WHERE t.school_id = %s AND u.status = 'active' ORDER BY u.full_name
        """,
        (user.school_id,),
    )
    punches = {r["teacher_id"]: r for r in await fetch_all(
        "SELECT * FROM staff_punches WHERE school_id = %s AND punch_date = %s", (user.school_id, day)
    )}
    on_leave = {r["teacher_id"] for r in await fetch_all(
        """
        SELECT teacher_id FROM leave_requests
        WHERE school_id = %s AND teacher_id IS NOT NULL AND status = 'approved' AND %s BETWEEN from_date AND to_date
        """,
        (user.school_id, day),
    )}
    return [
        StaffPunchRow(
            teacher_id=t["id"],
            full_name=t["full_name"],
            department=t["department"],
            punch=_punch_out(punches[t["id"]], day) if t["id"] in punches else None,
            on_leave=t["id"] in on_leave,
        )
        for t in teachers
    ]
