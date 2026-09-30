"""Leave requests.

- A teacher applies; admins are notified and one approves or rejects. An
  approved teacher leave marks those weekdays 'leave' in staff attendance.
- A parent applies for their child; the class teacher is notified and approves
  or rejects (admins can too). On an approved leave day the attendance sheet
  shows the student as on leave and no absence alert goes to the parent.
- The applicant is notified of the decision.
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from fastapi import status
from pydantic import BaseModel, Field, field_validator, model_validator

from app.api.deps import CurrentUser
from app.core.errors import AppError
from app.db.database import db
from app.db.helpers import execute, fetch_all, fetch_one
from app.modules.alerts.service import today_ist
from app.modules.notifications import service as notifications

LeaveType = Literal["sick", "casual", "family", "other"]
LEAVE_LABELS = {"sick": "Sick leave", "casual": "Casual leave", "family": "Family function", "other": "Other"}
MAX_DAYS = 60
MAX_DAYS_BACK = 30


class ApplyLeaveRequest(BaseModel):
    student_id: str | None = None  # a parent says which child
    leave_type: LeaveType
    from_date: date
    to_date: date
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("reason", mode="before")
    @classmethod
    def _strip(cls, value):
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def _dates(self):
        if self.to_date < self.from_date:
            raise ValueError("The leave can't end before it starts.")
        if (self.to_date - self.from_date).days + 1 > MAX_DAYS:
            raise ValueError(f"A single leave can be at most {MAX_DAYS} days.")
        return self


class ReviewLeaveRequest(BaseModel):
    status: Literal["approved", "rejected"]
    note: str = Field(default="", max_length=300)


class LeaveOut(BaseModel):
    id: str
    applicant_name: str  # the student's name for a student's leave, even when a parent applied
    applicant_kind: Literal["teacher", "student"]
    applied_by_parent: bool = False
    student_id: str | None = None
    class_name: str | None
    admission_number: str | None
    leave_type: LeaveType
    leave_type_label: str
    from_date: date
    to_date: date
    days: int
    reason: str
    status: str
    review_note: str
    reviewer_name: str | None
    created_at: str
    can_review: bool
    can_cancel: bool


_SELECT = """
    SELECT l.*, COALESCE(s.full_name, u.full_name) AS applicant_name, u.role AS applicant_role, r.full_name AS reviewer_name,
           c.name AS class_name, c.section, c.teacher_id AS class_teacher_id, s.admission_number,
           apt.department_id AS applicant_department_id
    FROM leave_requests l
    JOIN users u ON u.id = l.applicant_user_id
    LEFT JOIN teachers apt ON apt.id = l.teacher_id
    LEFT JOIN users r ON r.id = l.reviewer_id
    LEFT JOIN classes c ON c.id = l.class_id
    LEFT JOIN students s ON s.id = l.student_id
"""


async def _teacher_id(user: CurrentUser) -> str | None:
    row = await fetch_one("SELECT id FROM teachers WHERE user_id = %s AND school_id = %s", (user.id, user.school_id))
    return row["id"] if row else None


async def _hod_departments(teacher_id: str | None) -> frozenset[str]:
    """Departments the faculty member heads."""
    if teacher_id is None:
        return frozenset()
    rows = await fetch_all("SELECT id FROM departments WHERE hod_teacher_id = %s", (teacher_id,))
    return frozenset(r["id"] for r in rows)


def _can_review(user: CurrentUser, teacher_id: str | None, row: dict, hod_of: frozenset[str] = frozenset()) -> bool:
    if row["status"] != "pending" or row["applicant_user_id"] == user.id:
        return False
    if user.role == "admin":
        return True
    # Class teachers review their own students' leave; a HOD reviews their department's faculty; other staff leave is for admins.
    if row["student_id"] is not None:
        return teacher_id is not None and row["class_teacher_id"] == teacher_id
    return row["applicant_department_id"] in hod_of


def _out(row: dict, user: CurrentUser, teacher_id: str | None, hod_of: frozenset[str] = frozenset()) -> LeaveOut:
    return LeaveOut(
        id=row["id"],
        applicant_name=row["applicant_name"],
        applicant_kind="student" if row["student_id"] else "teacher",
        applied_by_parent=row["applicant_role"] == "parent",
        student_id=row["student_id"],
        class_name=f"{row['class_name']} - {row['section']}" if row["class_name"] else None,
        admission_number=row["admission_number"],
        leave_type=row["leave_type"],
        leave_type_label=LEAVE_LABELS[row["leave_type"]],
        from_date=row["from_date"],
        to_date=row["to_date"],
        days=(row["to_date"] - row["from_date"]).days + 1,
        reason=row["reason"],
        status=row["status"],
        review_note=row["review_note"],
        reviewer_name=row["reviewer_name"],
        created_at=row["created_at"].isoformat(),
        can_review=_can_review(user, teacher_id, row, hod_of),
        can_cancel=row["applicant_user_id"] == user.id and row["status"] == "pending",
    )


def _range(start: date, end: date) -> str:
    return f"{start:%d %b}" if start == end else f"{start:%d %b} to {end:%d %b %Y}"


async def apply(user: CurrentUser, payload: ApplyLeaveRequest) -> LeaveOut:
    if payload.from_date < today_ist() - timedelta(days=MAX_DAYS_BACK):
        raise AppError(status.HTTP_400_BAD_REQUEST, "too_far_back", f"Leave can be applied up to {MAX_DAYS_BACK} days back.")

    teacher_id = student = None
    if user.role == "teacher":
        teacher_id = await _teacher_id(user)
        if teacher_id is None:
            raise AppError(status.HTTP_403_FORBIDDEN, "forbidden", "Only staff and students apply for leave here.")
    elif user.role in ("parent", "student"):
        student = await fetch_one(
            """
            SELECT s.* FROM parent_students ps JOIN students s ON s.id = ps.student_id
            WHERE ps.parent_user_id = %s AND s.id = %s AND s.status = 'active'
            """,
            (user.id, payload.student_id or ""),
        )
        if student is None:
            raise AppError(status.HTTP_404_NOT_FOUND, "child_not_found", "Choose your child.")
    else:
        raise AppError(status.HTTP_403_FORBIDDEN, "forbidden", "Only staff and students apply for leave here.")
    # A parent has no school of their own; the child's school is used.
    school_id = student["school_id"] if student else user.school_id

    # Overlaps are per student (a parent may apply for two children), or per teacher.
    who, who_id = ("student_id", student["id"]) if student else ("applicant_user_id", user.id)
    overlap = await fetch_one(
        f"""
        SELECT id FROM leave_requests WHERE {who} = %s AND status IN ('pending', 'approved')
          AND from_date <= %s AND to_date >= %s LIMIT 1
        """,
        (who_id, payload.to_date, payload.from_date),
    )
    if overlap:
        raise AppError(status.HTTP_409_CONFLICT, "leave_overlaps", "You already have a leave request for some of these dates.")

    leave_id = str(uuid.uuid4())
    await execute(
        """
        INSERT INTO leave_requests (id, school_id, applicant_user_id, teacher_id, student_id, class_id, leave_type, from_date, to_date, reason)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (leave_id, school_id, user.id, teacher_id, student["id"] if student else None, student["class_id"] if student else None,
         payload.leave_type, payload.from_date, payload.to_date, payload.reason),
    )

    when = _range(payload.from_date, payload.to_date)
    if student:
        class_teacher = await fetch_one(
            "SELECT t.user_id FROM classes c JOIN teachers t ON t.id = c.teacher_id WHERE c.id = %s", (student["class_id"],)
        )
        await notifications.notify(
            [class_teacher["user_id"]] if class_teacher else [],
            school_id=school_id,
            title=f"Leave request: {student['full_name']}" + {"parent": " (from parent)", "student": " (from student)"}.get(user.role, ""),
            body=f"{LEAVE_LABELS[payload.leave_type]}, {when}. {payload.reason}",
            link="leave",
        )
    else:
        hod = await fetch_one(
            """
            SELECT h.user_id FROM teachers t JOIN departments d ON d.id = t.department_id JOIN teachers h ON h.id = d.hod_teacher_id
            WHERE t.id = %s AND h.user_id <> %s
            """,
            (teacher_id, user.id),
        )
        await notifications.notify(
            await notifications.admin_user_ids(user.school_id) + ([hod["user_id"]] if hod else []),
            school_id=user.school_id,
            title=f"Staff leave request: {user.full_name}",
            body=f"{LEAVE_LABELS[payload.leave_type]}, {when}. {payload.reason}",
            link="leave",
        )
    return await _get(user, leave_id)


async def _get(user: CurrentUser, leave_id: str) -> LeaveOut:
    # Parents have no school_id; they see only the requests they made.
    row = await fetch_one(
        f"{_SELECT} WHERE l.id = %s AND (l.school_id = %s OR l.applicant_user_id = %s)", (leave_id, user.school_id, user.id)
    )
    if row is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "leave_not_found", "Leave request not found.")
    teacher_id = await _teacher_id(user) if user.role == "teacher" else None
    return _out(row, user, teacher_id, await _hod_departments(teacher_id))


async def my_leaves(user: CurrentUser) -> list[LeaveOut]:
    rows = await fetch_all(f"{_SELECT} WHERE l.applicant_user_id = %s ORDER BY l.from_date DESC, l.created_at DESC", (user.id,))
    teacher_id = await _teacher_id(user) if user.role == "teacher" else None
    return [_out(r, user, teacher_id) for r in rows]


async def inbox(user: CurrentUser, *, only_pending: bool) -> list[LeaveOut]:
    """Requests the user reviews: admins see all; a class teacher their students'; a HOD also their department's faculty."""
    where, params = ["l.school_id = %s", "l.applicant_user_id <> %s"], [user.school_id, user.id]
    teacher_id, hod_of = None, frozenset()
    if user.role == "teacher":
        teacher_id = await _teacher_id(user)
        hod_of = await _hod_departments(teacher_id)
        mine = "(l.student_id IS NOT NULL AND c.teacher_id = %s)"
        params.append(teacher_id)
        if hod_of:
            mine = f"({mine} OR (l.teacher_id IS NOT NULL AND apt.department_id IN ({', '.join(['%s'] * len(hod_of))})))"
            params.extend(sorted(hod_of))
        where.append(mine)
    if only_pending:
        where.append("l.status = 'pending'")
    rows = await fetch_all(
        f"{_SELECT} WHERE {' AND '.join(where)} ORDER BY l.status = 'pending' DESC, l.from_date DESC LIMIT 300", tuple(params)
    )
    return [_out(r, user, teacher_id, hod_of) for r in rows]


async def cancel(user: CurrentUser, leave_id: str) -> LeaveOut:
    leave = await _get(user, leave_id)
    if not leave.can_cancel:
        raise AppError(status.HTTP_409_CONFLICT, "not_cancellable", "Only your own pending request can be cancelled.")
    await execute("UPDATE leave_requests SET status = 'cancelled' WHERE id = %s", (leave_id,))
    return await _get(user, leave_id)


async def review(user: CurrentUser, leave_id: str, payload: ReviewLeaveRequest) -> LeaveOut:
    row = await fetch_one(f"{_SELECT} WHERE l.id = %s AND l.school_id = %s", (leave_id, user.school_id))
    if row is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "leave_not_found", "Leave request not found.")
    teacher_id = await _teacher_id(user) if user.role == "teacher" else None
    if not _can_review(user, teacher_id, row, await _hod_departments(teacher_id)):
        if row["status"] != "pending":
            raise AppError(status.HTTP_409_CONFLICT, "already_reviewed", "This request was already handled.")
        raise AppError(status.HTTP_403_FORBIDDEN, "forbidden", "You can't review this request.")
    if payload.status == "rejected" and not payload.note.strip():
        raise AppError(status.HTTP_400_BAD_REQUEST, "note_required", "Give a reason for rejecting.")

    await execute(
        "UPDATE leave_requests SET status = %s, reviewer_id = %s, review_note = %s, reviewed_at = %s WHERE id = %s",
        (payload.status, user.id, payload.note.strip(), datetime.now(timezone.utc), leave_id),
    )
    when = _range(row["from_date"], row["to_date"])
    decision = "approved" if payload.status == "approved" else "rejected"
    await notifications.notify(
        [row["applicant_user_id"]],
        school_id=user.school_id,
        title=f"Your leave was {decision}",
        body=f"{LEAVE_LABELS[row['leave_type']]}, {when}." + (f" Note: {payload.note.strip()}" if payload.note.strip() else ""),
        link="leave",
    )
    if payload.status == "approved" and row["teacher_id"]:
        await _apply_teacher_leave(user, row, when)
    return await _get(user, leave_id)


async def _apply_teacher_leave(user: CurrentUser, row: dict, when: str) -> None:
    # Weekdays in the range become 'leave' in staff attendance.
    day, marks = row["from_date"], []
    while day <= row["to_date"]:
        if day.weekday() < 5:
            marks.append((str(uuid.uuid4()), row["school_id"], row["teacher_id"], day, "leave", user.id))
        day += timedelta(days=1)
    if marks:
        async with db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.executemany(
                    """
                    INSERT INTO staff_attendance (id, school_id, teacher_id, attendance_date, status, marked_by)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE status = VALUES(status), marked_by = VALUES(marked_by)
                    """,
                    marks,
                )


async def students_on_leave(class_id: str, day: date) -> set[str]:
    rows = await fetch_all(
        """
        SELECT student_id FROM leave_requests
        WHERE class_id = %s AND student_id IS NOT NULL AND status = 'approved' AND %s BETWEEN from_date AND to_date
        """,
        (class_id, day),
    )
    return {r["student_id"] for r in rows}
