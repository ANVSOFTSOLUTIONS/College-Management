"""What a teacher sees of the classes they teach, and remarks about students.

A teacher "teaches" a class if they are its class teacher or teach one of its
subjects. Subject teachers see the class list and write remarks, but student
records, parents' details, and attendance stay with the class teacher.
"""

import uuid
from datetime import date
from typing import Literal

from fastapi import status
from pydantic import BaseModel, Field, field_validator

from app.api.deps import CurrentUser
from app.core.errors import AppError
from app.db.helpers import execute, fetch_all, fetch_one
from app.modules.alerts import service as alerts

RemarkCategory = Literal["missed_exam", "absent_class", "homework", "behaviour", "appreciation", "other"]
CATEGORY_LABELS = {
    "missed_exam": "Missed exam",
    "absent_class": "Absent from class",
    "homework": "Homework",
    "behaviour": "Behaviour",
    "appreciation": "Appreciation",
    "other": "Other",
}


class SubjectRef(BaseModel):
    id: str
    name: str


class TeachingClass(BaseModel):
    id: str
    name: str
    section: str
    academic_year: str
    is_class_teacher: bool
    subjects: list[SubjectRef]
    student_count: int


class RosterStudent(BaseModel):
    id: str
    full_name: str
    admission_number: str
    has_photo: bool


class CreateRemarkRequest(BaseModel):
    student_id: str
    category: RemarkCategory
    note: str = Field(default="", max_length=500)
    subject_id: str | None = None
    remark_date: date | None = None
    notify_parent: bool = False

    @field_validator("note", mode="before")
    @classmethod
    def _strip(cls, value):
        return value.strip() if isinstance(value, str) else value


class RemarkOut(BaseModel):
    id: str
    student_id: str
    student_name: str
    admission_number: str
    class_id: str
    class_name: str
    section: str
    subject_name: str | None
    category: RemarkCategory
    category_label: str
    note: str
    remark_date: date
    author_name: str
    notify_parent: bool
    alert_status: str | None
    can_delete: bool
    created_at: str


# --- Access -------------------------------------------------------------------


async def _teacher_id(user: CurrentUser) -> str | None:
    row = await fetch_one("SELECT id FROM teachers WHERE user_id = %s AND school_id = %s", (user.id, user.school_id))
    return row["id"] if row else None


async def teaching_classes(user: CurrentUser) -> list[TeachingClass]:
    teacher_id = await _teacher_id(user) if user.role == "teacher" else None
    if user.role == "teacher" and teacher_id is None:
        return []
    if user.role == "admin":
        classes = await fetch_all("SELECT * FROM classes WHERE school_id = %s AND is_archived = 0 ORDER BY name, section", (user.school_id,))
    else:
        classes = await fetch_all(
            """
            SELECT DISTINCT c.* FROM classes c
            LEFT JOIN class_subjects cs ON cs.class_id = c.id AND cs.teacher_id = %s
            WHERE c.school_id = %s AND c.is_archived = 0 AND (c.teacher_id = %s OR cs.id IS NOT NULL)
            ORDER BY c.name, c.section
            """,
            (teacher_id, user.school_id, teacher_id),
        )
    if not classes:
        return []
    placeholders = ", ".join(["%s"] * len(classes))
    subject_rows = await fetch_all(
        f"""
        SELECT cs.class_id, cs.teacher_id, s.id, s.name FROM class_subjects cs JOIN subjects s ON s.id = cs.subject_id
        WHERE cs.class_id IN ({placeholders}) ORDER BY s.name
        """,
        tuple(c["id"] for c in classes),
    )
    counts = {
        row["class_id"]: row["n"]
        for row in await fetch_all(
            f"SELECT class_id, COUNT(*) AS n FROM students WHERE status = 'active' AND class_id IN ({placeholders}) GROUP BY class_id",
            tuple(c["id"] for c in classes),
        )
    }
    return [
        TeachingClass(
            id=c["id"],
            name=c["name"],
            section=c["section"],
            academic_year=c["academic_year"],
            is_class_teacher=teacher_id is not None and c["teacher_id"] == teacher_id,
            # A teacher sees the subjects they teach; an admin sees them all.
            subjects=[
                SubjectRef(id=s["id"], name=s["name"])
                for s in subject_rows
                if s["class_id"] == c["id"] and (user.role == "admin" or s["teacher_id"] == teacher_id)
            ],
            student_count=counts.get(c["id"], 0),
        )
        for c in classes
    ]


async def _require_teaching(user: CurrentUser, class_id: str) -> TeachingClass:
    teaching = next((c for c in await teaching_classes(user) if c.id == class_id), None)
    if teaching is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "class_not_found", "Class not found.")
    return teaching


async def class_roster(user: CurrentUser, class_id: str) -> list[RosterStudent]:
    await _require_teaching(user, class_id)
    rows = await fetch_all(
        "SELECT id, full_name, admission_number, photo_path FROM students WHERE class_id = %s AND status = 'active' ORDER BY full_name",
        (class_id,),
    )
    return [
        RosterStudent(id=r["id"], full_name=r["full_name"], admission_number=r["admission_number"], has_photo=bool(r["photo_path"]))
        for r in rows
    ]


# --- Remarks ------------------------------------------------------------------

_REMARK_SELECT = """
    SELECT r.*, s.full_name AS student_name, s.admission_number, c.name AS class_name, c.section, c.teacher_id AS class_teacher_id,
           sub.name AS subject_name, u.full_name AS author_name,
           (SELECT a.status FROM parent_alerts a WHERE a.school_id = r.school_id AND a.dedupe_key = CONCAT('remark:', r.id)) AS alert_status
    FROM student_remarks r
    JOIN students s ON s.id = r.student_id
    JOIN classes c ON c.id = r.class_id
    LEFT JOIN subjects sub ON sub.id = r.subject_id
    LEFT JOIN users u ON u.id = r.author_id
"""


def _remark_out(row: dict, user: CurrentUser) -> RemarkOut:
    return RemarkOut(
        id=row["id"],
        student_id=row["student_id"],
        student_name=row["student_name"],
        admission_number=row["admission_number"],
        class_id=row["class_id"],
        class_name=row["class_name"],
        section=row["section"],
        subject_name=row["subject_name"],
        category=row["category"],
        category_label=CATEGORY_LABELS[row["category"]],
        note=row["note"],
        remark_date=row["remark_date"],
        author_name=row["author_name"] or "Former staff",
        notify_parent=bool(row["notify_parent"]),
        alert_status=row["alert_status"],
        can_delete=user.role == "admin" or row["author_id"] == user.id,
        created_at=row["created_at"].isoformat(),
    )


async def create_remark(user: CurrentUser, payload: CreateRemarkRequest) -> RemarkOut:
    student = await fetch_one(
        "SELECT * FROM students WHERE id = %s AND school_id = %s AND status = 'active'", (payload.student_id, user.school_id)
    )
    if student is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "student_not_found", "Student not found.")
    teaching = await _require_teaching(user, student["class_id"])

    subject_name = None
    if payload.subject_id:
        subject = next((s for s in teaching.subjects if s.id == payload.subject_id), None)
        if subject is None:
            raise AppError(status.HTTP_400_BAD_REQUEST, "invalid_subject", "Choose a subject you teach in this class.")
        subject_name = subject.name

    remark_id = str(uuid.uuid4())
    remark_date = payload.remark_date or alerts.today_ist()
    await execute(
        """
        INSERT INTO student_remarks (id, school_id, student_id, class_id, subject_id, author_id, category, note, remark_date, notify_parent)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            remark_id,
            user.school_id,
            student["id"],
            student["class_id"],
            payload.subject_id,
            user.id,
            payload.category,
            payload.note,
            remark_date,
            payload.notify_parent,
        ),
    )
    row = await fetch_one(f"{_REMARK_SELECT} WHERE r.id = %s", (remark_id,))
    if payload.notify_parent:
        await alerts.alert_remark(row, subject_name, user.id)
        row = await fetch_one(f"{_REMARK_SELECT} WHERE r.id = %s", (remark_id,))
    return _remark_out(row, user)


async def list_remarks(user: CurrentUser, *, class_id: str | None, student_id: str | None) -> list[RemarkOut]:
    where, params = ["r.school_id = %s"], [user.school_id]
    if user.role != "admin":
        # Class teachers see every remark in their classes; subject teachers see their own.
        teacher_id = await _teacher_id(user)
        where.append("(c.teacher_id = %s OR r.author_id = %s)")
        params.extend([teacher_id, user.id])
    if class_id:
        where.append("r.class_id = %s")
        params.append(class_id)
    if student_id:
        where.append("r.student_id = %s")
        params.append(student_id)
    rows = await fetch_all(
        f"{_REMARK_SELECT} WHERE {' AND '.join(where)} ORDER BY r.remark_date DESC, r.created_at DESC LIMIT 300", tuple(params)
    )
    return [_remark_out(row, user) for row in rows]


async def delete_remark(user: CurrentUser, remark_id: str) -> None:
    row = await fetch_one("SELECT author_id FROM student_remarks WHERE id = %s AND school_id = %s", (remark_id, user.school_id))
    if row is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "remark_not_found", "Remark not found.")
    if user.role != "admin" and row["author_id"] != user.id:
        raise AppError(status.HTTP_403_FORBIDDEN, "forbidden", "Only the teacher who wrote this remark or an admin can delete it.")
    await execute("DELETE FROM student_remarks WHERE id = %s", (remark_id,))
