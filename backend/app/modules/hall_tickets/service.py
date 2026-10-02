"""Hall tickets and exam seating.

For an exam the office sets the minimum attendance and the exam rooms. Each
student writing at least one paper (electives and supplementary backlogs
included) gets a hall ticket when their attendance meets the minimum, unless
the office overrides it (condonation, or holding a ticket back). Seats are
assigned room by room, alternating batches so neighbours are from different
batches. Released hall tickets appear in the student app.
"""

import uuid
from datetime import date

from fastapi import status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser
from app.core.errors import AppError
from app.db.database import db
from app.db.helpers import execute, fetch_all, fetch_one
from app.modules.exams.service import _roster


class RoomIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    capacity: int = Field(ge=1, le=1000)


class SettingsIn(BaseModel):
    min_attendance: int | None = Field(default=None, ge=0, le=100)
    released: bool = False


class OverrideIn(BaseModel):
    student_id: str
    allowed: bool | None  # None removes the override


class TicketPaper(BaseModel):
    subject_name: str
    subject_code: str
    exam_date: date | None


class TicketRow(BaseModel):
    student_id: str
    full_name: str
    admission_number: str
    batch: str
    attendance: float | None
    override: bool | None
    eligible: bool
    room: str | None
    seat: int | None
    papers: list[TicketPaper]


class Room(BaseModel):
    name: str
    capacity: int
    seated: int


class HallTicketSheet(BaseModel):
    exam_id: str
    exam_name: str
    college_name: str
    min_attendance: int | None
    released: bool
    rooms: list[Room]
    students: list[TicketRow]
    unseated: int


async def _exam(user_school_id: str, exam_id: str) -> dict:
    exam = await fetch_one("SELECT * FROM exams WHERE id = %s AND school_id = %s", (exam_id, user_school_id))
    if exam is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "exam_not_found", "Exam not found.")
    return exam


async def attendance_percent(student_id: str, class_id: str) -> float | None:
    """Subject-wise attendance in the batch; daily attendance when subjects aren't marked."""
    for table in ("subject_attendance", "attendance"):
        row = await fetch_one(
            f"SELECT COUNT(*) AS held, SUM(status IN ('present', 'late')) AS attended FROM {table} WHERE student_id = %s AND class_id = %s",
            (student_id, class_id),
        )
        if row["held"]:
            return round(int(row["attended"]) * 100 / row["held"], 1)
    return None


async def _build(school_id: str, exam: dict) -> HallTicketSheet:
    papers = await fetch_all(
        """
        SELECT es.*, s.name AS subject_name, s.code AS subject_code FROM exam_subjects es JOIN subjects s ON s.id = es.subject_id
        WHERE es.exam_id = %s ORDER BY es.exam_date IS NULL, es.exam_date, s.name
        """,
        (exam["id"],),
    )
    by_student: dict[str, list[dict]] = {}
    for paper in papers:
        for student_id in await _roster(paper):
            by_student.setdefault(student_id, []).append(paper)
    students = []
    if by_student:
        placeholders = ", ".join(["%s"] * len(by_student))
        students = await fetch_all(
            f"""
            SELECT s.id, s.full_name, s.admission_number, s.class_id, c.name AS class_name, c.section
            FROM students s JOIN classes c ON c.id = s.class_id WHERE s.id IN ({placeholders})
            ORDER BY c.name, c.section, s.admission_number
            """,
            tuple(by_student),
        )
    overrides = {r["student_id"]: bool(r["allowed"]) for r in await fetch_all("SELECT * FROM hall_ticket_overrides WHERE exam_id = %s", (exam["id"],))}
    minimum = exam["hall_ticket_min_attendance"]
    rows = []
    for s in students:
        percent = await attendance_percent(s["id"], s["class_id"])
        override = overrides.get(s["id"])
        meets = minimum is None or percent is None or percent >= minimum
        rows.append(
            TicketRow(
                student_id=s["id"], full_name=s["full_name"], admission_number=s["admission_number"], batch=f"{s['class_name']} - {s['section']}",
                attendance=percent, override=override, eligible=override if override is not None else meets, room=None, seat=None,
                papers=[TicketPaper(subject_name=p["subject_name"], subject_code=p["subject_code"], exam_date=p["exam_date"]) for p in by_student[s["id"]]],
            )
        )

    # Seat eligible students alternating batches: A1, B1, A2, B2 ...
    queues: dict[str, list[TicketRow]] = {}
    for r in rows:
        if r.eligible:
            queues.setdefault(r.batch, []).append(r)
    order = []
    while any(queues.values()):
        for batch in list(queues):
            if queues[batch]:
                order.append(queues[batch].pop(0))
    rooms = await fetch_all("SELECT name, capacity FROM exam_rooms WHERE exam_id = %s ORDER BY position", (exam["id"],))
    room_out, index = [], 0
    for room in rooms:
        seated = order[index:index + room["capacity"]]
        for seat, r in enumerate(seated, start=1):
            r.room, r.seat = room["name"], seat
        index += len(seated)
        room_out.append(Room(name=room["name"], capacity=room["capacity"], seated=len(seated)))
    school = await fetch_one("SELECT name FROM schools WHERE id = %s", (school_id,))
    return HallTicketSheet(
        exam_id=exam["id"], exam_name=exam["name"], college_name=school["name"], min_attendance=minimum, released=bool(exam["hall_tickets_released"]),
        rooms=room_out, students=rows, unseated=len(order) - index,
    )


async def sheet(user: CurrentUser, exam_id: str) -> HallTicketSheet:
    return await _build(user.school_id, await _exam(user.school_id, exam_id))


async def save_settings(user: CurrentUser, exam_id: str, payload: SettingsIn) -> HallTicketSheet:
    await _exam(user.school_id, exam_id)
    await execute(
        "UPDATE exams SET hall_ticket_min_attendance = %s, hall_tickets_released = %s WHERE id = %s", (payload.min_attendance, payload.released, exam_id)
    )
    return await sheet(user, exam_id)


async def save_rooms(user: CurrentUser, exam_id: str, rooms: list[RoomIn]) -> HallTicketSheet:
    await _exam(user.school_id, exam_id)
    names = [r.name.strip().lower() for r in rooms]
    if len(set(names)) != len(names):
        raise AppError(status.HTTP_400_BAD_REQUEST, "duplicate_room", "Each room can be listed once.")
    async with db.pool.acquire() as conn:
        await conn.begin()
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM exam_rooms WHERE exam_id = %s", (exam_id,))
            for position, room in enumerate(rooms):
                await cur.execute(
                    "INSERT INTO exam_rooms (id, exam_id, name, capacity, position) VALUES (%s, %s, %s, %s, %s)",
                    (str(uuid.uuid4()), exam_id, room.name.strip(), room.capacity, position),
                )
        await conn.commit()
    return await sheet(user, exam_id)


async def save_override(user: CurrentUser, exam_id: str, payload: OverrideIn) -> HallTicketSheet:
    await _exam(user.school_id, exam_id)
    if not await fetch_one("SELECT id FROM students WHERE id = %s AND school_id = %s", (payload.student_id, user.school_id)):
        raise AppError(status.HTTP_404_NOT_FOUND, "student_not_found", "Student not found.")
    if payload.allowed is None:
        await execute("DELETE FROM hall_ticket_overrides WHERE exam_id = %s AND student_id = %s", (exam_id, payload.student_id))
    else:
        await execute(
            "INSERT INTO hall_ticket_overrides (exam_id, student_id, allowed) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE allowed = VALUES(allowed)",
            (exam_id, payload.student_id, payload.allowed),
        )
    return await sheet(user, exam_id)


class StudentHallTicket(BaseModel):
    exam_id: str
    exam_name: str
    college_name: str
    full_name: str
    admission_number: str
    batch: str
    eligible: bool
    attendance: float | None
    min_attendance: int | None
    room: str | None
    seat: int | None
    papers: list[TicketPaper]


async def student_tickets(student: dict) -> list[StudentHallTicket]:
    exams = await fetch_all(
        """
        SELECT DISTINCT e.* FROM exams e JOIN exam_subjects es ON es.exam_id = e.id
        WHERE e.school_id = %s AND e.hall_tickets_released = 1 AND e.published_at IS NULL
          AND (es.class_id = %s OR e.exam_type = 'supplementary')
        ORDER BY e.created_at DESC
        """,
        (student["school_id"], student["class_id"]),
    )
    result = []
    for exam in exams:
        built = await _build(student["school_id"], exam)
        mine = next((r for r in built.students if r.student_id == student["id"]), None)
        if mine is None:
            continue
        result.append(
            StudentHallTicket(
                exam_id=exam["id"], exam_name=exam["name"], college_name=built.college_name, full_name=mine.full_name,
                admission_number=mine.admission_number, batch=mine.batch, eligible=mine.eligible, attendance=mine.attendance,
                min_attendance=built.min_attendance, room=mine.room, seat=mine.seat, papers=mine.papers,
            )
        )
    return result
