"""Grievances: students, parents and faculty raise a ticket from the app; the college office answers.

Ragging and harassment complaints are marked high priority and every admin is
notified straight away. The person who raised a ticket sees only their own
tickets and the office's replies; the office sees everything. Replying from
either side keeps the thread; a reply from the raiser reopens a resolved ticket.
"""

import uuid
from datetime import datetime
from typing import Literal

import aiomysql
from fastapi import status
from pydantic import BaseModel, Field, field_validator

from app.api.deps import CurrentUser
from app.core.errors import AppError
from app.db.helpers import execute, fetch_all, fetch_one
from app.modules.notifications import service as notifications

Category = Literal["academic", "examination", "fees", "hostel", "transport", "infrastructure", "ragging", "harassment", "other"]
Status = Literal["open", "in_progress", "resolved", "closed"]
HIGH_PRIORITY = {"ragging", "harassment"}
CATEGORY_LABELS = {
    "academic": "Academic", "examination": "Examination", "fees": "Fees", "hostel": "Hostel", "transport": "Transport",
    "infrastructure": "Infrastructure", "ragging": "Ragging", "harassment": "Harassment", "other": "Other",
}


def _strip(value):
    return value.strip() if isinstance(value, str) else value


class GrievanceIn(BaseModel):
    category: Category
    subject: str = Field(min_length=3, max_length=150)
    description: str = Field(min_length=10, max_length=4000)
    student_id: str | None = None

    _strip = field_validator("subject", "description", mode="before")(_strip)


class ReplyIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)

    _strip = field_validator("message", mode="before")(_strip)


class StatusIn(BaseModel):
    status: Status
    note: str | None = Field(default=None, max_length=4000)


class ReplyOut(BaseModel):
    id: str
    from_office: bool
    author_name: str | None
    message: str
    created_at: datetime


class GrievanceOut(BaseModel):
    id: str
    ticket_number: str
    category: str
    category_label: str
    priority: str
    subject: str
    description: str
    status: str
    raised_by: str
    raised_by_role: str
    student_name: str | None
    created_at: datetime
    resolved_at: datetime | None
    replies: list[ReplyOut] = []


class GrievanceSummary(BaseModel):
    open: int
    in_progress: int
    resolved: int
    closed: int
    high_priority_open: int


_SELECT = """
    SELECT g.*, u.full_name AS raised_by, u.role AS raised_by_role, s.full_name AS student_name
    FROM grievances g JOIN users u ON u.id = g.raised_by_user_id LEFT JOIN students s ON s.id = g.student_id
"""


def _out(row: dict) -> GrievanceOut:
    return GrievanceOut(
        id=row["id"], ticket_number=row["ticket_number"], category=row["category"], category_label=CATEGORY_LABELS.get(row["category"], row["category"]),
        priority=row["priority"], subject=row["subject"], description=row["description"], status=row["status"], raised_by=row["raised_by"],
        raised_by_role=row["raised_by_role"], student_name=row["student_name"], created_at=row["created_at"], resolved_at=row["resolved_at"],
    )


async def _with_replies(row: dict, office: bool) -> GrievanceOut:
    out = _out(row)
    replies = await fetch_all(
        """
        SELECT r.id, r.from_office, r.message, r.created_at, u.full_name AS author_name FROM grievance_replies r
        LEFT JOIN users u ON u.id = r.author_user_id WHERE r.grievance_id = %s ORDER BY r.created_at, r.id
        """,
        (row["id"],),
    )
    # The raiser sees "College office" rather than the staff member's name.
    out.replies = [ReplyOut(id=r["id"], from_office=bool(r["from_office"]), author_name=r["author_name"] if office or not r["from_office"] else None,
                            message=r["message"], created_at=r["created_at"])
                   for r in replies]
    return out


async def _get(user: CurrentUser, grievance_id: str) -> dict:
    row = await fetch_one(f"{_SELECT} WHERE g.id = %s AND g.school_id = %s", (grievance_id, user.school_id))
    if row is None or (user.role != "admin" and row["raised_by_user_id"] != user.id):
        raise AppError(status.HTTP_404_NOT_FOUND, "grievance_not_found", "Grievance not found.")
    return row


async def _raiser_student(user: CurrentUser, student_id: str | None) -> str | None:
    """The student a ticket is about: a student's own record, or one of a parent's children."""
    if user.role == "teacher":
        return None
    if user.role == "student":
        row = await fetch_one("SELECT id FROM students WHERE user_id = %s", (user.id,))
        return row["id"] if row else None
    if student_id is None:
        rows = await fetch_all("SELECT student_id FROM parent_students WHERE parent_user_id = %s", (user.id,))
        return rows[0]["student_id"] if len(rows) == 1 else None
    if not await fetch_one("SELECT 1 FROM parent_students WHERE parent_user_id = %s AND student_id = %s", (user.id, student_id)):
        raise AppError(status.HTTP_404_NOT_FOUND, "child_not_found", "Child not found.")
    return student_id


async def create(user: CurrentUser, payload: GrievanceIn) -> GrievanceOut:
    student_id = await _raiser_student(user, payload.student_id)
    priority = "high" if payload.category in HIGH_PRIORITY else "normal"
    grievance_id = str(uuid.uuid4())
    for _ in range(5):
        count = await fetch_one("SELECT COUNT(*) AS n FROM grievances WHERE school_id = %s", (user.school_id,))
        ticket = f"GRV-{count['n'] + 1:05d}"
        try:
            await execute(
                """
                INSERT INTO grievances (id, school_id, ticket_number, raised_by_user_id, student_id, category, priority, subject, description)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (grievance_id, user.school_id, ticket, user.id, student_id, payload.category, priority, payload.subject, payload.description),
            )
            break
        except aiomysql.IntegrityError:
            continue  # two tickets raised at the same moment; take the next number
    else:
        raise AppError(status.HTTP_409_CONFLICT, "try_again", "Couldn't raise the grievance. Please try again.")
    title = f"{'URGENT ' if priority == 'high' else ''}Grievance {ticket}: {CATEGORY_LABELS[payload.category]}"
    await notifications.notify(await notifications.admin_user_ids(user.school_id), school_id=user.school_id, title=title, body=payload.subject, link="grievances")
    return await _with_replies(await _get(user, grievance_id), False)


async def mine(user: CurrentUser) -> list[GrievanceOut]:
    rows = await fetch_all(f"{_SELECT} WHERE g.raised_by_user_id = %s ORDER BY g.created_at DESC, g.ticket_number DESC", (user.id,))
    return [_out(r) for r in rows]


async def list_all(user: CurrentUser, status_filter: str | None, category: str | None) -> list[GrievanceOut]:
    where, params = ["g.school_id = %s"], [user.school_id]
    if status_filter:
        where.append("g.status = %s")
        params.append(status_filter)
    if category:
        where.append("g.category = %s")
        params.append(category)
    rows = await fetch_all(
        f"{_SELECT} WHERE {' AND '.join(where)} ORDER BY g.status IN ('resolved', 'closed'), g.priority = 'high' DESC, g.created_at DESC, g.ticket_number DESC",
        tuple(params),
    )
    return [_out(r) for r in rows]


async def summary(user: CurrentUser) -> GrievanceSummary:
    row = await fetch_one(
        """
        SELECT SUM(status = 'open') AS open, SUM(status = 'in_progress') AS in_progress, SUM(status = 'resolved') AS resolved,
               SUM(status = 'closed') AS closed, SUM(priority = 'high' AND status IN ('open', 'in_progress')) AS high_priority_open
        FROM grievances WHERE school_id = %s
        """,
        (user.school_id,),
    )
    return GrievanceSummary(**{k: int(v or 0) for k, v in row.items()})


async def get(user: CurrentUser, grievance_id: str) -> GrievanceOut:
    return await _with_replies(await _get(user, grievance_id), user.role == "admin")


async def _add_reply(grievance_id: str, user: CurrentUser, from_office: bool, message: str) -> None:
    await execute(
        "INSERT INTO grievance_replies (id, grievance_id, author_user_id, from_office, message) VALUES (%s, %s, %s, %s, %s)",
        (str(uuid.uuid4()), grievance_id, user.id, from_office, message),
    )


async def reply(user: CurrentUser, grievance_id: str, payload: ReplyIn) -> GrievanceOut:
    row = await _get(user, grievance_id)
    office = user.role == "admin"
    if row["status"] == "closed" and not office:
        raise AppError(status.HTTP_409_CONFLICT, "grievance_closed", "This grievance is closed. Raise a new one if needed.")
    await _add_reply(grievance_id, user, office, payload.message)
    if office:
        if row["status"] == "open":
            await execute("UPDATE grievances SET status = 'in_progress' WHERE id = %s", (grievance_id,))
        await notifications.notify([row["raised_by_user_id"]], school_id=user.school_id, title=f"Reply on {row['ticket_number']}", body=payload.message[:200],
                                   link="grievances")
    elif row["status"] == "resolved":
        await execute("UPDATE grievances SET status = 'open', resolved_at = NULL WHERE id = %s", (grievance_id,))
    return await get(user, grievance_id)


async def set_status(user: CurrentUser, grievance_id: str, payload: StatusIn) -> GrievanceOut:
    row = await _get(user, grievance_id)
    done = payload.status in ("resolved", "closed")
    await execute(
        "UPDATE grievances SET status = %s, resolved_at = CASE WHEN %s THEN COALESCE(resolved_at, CURRENT_TIMESTAMP) ELSE NULL END WHERE id = %s",
        (payload.status, done, grievance_id),
    )
    if payload.note and payload.note.strip():
        await _add_reply(grievance_id, user, True, payload.note.strip())
    label = {"open": "reopened", "in_progress": "being looked into", "resolved": "resolved", "closed": "closed"}[payload.status]
    await notifications.notify([row["raised_by_user_id"]], school_id=user.school_id, title=f"{row['ticket_number']} is {label}", body=row["subject"],
                               link="grievances")
    return await get(user, grievance_id)
