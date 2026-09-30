"""Timetable.

The admin sets the school's periods (bell schedule) once, then fills a weekly
Monday–Saturday grid per class with that class's subjects. A cell's teacher
is the class's subject teacher, so a teacher can't be put in two classes in
the same period: saving a grid that would do that is refused.
"""

import uuid
from datetime import time

from fastapi import status
from pydantic import BaseModel, Field, field_validator, model_validator

from app.api.deps import CurrentUser
from app.core.errors import AppError
from app.db.database import db
from app.db.helpers import fetch_all, fetch_one
from app.modules.board import audience

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
MAX_PERIODS = 15


class PeriodIn(BaseModel):
    id: str | None = None  # keep an existing period (and its timetable cells)
    label: str = Field(min_length=1, max_length=30)
    start_time: time
    end_time: time
    is_break: bool = False

    @field_validator("label", mode="before")
    @classmethod
    def _strip(cls, value):
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def _order(self):
        if self.end_time <= self.start_time:
            raise ValueError(f"{self.label} must end after it starts.")
        return self


class PeriodsIn(BaseModel):
    periods: list[PeriodIn] = Field(max_length=MAX_PERIODS)


class PeriodOut(BaseModel):
    id: str
    label: str
    start_time: str  # "09:00"
    end_time: str
    is_break: bool


class CellIn(BaseModel):
    weekday: int = Field(ge=0, le=5)
    period_id: str
    subject_id: str


class ClassGridIn(BaseModel):
    cells: list[CellIn] = Field(max_length=6 * MAX_PERIODS)


class CellOut(BaseModel):
    weekday: int
    period_id: str
    subject_id: str
    subject_name: str
    teacher_name: str | None
    class_id: str
    class_label: str  # "Grade 5 - A"


class TimetableOut(BaseModel):
    title: str
    periods: list[PeriodOut]
    cells: list[CellOut]


def _hhmm(value) -> str:
    # MySQL TIME columns arrive as timedelta.
    seconds = int(value.total_seconds()) if hasattr(value, "total_seconds") else value.hour * 3600 + value.minute * 60
    return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}"


async def list_periods(school_id: str) -> list[PeriodOut]:
    rows = await fetch_all("SELECT * FROM school_periods WHERE school_id = %s ORDER BY position", (school_id,))
    return [PeriodOut(id=r["id"], label=r["label"], start_time=_hhmm(r["start_time"]), end_time=_hhmm(r["end_time"]), is_break=bool(r["is_break"])) for r in rows]


async def save_periods(user: CurrentUser, payload: PeriodsIn) -> list[PeriodOut]:
    periods = sorted(payload.periods, key=lambda p: p.start_time)
    for earlier, later in zip(periods, periods[1:]):
        if later.start_time < earlier.end_time:
            raise AppError(status.HTTP_400_BAD_REQUEST, "periods_overlap", f"{earlier.label} and {later.label} overlap.")
    existing = {r["id"] for r in await fetch_all("SELECT id FROM school_periods WHERE school_id = %s", (user.school_id,))}
    unknown = [p.id for p in periods if p.id and p.id not in existing]
    if unknown:
        raise AppError(status.HTTP_404_NOT_FOUND, "period_not_found", "Period not found.")

    kept = {p.id for p in periods if p.id}
    async with db.pool.acquire() as conn:
        await conn.begin()
        try:
            async with conn.cursor() as cur:
                for period_id in existing - kept:
                    await cur.execute("DELETE FROM school_periods WHERE id = %s", (period_id,))
                for position, p in enumerate(periods, start=1):
                    if p.id:
                        await cur.execute(
                            "UPDATE school_periods SET position = %s, label = %s, start_time = %s, end_time = %s, is_break = %s WHERE id = %s",
                            (position, p.label, p.start_time, p.end_time, p.is_break, p.id),
                        )
                    else:
                        await cur.execute(
                            "INSERT INTO school_periods (id, school_id, position, label, start_time, end_time, is_break) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                            (str(uuid.uuid4()), user.school_id, position, p.label, p.start_time, p.end_time, p.is_break),
                        )
                # A period turned into a break loses its lessons.
                await cur.execute(
                    """
                    DELETE te FROM timetable_entries te JOIN school_periods sp ON sp.id = te.period_id
                    WHERE sp.school_id = %s AND sp.is_break = 1
                    """,
                    (user.school_id,),
                )
        except Exception:
            await conn.rollback()
            raise
        await conn.commit()
    return await list_periods(user.school_id)


_CELLS = """
    SELECT te.weekday, te.period_id, te.subject_id, te.class_id, sub.name AS subject_name,
           c.name AS class_name, c.section, u.full_name AS teacher_name, cs.teacher_id
    FROM timetable_entries te
    JOIN subjects sub ON sub.id = te.subject_id
    JOIN classes c ON c.id = te.class_id
    LEFT JOIN class_subjects cs ON cs.class_id = te.class_id AND cs.subject_id = te.subject_id
    LEFT JOIN teachers t ON t.id = cs.teacher_id
    LEFT JOIN users u ON u.id = t.user_id
"""


def _cell(r: dict) -> CellOut:
    return CellOut(
        weekday=r["weekday"], period_id=r["period_id"], subject_id=r["subject_id"], subject_name=r["subject_name"],
        teacher_name=r["teacher_name"], class_id=r["class_id"], class_label=f"{r['class_name']} - {r['section']}",
    )


async def _class_row(school_id: str, class_id: str) -> dict:
    row = await fetch_one("SELECT * FROM classes WHERE id = %s AND school_id = %s AND is_archived = 0", (class_id, school_id))
    if row is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "class_not_found", "Class not found.")
    return row


async def _class_timetable(cls: dict) -> TimetableOut:
    rows = await fetch_all(f"{_CELLS} WHERE te.class_id = %s", (cls["id"],))
    return TimetableOut(title=f"{cls['name']} - {cls['section']}", periods=await list_periods(cls["school_id"]), cells=[_cell(r) for r in rows])


async def class_timetable(user: CurrentUser, class_id: str) -> TimetableOut:
    """Staff can view any class's timetable."""
    return await _class_timetable(await _class_row(user.school_id, class_id))


async def save_class_timetable(user: CurrentUser, class_id: str, payload: ClassGridIn) -> TimetableOut:
    cls = await _class_row(user.school_id, class_id)
    periods = {r["id"]: r for r in await fetch_all("SELECT * FROM school_periods WHERE school_id = %s", (user.school_id,))}
    subjects = {
        r["subject_id"]: r
        for r in await fetch_all(
            """
            SELECT cs.subject_id, cs.teacher_id, sub.name, u.full_name AS teacher_name
            FROM class_subjects cs JOIN subjects sub ON sub.id = cs.subject_id
            JOIN teachers t ON t.id = cs.teacher_id JOIN users u ON u.id = t.user_id
            WHERE cs.class_id = %s
            """,
            (class_id,),
        )
    }
    slots = set()
    for cell in payload.cells:
        period = periods.get(cell.period_id)
        if period is None:
            raise AppError(status.HTTP_404_NOT_FOUND, "period_not_found", "Period not found.")
        if period["is_break"]:
            raise AppError(status.HTTP_400_BAD_REQUEST, "break_period", f"{period['label']} is a break.")
        if cell.subject_id not in subjects:
            raise AppError(status.HTTP_400_BAD_REQUEST, "subject_not_in_class", "That subject isn't taught in this class.")
        if (cell.weekday, cell.period_id) in slots:
            raise AppError(status.HTTP_400_BAD_REQUEST, "duplicate_slot", "A period appears twice.")
        slots.add((cell.weekday, cell.period_id))

    # The same teacher can't be in another class at the same time.
    busy = {
        (r["weekday"], r["period_id"], r["teacher_id"]): r
        for r in await fetch_all(
            f"{_CELLS} WHERE te.school_id = %s AND te.class_id <> %s AND c.is_archived = 0 AND cs.teacher_id IS NOT NULL",
            (user.school_id, class_id),
        )
    }
    for cell in payload.cells:
        subject = subjects[cell.subject_id]
        other = busy.get((cell.weekday, cell.period_id, subject["teacher_id"]))
        if other:
            raise AppError(
                status.HTTP_409_CONFLICT,
                "teacher_clash",
                f"{subject['teacher_name']} already teaches {other['class_name']} - {other['section']} "
                f"on {WEEKDAYS[cell.weekday]}, {periods[cell.period_id]['label']}.",
            )

    async with db.pool.acquire() as conn:
        await conn.begin()
        try:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM timetable_entries WHERE class_id = %s", (class_id,))
                if payload.cells:
                    await cur.executemany(
                        "INSERT INTO timetable_entries (id, school_id, class_id, weekday, period_id, subject_id) VALUES (%s, %s, %s, %s, %s, %s)",
                        [(str(uuid.uuid4()), user.school_id, class_id, c.weekday, c.period_id, c.subject_id) for c in payload.cells],
                    )
        except Exception:
            await conn.rollback()
            raise
        await conn.commit()
    return await _class_timetable(cls)


async def my_timetable(user: CurrentUser, student_id: str | None) -> TimetableOut:
    """A teacher's week across classes, or a parent's child's class."""
    if user.role == "teacher":
        teacher_id = await audience.teacher_id(user)
        rows = await fetch_all(f"{_CELLS} WHERE te.school_id = %s AND c.is_archived = 0 AND cs.teacher_id = %s", (user.school_id, teacher_id)) if teacher_id else []
        return TimetableOut(title="My timetable", periods=await list_periods(user.school_id), cells=[_cell(r) for r in rows])
    if user.role in ("parent", "student"):
        kids = await audience.children(user)
        child = next((k for k in kids if k["id"] == student_id), None) if student_id else (kids[0] if kids else None)
        if child is None:
            raise AppError(status.HTTP_404_NOT_FOUND, "child_not_found", "Child not found.")
        return await _class_timetable(await _class_row(child["school_id"], child["class_id"]))
    raise AppError(status.HTTP_403_FORBIDDEN, "forbidden", "Admins view class timetables.")


async def today_for_teacher(user: CurrentUser, weekday: int) -> list[tuple[PeriodOut, CellOut]]:
    """A teacher's lessons on a weekday, in period order (for the dashboard)."""
    week = await my_timetable(user, None)
    cells = {c.period_id: c for c in week.cells if c.weekday == weekday}
    return [(p, cells[p.id]) for p in week.periods if p.id in cells]
