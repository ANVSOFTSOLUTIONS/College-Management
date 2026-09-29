"""The school's holiday and event calendar.

Holidays matter elsewhere: the dashboard skips them in the attendance trend
and doesn't chase classes for attendance on a holiday.
"""

import uuid
from datetime import date, timedelta
from typing import Literal

from fastapi import status
from pydantic import BaseModel, Field, field_validator, model_validator

from app.api.deps import CurrentUser
from app.core.errors import AppError
from app.db.helpers import execute, fetch_all, fetch_one
from app.modules.board import audience
from app.modules.notifications import service as notifications

MAX_RANGE_DAYS = 400
MAX_EVENT_DAYS = 60


class HolidayIn(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    kind: Literal["holiday", "event"] = "holiday"
    start_date: date
    end_date: date | None = None  # defaults to a single day
    notes: str = Field(default="", max_length=300)
    notify: bool = True  # bell notification to staff, students and parents

    @field_validator("title", "notes", mode="before")
    @classmethod
    def _strip(cls, value):
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def _dates(self):
        self.end_date = self.end_date or self.start_date
        if self.end_date < self.start_date:
            raise ValueError("It can't end before it starts.")
        if (self.end_date - self.start_date).days + 1 > MAX_EVENT_DAYS:
            raise ValueError(f"One entry can cover at most {MAX_EVENT_DAYS} days.")
        return self


class HolidayOut(BaseModel):
    id: str
    title: str
    kind: str
    start_date: date
    end_date: date
    days: int
    notes: str


def _out(r: dict) -> HolidayOut:
    return HolidayOut(
        id=r["id"], title=r["title"], kind=r["kind"], start_date=r["start_date"], end_date=r["end_date"],
        days=(r["end_date"] - r["start_date"]).days + 1, notes=r["notes"],
    )


async def _school_ids(user: CurrentUser) -> list[str]:
    if user.role in ("parent", "student"):
        return sorted({k["school_id"] for k in await audience.children(user)})
    return [user.school_id] if user.school_id else []


async def list_holidays(user: CurrentUser, start: date, end: date) -> list[HolidayOut]:
    if end < start or (end - start).days > MAX_RANGE_DAYS:
        raise AppError(status.HTTP_400_BAD_REQUEST, "invalid_range", f"Choose a range of at most {MAX_RANGE_DAYS} days.")
    school_ids = await _school_ids(user)
    if not school_ids:
        return []
    placeholders = ", ".join(["%s"] * len(school_ids))
    rows = await fetch_all(
        f"""
        SELECT * FROM school_holidays WHERE school_id IN ({placeholders}) AND start_date <= %s AND end_date >= %s
        ORDER BY start_date, title
        """,
        (*school_ids, end, start),
    )
    return [_out(r) for r in rows]


async def holiday_on(school_id: str, day: date) -> str | None:
    """The holiday's title if the school is closed that day."""
    row = await fetch_one(
        "SELECT title FROM school_holidays WHERE school_id = %s AND kind = 'holiday' AND %s BETWEEN start_date AND end_date LIMIT 1",
        (school_id, day),
    )
    return row["title"] if row else None


async def holidays_between(school_id: str, start: date, end: date) -> set[date]:
    rows = await fetch_all(
        "SELECT start_date, end_date FROM school_holidays WHERE school_id = %s AND kind = 'holiday' AND start_date <= %s AND end_date >= %s",
        (school_id, end, start),
    )
    days = set()
    for r in rows:
        day = max(r["start_date"], start)
        while day <= min(r["end_date"], end):
            days.add(day)
            day += timedelta(days=1)
    return days


def _when(payload: HolidayIn) -> str:
    if payload.start_date == payload.end_date:
        return f"{payload.start_date:%a %d %b}"
    return f"{payload.start_date:%d %b} to {payload.end_date:%d %b}"


async def create_holiday(user: CurrentUser, payload: HolidayIn) -> HolidayOut:
    holiday_id = str(uuid.uuid4())
    await execute(
        """
        INSERT INTO school_holidays (id, school_id, title, kind, start_date, end_date, notes, created_by)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (holiday_id, user.school_id, payload.title, payload.kind, payload.start_date, payload.end_date, payload.notes, user.id),
    )
    if payload.notify:
        recipients = await audience.recipients(user.school_id, [], staff=True, parents=True, students=True)
        label = "Holiday" if payload.kind == "holiday" else "Event"
        await notifications.notify(
            [r for r in recipients if r != user.id],
            school_id=user.school_id,
            title=f"{label}: {payload.title}",
            body=_when(payload) + (f". {payload.notes}" if payload.notes else ""),
            link="calendar",
        )
    return await _get(user, holiday_id)


async def _get(user: CurrentUser, holiday_id: str) -> HolidayOut:
    row = await fetch_one("SELECT * FROM school_holidays WHERE id = %s AND school_id = %s", (holiday_id, user.school_id))
    if row is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "holiday_not_found", "Calendar entry not found.")
    return _out(row)


async def update_holiday(user: CurrentUser, holiday_id: str, payload: HolidayIn) -> HolidayOut:
    await _get(user, holiday_id)
    await execute(
        "UPDATE school_holidays SET title = %s, kind = %s, start_date = %s, end_date = %s, notes = %s WHERE id = %s",
        (payload.title, payload.kind, payload.start_date, payload.end_date, payload.notes, holiday_id),
    )
    return await _get(user, holiday_id)


async def delete_holiday(user: CurrentUser, holiday_id: str) -> None:
    await _get(user, holiday_id)
    await execute("DELETE FROM school_holidays WHERE id = %s", (holiday_id,))
