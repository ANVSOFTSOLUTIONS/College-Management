"""Lesson plans: each subject's syllabus topics for a batch, ticked off as they're taught.

The subject's faculty (or the class teacher, or an admin) adds topics unit by
unit, optionally with a planned date, and marks them done. Progress is shown
per batch and subject to admins, to HODs for their department and to faculty
for their own subjects; students see how much of each subject is covered.
"""

import uuid
from datetime import date

from fastapi import status
from pydantic import BaseModel, Field, field_validator

from app.api.deps import CurrentUser
from app.core.errors import AppError
from app.db.database import db
from app.db.helpers import execute, fetch_all, fetch_one
from app.modules.alerts.service import today_ist
from app.modules.hod.service import hod_departments
from app.modules.subject_attendance.service import _require_subject, _teacher_id


class TopicIn(BaseModel):
    unit: int = Field(default=1, ge=1, le=20)
    title: str = Field(min_length=1, max_length=200)
    planned_date: date | None = None

    _strip = field_validator("title", mode="before")(lambda v: v.strip() if isinstance(v, str) else v)


class AddTopicsIn(BaseModel):
    class_id: str
    subject_id: str
    topics: list[TopicIn] = Field(min_length=1, max_length=300)


class TopicUpdate(BaseModel):
    completed: bool | None = None
    completed_on: date | None = None
    planned_date: date | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)


class TopicOut(BaseModel):
    id: str
    unit: int
    title: str
    planned_date: date | None
    completed_on: date | None
    overdue: bool


class LessonPlan(BaseModel):
    class_id: str
    subject_id: str
    subject_name: str
    topics: list[TopicOut]
    done: int
    total: int
    percent: float | None


class Progress(BaseModel):
    class_id: str
    batch: str
    subject_id: str
    subject_name: str
    teacher_name: str
    done: int
    total: int
    overdue: int
    percent: float | None


def _pct(done: int, total: int) -> float | None:
    return round(done * 100 / total, 1) if total else None


async def plan(user: CurrentUser, class_id: str, subject_id: str) -> LessonPlan:
    subject = await _require_subject(user, class_id, subject_id)
    return await _plan(class_id, subject_id, subject["subject_name"])


async def _plan(class_id: str, subject_id: str, subject_name: str) -> LessonPlan:
    today = today_ist()
    rows = await fetch_all(
        "SELECT * FROM lesson_topics WHERE class_id = %s AND subject_id = %s ORDER BY unit, position, created_at", (class_id, subject_id)
    )
    topics = [
        TopicOut(id=r["id"], unit=r["unit"], title=r["title"], planned_date=r["planned_date"], completed_on=r["completed_on"],
                 overdue=r["completed_on"] is None and r["planned_date"] is not None and r["planned_date"] < today)
        for r in rows
    ]
    done = sum(1 for t in topics if t.completed_on)
    return LessonPlan(class_id=class_id, subject_id=subject_id, subject_name=subject_name, topics=topics, done=done, total=len(topics),
                      percent=_pct(done, len(topics)))


async def add_topics(user: CurrentUser, payload: AddTopicsIn) -> LessonPlan:
    subject = await _require_subject(user, payload.class_id, payload.subject_id)
    last = await fetch_one(
        "SELECT COALESCE(MAX(position), 0) AS p FROM lesson_topics WHERE class_id = %s AND subject_id = %s", (payload.class_id, payload.subject_id)
    )
    async with db.pool.acquire() as conn:
        await conn.begin()
        async with conn.cursor() as cur:
            for i, topic in enumerate(payload.topics, start=1):
                await cur.execute(
                    """
                    INSERT INTO lesson_topics (id, school_id, class_id, subject_id, unit, title, planned_date, position)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (str(uuid.uuid4()), user.school_id, payload.class_id, payload.subject_id, topic.unit, topic.title, topic.planned_date, last["p"] + i),
                )
        await conn.commit()
    return await _plan(payload.class_id, payload.subject_id, subject["subject_name"])


async def _topic(user: CurrentUser, topic_id: str) -> tuple[dict, dict]:
    row = await fetch_one("SELECT * FROM lesson_topics WHERE id = %s AND school_id = %s", (topic_id, user.school_id))
    if row is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "topic_not_found", "Topic not found.")
    return row, await _require_subject(user, row["class_id"], row["subject_id"])


async def update_topic(user: CurrentUser, topic_id: str, payload: TopicUpdate) -> LessonPlan:
    row, subject = await _topic(user, topic_id)
    changes = {}
    if payload.title is not None:
        changes["title"] = payload.title.strip()
    if "planned_date" in payload.model_fields_set:
        changes["planned_date"] = payload.planned_date
    if payload.completed is not None:
        changes["completed_on"] = (payload.completed_on or today_ist()) if payload.completed else None
        changes["completed_by"] = user.id if payload.completed else None
    if changes:
        await execute(f"UPDATE lesson_topics SET {', '.join(f'{k} = %s' for k in changes)} WHERE id = %s", (*changes.values(), topic_id))
    return await _plan(row["class_id"], row["subject_id"], subject["subject_name"])


async def delete_topic(user: CurrentUser, topic_id: str) -> LessonPlan:
    row, subject = await _topic(user, topic_id)
    await execute("DELETE FROM lesson_topics WHERE id = %s", (topic_id,))
    return await _plan(row["class_id"], row["subject_id"], subject["subject_name"])


async def progress(user: CurrentUser) -> list[Progress]:
    """Every batch-subject the user may see: all for an admin, the department for a HOD, own subjects for faculty."""
    where, params = ["c.school_id = %s", "c.is_archived = 0"], [user.school_id]
    if user.role != "admin":
        teacher_id = await _teacher_id(user)
        departments = [d["id"] for d in await hod_departments(user)]
        clause = "cs.teacher_id = %s"
        params.append(teacher_id)
        if departments:
            clause += f" OR c.department_id IN ({', '.join(['%s'] * len(departments))})"
            params += departments
        where.append(f"({clause})")
    rows = await fetch_all(
        f"""
        SELECT c.id AS class_id, CONCAT(c.name, ' - ', c.section) AS batch, s.id AS subject_id, s.name AS subject_name, u.full_name AS teacher_name,
               COUNT(lt.id) AS total, SUM(lt.completed_on IS NOT NULL) AS done,
               SUM(lt.completed_on IS NULL AND lt.planned_date < %s) AS overdue
        FROM class_subjects cs JOIN classes c ON c.id = cs.class_id JOIN subjects s ON s.id = cs.subject_id
        JOIN teachers t ON t.id = cs.teacher_id JOIN users u ON u.id = t.user_id
        LEFT JOIN lesson_topics lt ON lt.class_id = cs.class_id AND lt.subject_id = cs.subject_id
        WHERE {' AND '.join(where)}
        GROUP BY c.id, c.name, c.section, s.id, s.name, u.full_name ORDER BY c.name, c.section, s.name
        """,
        (today_ist(), *params),
    )
    return [
        Progress(**{k: r[k] for k in ("class_id", "batch", "subject_id", "subject_name", "teacher_name")}, total=r["total"], done=int(r["done"] or 0),
                 overdue=int(r["overdue"] or 0), percent=_pct(int(r["done"] or 0), r["total"]))
        for r in rows
    ]


async def student_syllabus(student: dict) -> list[LessonPlan]:
    rows = await fetch_all(
        """
        SELECT DISTINCT s.id, s.name FROM lesson_topics lt JOIN subjects s ON s.id = lt.subject_id WHERE lt.class_id = %s ORDER BY s.name
        """,
        (student["class_id"],),
    )
    return [await _plan(student["class_id"], r["id"], r["name"]) for r in rows]
