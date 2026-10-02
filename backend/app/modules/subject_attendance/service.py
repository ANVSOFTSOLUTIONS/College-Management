"""Subject-wise attendance: marked per subject and period by the subject's faculty.

Colleges check the 75% rule per subject, so each class hour is recorded
separately (date + period). Late counts as attended. The class teacher and
admins can mark any subject of the batch; other faculty only the subjects
they teach in it.
"""

import uuid
from datetime import date
from typing import Literal

from fastapi import status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser
from app.core.errors import AppError
from app.db.database import db
from app.db.helpers import fetch_all, fetch_one

Status = Literal["present", "absent", "late"]
REQUIRED_PERCENT = 75.0


class TeachingSubject(BaseModel):
    class_id: str
    class_name: str
    section: str
    subject_id: str
    subject_name: str


class SheetRow(BaseModel):
    student_id: str
    full_name: str
    admission_number: str
    status: Status | None


class Sheet(BaseModel):
    class_id: str
    subject_id: str
    subject_name: str
    date: date
    period: int
    marked: bool
    rows: list[SheetRow]


class RecordIn(BaseModel):
    student_id: str
    status: Status


class SaveSheetIn(BaseModel):
    class_id: str
    subject_id: str
    date: date
    period: int = Field(default=1, ge=1, le=12)
    records: list[RecordIn] = Field(min_length=1)


class SubjectPercent(BaseModel):
    subject_id: str
    subject_name: str
    held: int
    attended: int
    percent: float | None
    short: bool  # below the required percentage


class StudentSummary(BaseModel):
    student_id: str
    full_name: str
    admission_number: str
    subjects: list[SubjectPercent]


async def _teacher_id(user: CurrentUser) -> str | None:
    row = await fetch_one("SELECT id FROM teachers WHERE user_id = %s AND school_id = %s", (user.id, user.school_id))
    return row["id"] if row else None


async def my_subjects(user: CurrentUser) -> list[TeachingSubject]:
    where, params = "c.school_id = %s AND c.is_archived = 0", [user.school_id]
    if user.role != "admin":
        where += " AND (cs.teacher_id = %s OR c.teacher_id = %s)"
        teacher_id = await _teacher_id(user)
        params += [teacher_id, teacher_id]
    rows = await fetch_all(
        f"""
        SELECT c.id AS class_id, c.name AS class_name, c.section, s.id AS subject_id, s.name AS subject_name
        FROM class_subjects cs JOIN classes c ON c.id = cs.class_id JOIN subjects s ON s.id = cs.subject_id
        WHERE {where} ORDER BY c.name, c.section, s.name
        """,
        tuple(params),
    )
    return [TeachingSubject(**r) for r in rows]


async def _require_subject(user: CurrentUser, class_id: str, subject_id: str) -> dict:
    row = await fetch_one(
        """
        SELECT c.teacher_id AS class_teacher_id, cs.teacher_id AS subject_teacher_id, s.name AS subject_name
        FROM class_subjects cs JOIN classes c ON c.id = cs.class_id JOIN subjects s ON s.id = cs.subject_id
        WHERE cs.class_id = %s AND cs.subject_id = %s AND c.school_id = %s
        """,
        (class_id, subject_id, user.school_id),
    )
    if row is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "subject_not_found", "This subject isn't taught in this batch.")
    if user.role != "admin" and await _teacher_id(user) not in (row["class_teacher_id"], row["subject_teacher_id"]):
        raise AppError(status.HTTP_403_FORBIDDEN, "forbidden", "Only the subject's faculty or the class teacher can mark this.")
    return row


async def sheet(user: CurrentUser, class_id: str, subject_id: str, day: date, period: int) -> Sheet:
    subject = await _require_subject(user, class_id, subject_id)
    rows = await fetch_all(
        """
        SELECT s.id, s.full_name, s.admission_number, a.status FROM students s
        LEFT JOIN subject_attendance a ON a.student_id = s.id AND a.subject_id = %s AND a.attendance_date = %s AND a.period = %s
        WHERE s.class_id = %s AND s.status = 'active' ORDER BY s.admission_number
        """,
        (subject_id, day, period, class_id),
    )
    return Sheet(
        class_id=class_id, subject_id=subject_id, subject_name=subject["subject_name"], date=day, period=period,
        marked=any(r["status"] for r in rows),
        rows=[SheetRow(student_id=r["id"], full_name=r["full_name"], admission_number=r["admission_number"], status=r["status"]) for r in rows],
    )


async def save(user: CurrentUser, payload: SaveSheetIn) -> Sheet:
    await _require_subject(user, payload.class_id, payload.subject_id)
    roster = {r["id"] for r in await fetch_all("SELECT id FROM students WHERE class_id = %s AND status = 'active'", (payload.class_id,))}
    if any(r.student_id not in roster for r in payload.records):
        raise AppError(status.HTTP_400_BAD_REQUEST, "unknown_student", "Some students aren't in this batch.")
    async with db.pool.acquire() as conn:
        await conn.begin()
        async with conn.cursor() as cur:
            for record in payload.records:
                await cur.execute(
                    """
                    INSERT INTO subject_attendance (id, school_id, class_id, subject_id, student_id, attendance_date, period, status, marked_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE status = VALUES(status), marked_by = VALUES(marked_by)
                    """,
                    (str(uuid.uuid4()), user.school_id, payload.class_id, payload.subject_id, record.student_id, payload.date,
                     payload.period, record.status, user.id),
                )
        await conn.commit()
    return await sheet(user, payload.class_id, payload.subject_id, payload.date, payload.period)


def _percent(held: int, attended: int) -> float | None:
    return round(attended * 100 / held, 1) if held else None


async def _counts(where: str, params: tuple) -> list[dict]:
    return await fetch_all(
        f"""
        SELECT a.student_id, a.subject_id, s.name AS subject_name, COUNT(*) AS held, SUM(a.status IN ('present', 'late')) AS attended
        FROM subject_attendance a JOIN subjects s ON s.id = a.subject_id
        WHERE {where} GROUP BY a.student_id, a.subject_id, s.name ORDER BY s.name
        """,
        params,
    )


def _subject_percent(r: dict) -> SubjectPercent:
    percent = _percent(r["held"], int(r["attended"]))
    return SubjectPercent(
        subject_id=r["subject_id"], subject_name=r["subject_name"], held=r["held"], attended=int(r["attended"]), percent=percent,
        short=percent is not None and percent < REQUIRED_PERCENT,
    )


async def class_summary(user: CurrentUser, class_id: str) -> list[StudentSummary]:
    batch = await fetch_one("SELECT teacher_id FROM classes WHERE id = %s AND school_id = %s", (class_id, user.school_id))
    if batch is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "class_not_found", "Batch not found.")
    if user.role != "admin":
        teacher_id = await _teacher_id(user)
        teaches = await fetch_one("SELECT 1 FROM class_subjects WHERE class_id = %s AND teacher_id = %s", (class_id, teacher_id))
        if batch["teacher_id"] != teacher_id and not teaches:
            raise AppError(status.HTTP_403_FORBIDDEN, "forbidden", "Only the batch's faculty can see this.")
    students = await fetch_all(
        "SELECT id, full_name, admission_number FROM students WHERE class_id = %s AND status = 'active' ORDER BY admission_number", (class_id,)
    )
    counts = await _counts("a.class_id = %s", (class_id,))
    return [
        StudentSummary(
            student_id=s["id"], full_name=s["full_name"], admission_number=s["admission_number"],
            subjects=[_subject_percent(r) for r in counts if r["student_id"] == s["id"]],
        )
        for s in students
    ]


async def student_percentages(student_id: str) -> list[SubjectPercent]:
    return [_subject_percent(r) for r in await _counts("a.student_id = %s", (student_id,))]
