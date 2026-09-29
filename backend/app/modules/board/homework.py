"""Homework.

A subject teacher posts homework for the subjects they teach; a class teacher
for any subject of their class; admins for any class. Students and parents
of that class see it and get a bell notification.
"""

import uuid
from datetime import date, timedelta

from fastapi import UploadFile, status
from pydantic import BaseModel, Field, field_validator, model_validator

from app.api.deps import CurrentUser
from app.core.errors import AppError
from app.db.helpers import execute, fetch_all, fetch_one
from app.modules.alerts.service import today_ist
from app.modules.board import audience
from app.modules.notifications import service as notifications
from app.modules.students.files import delete_private_file

DEFAULT_DAYS_BACK = 14
MAX_DAYS_AHEAD = 120


class HomeworkIn(BaseModel):
    class_id: str
    subject_id: str
    title: str = Field(min_length=3, max_length=150)
    details: str = Field(default="", max_length=5000)
    assigned_on: date | None = None  # defaults to today
    due_on: date

    @field_validator("title", "details", mode="before")
    @classmethod
    def _strip(cls, value):
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def _dates(self):
        if self.assigned_on and self.due_on < self.assigned_on:
            raise ValueError("The due date can't be before the day it is given.")
        return self


class HomeworkOut(BaseModel):
    id: str
    class_id: str
    class_name: str
    section: str
    subject_id: str
    subject_name: str
    title: str
    details: str
    assigned_on: date
    due_on: date
    attachment_name: str | None
    posted_by_name: str | None
    created_at: str
    can_edit: bool


class SubjectOption(BaseModel):
    id: str
    name: str


class ClassOption(BaseModel):
    id: str
    name: str
    section: str
    subjects: list[SubjectOption]


_SELECT = """
    SELECT h.*, c.name AS class_name, c.section, sub.name AS subject_name, u.full_name AS posted_by_name
    FROM homework h
    JOIN classes c ON c.id = h.class_id
    JOIN subjects sub ON sub.id = h.subject_id
    LEFT JOIN users u ON u.id = h.posted_by
"""


def _out(row: dict, user: CurrentUser) -> HomeworkOut:
    return HomeworkOut(
        id=row["id"], class_id=row["class_id"], class_name=row["class_name"], section=row["section"],
        subject_id=row["subject_id"], subject_name=row["subject_name"], title=row["title"], details=row["details"],
        assigned_on=row["assigned_on"], due_on=row["due_on"], attachment_name=row["attachment_name"],
        posted_by_name=row["posted_by_name"], created_at=row["created_at"].isoformat(),
        can_edit=user.role == "admin" or row["posted_by"] == user.id,
    )


async def _can_post(user: CurrentUser, class_id: str, subject_id: str) -> None:
    link = await fetch_one(
        """
        SELECT cs.teacher_id AS subject_teacher_id, c.teacher_id AS class_teacher_id
        FROM class_subjects cs JOIN classes c ON c.id = cs.class_id
        WHERE cs.class_id = %s AND cs.subject_id = %s AND c.school_id = %s AND c.is_archived = 0
        """,
        (class_id, subject_id, user.school_id),
    )
    if link is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "subject_not_in_class", "That subject isn't taught in this class.")
    if user.role == "admin":
        return
    teacher_id = await audience.teacher_id(user)
    if teacher_id is None or teacher_id not in (link["subject_teacher_id"], link["class_teacher_id"]):
        raise AppError(status.HTTP_403_FORBIDDEN, "forbidden", "You can post homework only for subjects you teach or your own class.")


async def posting_options(user: CurrentUser) -> list[ClassOption]:
    """Classes and subjects the user can post homework (and class notices) for."""
    teacher_id = None if user.role == "admin" else await audience.teacher_id(user)
    if user.role != "admin" and teacher_id is None:
        return []
    rows = await fetch_all(
        """
        SELECT c.id AS class_id, c.name, c.section, c.teacher_id AS class_teacher_id, cs.teacher_id, sub.id AS subject_id, sub.name AS subject_name
        FROM classes c
        LEFT JOIN class_subjects cs ON cs.class_id = c.id
        LEFT JOIN subjects sub ON sub.id = cs.subject_id
        WHERE c.school_id = %s AND c.is_archived = 0
        ORDER BY c.name, c.section, sub.name
        """,
        (user.school_id,),
    )
    options: dict[str, ClassOption] = {}
    for r in rows:
        mine = teacher_id is None or teacher_id in (r["class_teacher_id"], r["teacher_id"])
        if not mine:
            continue
        option = options.setdefault(r["class_id"], ClassOption(id=r["class_id"], name=r["name"], section=r["section"], subjects=[]))
        if r["subject_id"]:
            option.subjects.append(SubjectOption(id=r["subject_id"], name=r["subject_name"]))
    return list(options.values())


async def _visible_class_ids(user: CurrentUser, *, class_id: str | None, student_id: str | None) -> list[str] | None:
    """Classes whose homework the user may list; None means every class of the school (admin)."""
    if user.role in ("parent", "student"):
        kids = await audience.children(user)
        if student_id:
            kids = [k for k in kids if k["id"] == student_id]
            if not kids:
                raise AppError(status.HTTP_404_NOT_FOUND, "child_not_found", "Child not found.")
        return list({k["class_id"] for k in kids})
    if user.role == "teacher":
        mine = await audience.teaching_class_ids(user)
        if class_id:
            if class_id not in mine:
                raise AppError(status.HTTP_404_NOT_FOUND, "class_not_found", "Class not found.")
            return [class_id]
        return list(mine)
    if user.role == "admin":
        return [class_id] if class_id else None
    raise AppError(status.HTTP_403_FORBIDDEN, "forbidden", "Not allowed.")


async def list_homework(user: CurrentUser, *, class_id: str | None, student_id: str | None, since: date | None) -> list[HomeworkOut]:
    class_ids = await _visible_class_ids(user, class_id=class_id, student_id=student_id)
    since = since or today_ist() - timedelta(days=DEFAULT_DAYS_BACK)
    where, params = ["h.due_on >= %s"], [since]
    if user.school_id:
        where.append("h.school_id = %s")
        params.append(user.school_id)
    if class_ids is not None:
        if not class_ids:
            return []
        where.append("h.class_id IN ({})".format(", ".join(["%s"] * len(class_ids))))
        params += class_ids
    rows = await fetch_all(
        f"{_SELECT} WHERE {' AND '.join(where)} ORDER BY h.due_on DESC, h.created_at DESC LIMIT 300", tuple(params)
    )
    return [_out(r, user) for r in rows]


async def _row(user: CurrentUser, homework_id: str) -> dict:
    row = await fetch_one(f"{_SELECT} WHERE h.id = %s", (homework_id,))
    if row is None or (user.role not in ("parent", "student") and row["school_id"] != user.school_id):
        raise AppError(status.HTTP_404_NOT_FOUND, "homework_not_found", "Homework not found.")
    visible = await _visible_class_ids(user, class_id=None, student_id=None)
    if visible is not None and row["class_id"] not in visible and row["posted_by"] != user.id:
        raise AppError(status.HTTP_404_NOT_FOUND, "homework_not_found", "Homework not found.")
    return row


async def _editable(user: CurrentUser, homework_id: str) -> dict:
    row = await _row(user, homework_id)
    if not (user.role == "admin" or row["posted_by"] == user.id):
        raise AppError(status.HTTP_403_FORBIDDEN, "forbidden", "Only the teacher who posted this homework or the admin can change it.")
    return row


def _check_dates(payload: HomeworkIn) -> date:
    today = today_ist()
    assigned = payload.assigned_on or today
    if payload.due_on < assigned:
        raise AppError(status.HTTP_400_BAD_REQUEST, "invalid_dates", "The due date can't be before the day it is given.")
    if payload.due_on > today + timedelta(days=MAX_DAYS_AHEAD):
        raise AppError(status.HTTP_400_BAD_REQUEST, "invalid_dates", f"The due date can be at most {MAX_DAYS_AHEAD} days ahead.")
    return assigned


async def create_homework(user: CurrentUser, payload: HomeworkIn) -> HomeworkOut:
    await _can_post(user, payload.class_id, payload.subject_id)
    assigned = _check_dates(payload)
    homework_id = str(uuid.uuid4())
    await execute(
        """
        INSERT INTO homework (id, school_id, class_id, subject_id, title, details, assigned_on, due_on, posted_by)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (homework_id, user.school_id, payload.class_id, payload.subject_id, payload.title, payload.details, assigned, payload.due_on, user.id),
    )
    row = await _row(user, homework_id)
    recipients = await audience.recipients(user.school_id, [payload.class_id], staff=False, parents=True, students=True)
    await notifications.notify(
        recipients,
        school_id=user.school_id,
        title=f"Homework: {row['subject_name']}",
        body=f"{payload.title}. Due {payload.due_on:%d %b}.",
        link="homework",
    )
    return _out(row, user)


async def update_homework(user: CurrentUser, homework_id: str, payload: HomeworkIn) -> HomeworkOut:
    await _editable(user, homework_id)
    await _can_post(user, payload.class_id, payload.subject_id)
    assigned = _check_dates(payload)
    await execute(
        "UPDATE homework SET class_id = %s, subject_id = %s, title = %s, details = %s, assigned_on = %s, due_on = %s WHERE id = %s",
        (payload.class_id, payload.subject_id, payload.title, payload.details, assigned, payload.due_on, homework_id),
    )
    return _out(await _row(user, homework_id), user)


async def delete_homework(user: CurrentUser, homework_id: str) -> None:
    row = await _editable(user, homework_id)
    await execute("DELETE FROM homework WHERE id = %s", (homework_id,))
    delete_private_file(row["attachment_path"])


async def set_attachment(user: CurrentUser, homework_id: str, file: UploadFile | None) -> HomeworkOut:
    row = await _editable(user, homework_id)
    path = name = content_type = None
    if file is not None:
        path, name, content_type = await audience.save_attachment(user.school_id, "homework", file)
    await execute(
        "UPDATE homework SET attachment_path = %s, attachment_name = %s, attachment_type = %s WHERE id = %s",
        (path, name, content_type, homework_id),
    )
    delete_private_file(row["attachment_path"])
    return _out(await _row(user, homework_id), user)


async def attachment_row(user: CurrentUser, homework_id: str) -> dict:
    return await _row(user, homework_id)
