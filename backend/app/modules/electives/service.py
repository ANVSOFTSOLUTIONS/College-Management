"""Electives: a batch's elective slot offers several subjects with limited seats.

The admin creates a slot (e.g. "Professional Elective I") with its subjects,
faculty and seats; each subject is added to the batch's subjects so the
faculty can take attendance and marks. Students pick one subject per slot in
the app while the slot is open, first come first served. Attendance sheets
and exam mark sheets of an elective subject list only the students who chose it.
"""

import uuid

import aiomysql
from fastapi import status
from pydantic import BaseModel, Field, field_validator

from app.api.deps import CurrentUser
from app.core.errors import AppError
from app.db.database import db
from app.db.helpers import execute, fetch_all, fetch_one


class OptionIn(BaseModel):
    subject_id: str
    teacher_id: str
    seats: int = Field(ge=1, le=1000)


class GroupIn(BaseModel):
    class_id: str
    name: str = Field(min_length=1, max_length=100)
    options: list[OptionIn] = Field(min_length=2)

    _strip = field_validator("name", mode="before")(lambda v: v.strip() if isinstance(v, str) else v)


class OpenIn(BaseModel):
    is_open: bool


class ChooseIn(BaseModel):
    option_id: str


class ChosenStudent(BaseModel):
    student_id: str
    full_name: str
    admission_number: str


class OptionOut(BaseModel):
    id: str
    subject_id: str
    subject_name: str
    subject_code: str
    teacher_name: str | None
    seats: int
    taken: int
    students: list[ChosenStudent] = []


class GroupOut(BaseModel):
    id: str
    class_id: str
    name: str
    is_open: bool
    options: list[OptionOut]
    not_chosen: list[ChosenStudent] = []
    my_option_id: str | None = None


def _not_found() -> AppError:
    return AppError(status.HTTP_404_NOT_FOUND, "elective_not_found", "Elective not found.")


async def _options(group_id: str, class_id: str, with_students: bool) -> list[OptionOut]:
    rows = await fetch_all(
        """
        SELECT o.id, o.subject_id, o.seats, s.name AS subject_name, s.code AS subject_code, u.full_name AS teacher_name,
               (SELECT COUNT(*) FROM elective_choices ch WHERE ch.option_id = o.id) AS taken
        FROM elective_options o JOIN subjects s ON s.id = o.subject_id
        LEFT JOIN class_subjects cs ON cs.class_id = %s AND cs.subject_id = o.subject_id
        LEFT JOIN teachers t ON t.id = cs.teacher_id LEFT JOIN users u ON u.id = t.user_id
        WHERE o.group_id = %s ORDER BY s.name
        """,
        (class_id, group_id),
    )
    options = [OptionOut(**r) for r in rows]
    if with_students:
        chosen = await fetch_all(
            """
            SELECT ch.option_id, s.id AS student_id, s.full_name, s.admission_number FROM elective_choices ch
            JOIN students s ON s.id = ch.student_id WHERE ch.group_id = %s ORDER BY s.admission_number
            """,
            (group_id,),
        )
        for option in options:
            option.students = [ChosenStudent(**c) for c in chosen if c["option_id"] == option.id]
    return options


async def _group_out(group: dict, with_students: bool = True) -> GroupOut:
    out = GroupOut(id=group["id"], class_id=group["class_id"], name=group["name"], is_open=bool(group["is_open"]),
                   options=await _options(group["id"], group["class_id"], with_students))
    if with_students:
        rows = await fetch_all(
            """
            SELECT id AS student_id, full_name, admission_number FROM students s
            WHERE s.class_id = %s AND s.status = 'active'
              AND NOT EXISTS (SELECT 1 FROM elective_choices ch WHERE ch.group_id = %s AND ch.student_id = s.id)
            ORDER BY admission_number
            """,
            (group["class_id"], group["id"]),
        )
        out.not_chosen = [ChosenStudent(**r) for r in rows]
    return out


async def _get_group(user: CurrentUser, group_id: str) -> dict:
    group = await fetch_one("SELECT * FROM elective_groups WHERE id = %s AND school_id = %s", (group_id, user.school_id))
    if group is None:
        raise _not_found()
    return group


async def list_groups(user: CurrentUser, class_id: str) -> list[GroupOut]:
    groups = await fetch_all("SELECT * FROM elective_groups WHERE class_id = %s AND school_id = %s ORDER BY name", (class_id, user.school_id))
    return [await _group_out(g) for g in groups]


async def create_group(user: CurrentUser, payload: GroupIn) -> GroupOut:
    if not await fetch_one("SELECT id FROM classes WHERE id = %s AND school_id = %s", (payload.class_id, user.school_id)):
        raise AppError(status.HTTP_404_NOT_FOUND, "class_not_found", "Batch not found.")
    subject_ids = [o.subject_id for o in payload.options]
    if len(set(subject_ids)) != len(subject_ids):
        raise AppError(status.HTTP_400_BAD_REQUEST, "duplicate_subject", "Each subject can be offered once in a slot.")
    for option in payload.options:
        if not await fetch_one("SELECT id FROM subjects WHERE id = %s AND school_id = %s", (option.subject_id, user.school_id)):
            raise AppError(status.HTTP_404_NOT_FOUND, "subject_not_found", "Subject not found.")
        if not await fetch_one("SELECT id FROM teachers WHERE id = %s AND school_id = %s", (option.teacher_id, user.school_id)):
            raise AppError(status.HTTP_404_NOT_FOUND, "teacher_not_found", "Faculty member not found.")
    placeholders = ", ".join(["%s"] * len(subject_ids))
    taken = await fetch_one(
        f"""
        SELECT s.name FROM elective_options o JOIN elective_groups g ON g.id = o.group_id JOIN subjects s ON s.id = o.subject_id
        WHERE g.class_id = %s AND o.subject_id IN ({placeholders})
        """,
        (payload.class_id, *subject_ids),
    )
    if taken:
        raise AppError(status.HTTP_409_CONFLICT, "subject_in_other_slot", f"{taken['name']} is already offered in another elective slot of this batch.")

    group_id = str(uuid.uuid4())
    async with db.pool.acquire() as conn:
        await conn.begin()
        try:
            async with conn.cursor() as cur:
                await cur.execute(
                    "INSERT INTO elective_groups (id, school_id, class_id, name) VALUES (%s, %s, %s, %s)",
                    (group_id, user.school_id, payload.class_id, payload.name),
                )
                for option in payload.options:
                    await cur.execute(
                        "INSERT INTO elective_options (id, group_id, subject_id, seats) VALUES (%s, %s, %s, %s)",
                        (str(uuid.uuid4()), group_id, option.subject_id, option.seats),
                    )
                    await cur.execute(
                        """
                        INSERT INTO class_subjects (id, school_id, class_id, subject_id, teacher_id) VALUES (%s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE teacher_id = VALUES(teacher_id)
                        """,
                        (str(uuid.uuid4()), user.school_id, payload.class_id, option.subject_id, option.teacher_id),
                    )
        except aiomysql.IntegrityError as exc:
            await conn.rollback()
            raise AppError(status.HTTP_409_CONFLICT, "elective_exists", "This batch already has an elective slot with that name.") from exc
        await conn.commit()
    return await _group_out(await _get_group(user, group_id))


async def set_open(user: CurrentUser, group_id: str, is_open: bool) -> GroupOut:
    group = await _get_group(user, group_id)
    await execute("UPDATE elective_groups SET is_open = %s WHERE id = %s", (is_open, group_id))
    group["is_open"] = is_open
    return await _group_out(group)


async def delete_group(user: CurrentUser, group_id: str) -> None:
    await _get_group(user, group_id)
    # The subjects stay with the batch (attendance and marks may exist); only the slot and choices go.
    await execute("DELETE FROM elective_groups WHERE id = %s", (group_id,))


async def assign(user: CurrentUser, group_id: str, student_id: str, option_id: str | None) -> GroupOut:
    """Admin override: put a student in an option (ignores seats and the open flag), or clear the choice."""
    group = await _get_group(user, group_id)
    if not await fetch_one("SELECT id FROM students WHERE id = %s AND class_id = %s", (student_id, group["class_id"])):
        raise AppError(status.HTTP_404_NOT_FOUND, "student_not_found", "Student isn't in this batch.")
    await execute("DELETE FROM elective_choices WHERE group_id = %s AND student_id = %s", (group_id, student_id))
    if option_id:
        if not await fetch_one("SELECT id FROM elective_options WHERE id = %s AND group_id = %s", (option_id, group_id)):
            raise _not_found()
        await execute(
            "INSERT INTO elective_choices (id, group_id, option_id, student_id) VALUES (%s, %s, %s, %s)",
            (str(uuid.uuid4()), group_id, option_id, student_id),
        )
    return await _group_out(group)


# --- Student app ----------------------------------------------------------------


async def student_groups(student: dict) -> list[GroupOut]:
    groups = await fetch_all("SELECT * FROM elective_groups WHERE class_id = %s ORDER BY name", (student["class_id"],))
    result = []
    for g in groups:
        out = await _group_out(g, with_students=False)
        mine = await fetch_one("SELECT option_id FROM elective_choices WHERE group_id = %s AND student_id = %s", (g["id"], student["id"]))
        out.my_option_id = mine["option_id"] if mine else None
        result.append(out)
    return result


async def choose(student: dict, group_id: str, option_id: str) -> list[GroupOut]:
    async with db.pool.acquire() as conn:
        await conn.begin()
        try:
            async with conn.cursor() as cur:
                # Lock the slot so two students can't take the last seat at once.
                await cur.execute("SELECT * FROM elective_groups WHERE id = %s AND class_id = %s FOR UPDATE", (group_id, student["class_id"]))
                group = await cur.fetchone()
                if group is None:
                    raise _not_found()
                if not group["is_open"]:
                    raise AppError(status.HTTP_409_CONFLICT, "elective_closed", "Choices for this elective are closed.")
                await cur.execute("SELECT seats FROM elective_options WHERE id = %s AND group_id = %s", (option_id, group_id))
                option = await cur.fetchone()
                if option is None:
                    raise _not_found()
                await cur.execute(
                    "SELECT COUNT(*) AS n FROM elective_choices WHERE option_id = %s AND student_id <> %s", (option_id, student["id"])
                )
                if (await cur.fetchone())["n"] >= option["seats"]:
                    raise AppError(status.HTTP_409_CONFLICT, "elective_full", "No seats left in this subject. Choose another.")
                await cur.execute("DELETE FROM elective_choices WHERE group_id = %s AND student_id = %s", (group_id, student["id"]))
                await cur.execute(
                    "INSERT INTO elective_choices (id, group_id, option_id, student_id) VALUES (%s, %s, %s, %s)",
                    (str(uuid.uuid4()), group_id, option_id, student["id"]),
                )
        except Exception:
            await conn.rollback()
            raise
        await conn.commit()
    return await student_groups(student)


# --- Used by attendance and exams -----------------------------------------------


async def elective_roster(class_id: str, subject_id: str) -> set[str] | None:
    """Students who chose this subject when it's an elective of the batch; None when it's a core subject."""
    option = await fetch_one(
        "SELECT o.id FROM elective_options o JOIN elective_groups g ON g.id = o.group_id WHERE g.class_id = %s AND o.subject_id = %s",
        (class_id, subject_id),
    )
    if option is None:
        return None
    rows = await fetch_all("SELECT student_id FROM elective_choices WHERE option_id = %s", (option["id"],))
    return {r["student_id"] for r in rows}
