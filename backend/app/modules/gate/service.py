"""Gate passes and the visitor register.

A student (or parent) asks for a gate pass in the app with the reason and the
leave / return times. The office approves or rejects; the gate marks the
student out and back in. Parents are notified when a pass is approved, when
their child leaves and when they return. Late returns are flagged.
The visitor register records who came in, to meet whom, and when they left.
"""

import uuid
from datetime import date, datetime, timedelta

from fastapi import status
from pydantic import BaseModel, Field, field_validator, model_validator

from app.api.deps import CurrentUser
from app.core.errors import AppError
from app.db.helpers import execute, fetch_all, fetch_one
from app.modules.alerts.service import IST
from app.modules.notifications import service as notifications


def _now() -> datetime:
    return datetime.now(IST).replace(tzinfo=None, microsecond=0)


def _strip(value):
    return value.strip() if isinstance(value, str) else value


class PassIn(BaseModel):
    reason: str = Field(min_length=3, max_length=300)
    leave_at: datetime
    return_by: datetime

    _strip = field_validator("reason", mode="before")(_strip)

    @model_validator(mode="after")
    def _times(self):
        if self.return_by <= self.leave_at:
            raise ValueError("Return time must be after the leaving time.")
        if self.return_by - self.leave_at > timedelta(days=30):
            raise ValueError("A gate pass can be for at most 30 days; apply for leave instead.")
        return self


class DecisionIn(BaseModel):
    approve: bool
    note: str = Field(default="", max_length=300)


class PassOut(BaseModel):
    id: str
    student_id: str
    full_name: str
    admission_number: str
    batch: str
    hostel: str | None
    reason: str
    leave_at: datetime
    return_by: datetime
    status: str
    note: str
    went_out_at: datetime | None
    returned_at: datetime | None
    late: bool
    created_at: datetime


class VisitorIn(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    phone: str = Field(default="", max_length=15)
    purpose: str = Field(min_length=2, max_length=200)
    to_meet: str = Field(default="", max_length=150)
    id_proof: str = Field(default="", max_length=60)
    vehicle_no: str = Field(default="", max_length=20)

    _strip = field_validator("name", "phone", "purpose", "to_meet", "id_proof", "vehicle_no", mode="before")(_strip)


class VisitorOut(VisitorIn):
    id: str
    in_at: datetime
    out_at: datetime | None


_SELECT = """
    SELECT g.*, s.full_name, s.admission_number, CONCAT(c.name, ' - ', c.section) AS batch,
           (SELECT CONCAT(h.name, ' / ', r.room_number) FROM hostel_allocations a JOIN hostel_rooms r ON r.id = a.room_id
            JOIN hostels h ON h.id = r.hostel_id WHERE a.student_id = s.id AND a.vacated_on IS NULL LIMIT 1) AS hostel
    FROM gate_passes g JOIN students s ON s.id = g.student_id JOIN classes c ON c.id = s.class_id
"""


def _out(row: dict) -> PassOut:
    back = row["returned_at"] or (_now() if row["status"] == "out" else None)
    return PassOut(**{k: row[k] for k in PassOut.model_fields if k in row and k != "late"}, late=bool(back and back > row["return_by"]))


async def _family(student_id: str) -> list[str]:
    rows = await fetch_all("SELECT parent_user_id FROM parent_students WHERE student_id = %s", (student_id,))
    student = await fetch_one("SELECT user_id FROM students WHERE id = %s", (student_id,))
    return [r["parent_user_id"] for r in rows] + ([student["user_id"]] if student and student["user_id"] else [])


async def _get(school_id: str, pass_id: str) -> dict:
    row = await fetch_one(f"{_SELECT} WHERE g.id = %s AND g.school_id = %s", (pass_id, school_id))
    if row is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "pass_not_found", "Gate pass not found.")
    return row


async def request(user: CurrentUser, student: dict, payload: PassIn) -> list[PassOut]:
    if payload.return_by < _now():
        raise AppError(status.HTTP_400_BAD_REQUEST, "past_time", "The return time is already past.")
    open_pass = await fetch_one("SELECT id FROM gate_passes WHERE student_id = %s AND status IN ('pending', 'approved', 'out')", (student["id"],))
    if open_pass:
        raise AppError(status.HTTP_409_CONFLICT, "pass_open", "There's already a pending or active gate pass.")
    await execute(
        "INSERT INTO gate_passes (id, school_id, student_id, requested_by, reason, leave_at, return_by) VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (str(uuid.uuid4()), student["school_id"], student["id"], user.id, payload.reason, payload.leave_at, payload.return_by),
    )
    await notifications.notify(await notifications.admin_user_ids(student["school_id"]), school_id=student["school_id"],
                               title=f"Gate pass request: {student['full_name']}", body=payload.reason, link="gate")
    return await for_student(student["id"])


async def for_student(student_id: str) -> list[PassOut]:
    return [_out(r) for r in await fetch_all(f"{_SELECT} WHERE g.student_id = %s ORDER BY g.created_at DESC, g.id LIMIT 30", (student_id,))]


async def list_passes(user: CurrentUser, status_filter: str | None, day: date | None) -> list[PassOut]:
    where, params = ["g.school_id = %s"], [user.school_id]
    if status_filter == "active":
        where.append("g.status IN ('pending', 'approved', 'out')")
    elif status_filter:
        where.append("g.status = %s")
        params.append(status_filter)
    if day:
        where.append("DATE(g.leave_at) <= %s AND DATE(g.return_by) >= %s")
        params += [day, day]
    rows = await fetch_all(
        f"{_SELECT} WHERE {' AND '.join(where)} ORDER BY FIELD(g.status, 'out', 'pending', 'approved') DESC, g.leave_at DESC LIMIT 300", tuple(params)
    )
    return [_out(r) for r in rows]


async def _tell_family(row: dict, title: str, body: str, school_id: str) -> None:
    await notifications.notify(await _family(row["student_id"]), school_id=school_id, title=title, body=body, link="gate")


async def decide(user: CurrentUser, pass_id: str, payload: DecisionIn) -> PassOut:
    row = await _get(user.school_id, pass_id)
    if row["status"] != "pending":
        raise AppError(status.HTTP_409_CONFLICT, "already_decided", "This gate pass was already handled.")
    if not payload.approve and len(payload.note.strip()) < 3:
        raise AppError(status.HTTP_400_BAD_REQUEST, "note_required", "Give a reason for rejecting.")
    new = "approved" if payload.approve else "rejected"
    await execute("UPDATE gate_passes SET status = %s, note = %s, decided_by = %s WHERE id = %s", (new, payload.note.strip(), user.id, pass_id))
    when = f"{row['leave_at']:%d %b %I:%M %p} to {row['return_by']:%d %b %I:%M %p}"
    await _tell_family(row, f"Gate pass {new}: {row['full_name']}", when if payload.approve else payload.note.strip(), user.school_id)
    return _out(await _get(user.school_id, pass_id))


async def mark_out(user: CurrentUser, pass_id: str) -> PassOut:
    row = await _get(user.school_id, pass_id)
    if row["status"] != "approved":
        raise AppError(status.HTTP_409_CONFLICT, "not_approved", "Only an approved gate pass can be used to go out.")
    now = _now()
    await execute("UPDATE gate_passes SET status = 'out', went_out_at = %s WHERE id = %s", (now, pass_id))
    await _tell_family(row, f"{row['full_name']} left campus", f"At {now:%d %b %I:%M %p}; due back by {row['return_by']:%d %b %I:%M %p}.", user.school_id)
    return _out(await _get(user.school_id, pass_id))


async def mark_returned(user: CurrentUser, pass_id: str) -> PassOut:
    row = await _get(user.school_id, pass_id)
    if row["status"] != "out":
        raise AppError(status.HTTP_409_CONFLICT, "not_out", "This student isn't marked out.")
    now = _now()
    await execute("UPDATE gate_passes SET status = 'returned', returned_at = %s WHERE id = %s", (now, pass_id))
    late = " (late)" if now > row["return_by"] else ""
    await _tell_family(row, f"{row['full_name']} is back on campus{late}", f"Returned at {now:%d %b %I:%M %p}.", user.school_id)
    return _out(await _get(user.school_id, pass_id))


async def cancel(user: CurrentUser, student: dict, pass_id: str) -> list[PassOut]:
    row = await _get(student["school_id"], pass_id)
    if row["student_id"] != student["id"] or row["status"] not in ("pending", "approved"):
        raise AppError(status.HTTP_409_CONFLICT, "cannot_cancel", "Only a pending or approved pass that isn't used yet can be cancelled.")
    await execute("UPDATE gate_passes SET status = 'cancelled' WHERE id = %s", (pass_id,))
    return await for_student(student["id"])


# --- Visitors -----------------------------------------------------------------


async def list_visitors(user: CurrentUser, day: date | None, inside_only: bool) -> list[VisitorOut]:
    where, params = ["school_id = %s"], [user.school_id]
    if inside_only:
        where.append("out_at IS NULL")
    else:
        where.append("DATE(in_at) = %s")
        params.append(day or _now().date())
    rows = await fetch_all(f"SELECT * FROM visitors WHERE {' AND '.join(where)} ORDER BY in_at DESC LIMIT 300", tuple(params))
    return [VisitorOut(**{k: r[k] for k in VisitorOut.model_fields}) for r in rows]


async def add_visitor(user: CurrentUser, payload: VisitorIn) -> VisitorOut:
    visitor_id = str(uuid.uuid4())
    await execute(
        """
        INSERT INTO visitors (id, school_id, name, phone, purpose, to_meet, id_proof, vehicle_no, in_at, created_by)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (visitor_id, user.school_id, payload.name, payload.phone, payload.purpose, payload.to_meet, payload.id_proof, payload.vehicle_no, _now(), user.id),
    )
    row = await fetch_one("SELECT * FROM visitors WHERE id = %s", (visitor_id,))
    return VisitorOut(**{k: row[k] for k in VisitorOut.model_fields})


async def visitor_out(user: CurrentUser, visitor_id: str) -> VisitorOut:
    row = await fetch_one("SELECT * FROM visitors WHERE id = %s AND school_id = %s", (visitor_id, user.school_id))
    if row is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "visitor_not_found", "Visitor not found.")
    if row["out_at"] is None:
        await execute("UPDATE visitors SET out_at = %s WHERE id = %s", (_now(), visitor_id))
        row = await fetch_one("SELECT * FROM visitors WHERE id = %s", (visitor_id,))
    return VisitorOut(**{k: row[k] for k in VisitorOut.model_fields})
