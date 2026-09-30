import uuid

import aiomysql
from fastapi import status

from app.api.deps import CurrentUser
from app.core.errors import AppError
from app.core.security import student_login_id
from app.db.database import db
from app.db.helpers import fetch_all, fetch_one
from app.modules.students.schemas import (
    ClassRef,
    CreateStudentRequest,
    GuardianIn,
    GuardianOut,
    StudentDetail,
    StudentSummary,
    UpdateStudentRequest,
)

_RELATIONS = ("father", "mother", "guardian")
_STUDENT_FIELDS = ("date_of_birth", "gender", "blood_group", "admission_date", "address", "email", "phone", "quota")

_FORBIDDEN = AppError(status.HTTP_403_FORBIDDEN, "forbidden", "Only this class's class teacher or an admin can do that.")
_NOT_FOUND = AppError(status.HTTP_404_NOT_FOUND, "student_not_found", "Student not found.")
_ADMISSION_TAKEN = AppError(
    status.HTTP_409_CONFLICT, "admission_number_taken", "Another student already has this admission number."
)


# --- Access -------------------------------------------------------------------


async def managed_class_ids(user: CurrentUser) -> set[str] | None:
    """Class ids the user may manage students in; None means every class (admin)."""
    if user.role == "admin":
        return None
    rows = await fetch_all(
        """
        SELECT c.id FROM classes c JOIN teachers t ON t.id = c.teacher_id
        WHERE c.school_id = %s AND t.user_id = %s AND c.is_archived = 0
        """,
        (user.school_id, user.id),
    )
    return {row["id"] for row in rows}


async def _require_class(user: CurrentUser, class_id: str) -> dict:
    row = await fetch_one("SELECT id, name, section FROM classes WHERE school_id = %s AND id = %s", (user.school_id, class_id))
    if row is None:
        raise AppError(status.HTTP_400_BAD_REQUEST, "invalid_class", "Choose a class from this school.")
    allowed = await managed_class_ids(user)
    if allowed is not None and class_id not in allowed:
        raise _FORBIDDEN
    return row


async def get_student_row(user: CurrentUser, student_id: str) -> dict:
    return await _get_student_row(user, student_id)


async def _get_student_row(user: CurrentUser, student_id: str) -> dict:
    row = await fetch_one("SELECT * FROM students WHERE school_id = %s AND id = %s", (user.school_id, student_id))
    if row is None:
        raise _NOT_FOUND
    allowed = await managed_class_ids(user)
    if allowed is not None and row["class_id"] not in allowed:
        # Teachers can't tell whether a student in another class exists.
        raise _NOT_FOUND
    return row


# --- Reads --------------------------------------------------------------------


async def list_students(
    user: CurrentUser, *, class_id: str | None, search: str | None, include_left: bool
) -> list[StudentSummary]:
    allowed = await managed_class_ids(user)
    if class_id is not None and allowed is not None and class_id not in allowed:
        raise _FORBIDDEN
    if allowed is not None and not allowed:
        return []

    where, params = ["s.school_id = %s"], [user.school_id]
    if class_id is not None:
        where.append("s.class_id = %s")
        params.append(class_id)
    elif allowed is not None:
        where.append(f"s.class_id IN ({', '.join(['%s'] * len(allowed))})")
        params.extend(sorted(allowed))
    if not include_left:
        where.append("s.status = 'active'")
    if search:
        where.append("(s.full_name LIKE %s OR s.admission_number LIKE %s)")
        params.extend([f"%{search}%"] * 2)

    rows = await fetch_all(
        f"""
        SELECT s.id, s.admission_number, s.full_name, s.gender, s.status, s.user_id, s.photo_path,
               c.id AS class_id, c.name AS class_name, c.section,
               g.full_name AS contact_name, g.phone AS contact_phone,
               (SELECT COUNT(*) FROM student_documents d WHERE d.student_id = s.id AND d.status = 'pending') AS pending_documents
        FROM students s
        JOIN classes c ON c.id = s.class_id
        LEFT JOIN student_guardians g ON g.student_id = s.id AND g.relation = s.primary_contact
        WHERE {' AND '.join(where)}
        ORDER BY c.name, c.section, s.full_name
        """,
        tuple(params),
    )
    return [
        StudentSummary(
            id=r["id"],
            admission_number=r["admission_number"],
            full_name=r["full_name"],
            gender=r["gender"],
            status=r["status"],
            class_=ClassRef(id=r["class_id"], name=r["class_name"], section=r["section"]),
            primary_contact_name=r["contact_name"] or "",
            primary_contact_phone=r["contact_phone"] or "",
            has_login=r["user_id"] is not None,
            has_photo=bool(r["photo_path"]),
            pending_documents=r["pending_documents"],
        )
        for r in rows
    ]


async def get_student(user: CurrentUser, student_id: str) -> StudentDetail:
    row = await _get_student_row(user, student_id)
    return await _detail(row)


async def _detail(row: dict) -> StudentDetail:
    class_row = await fetch_one("SELECT id, name, section FROM classes WHERE id = %s", (row["class_id"],))
    school = await fetch_one("SELECT code FROM schools WHERE id = %s", (row["school_id"],))
    login = await fetch_one("SELECT status FROM users WHERE id = %s", (row["user_id"],)) if row["user_id"] else None
    guardians = await fetch_all("SELECT * FROM student_guardians WHERE student_id = %s", (row["id"],))
    guardians.sort(key=lambda g: _RELATIONS.index(g["relation"]))
    return StudentDetail(
        id=row["id"],
        admission_number=row["admission_number"],
        full_name=row["full_name"],
        date_of_birth=row["date_of_birth"],
        gender=row["gender"],
        blood_group=row["blood_group"],
        admission_date=row["admission_date"],
        address=row["address"],
        email=row["email"] or "",
        phone=row["phone"] or "",
        quota=row["quota"],
        status=row["status"],
        class_=ClassRef(**class_row),
        primary_contact=row["primary_contact"],
        guardians=[
            GuardianOut(**{k: g[k] for k in ("relation", "relation_label", "full_name", "phone", "email", "occupation")})
            for g in guardians
        ],
        has_photo=bool(row["photo_path"]),
        login_enabled=login is not None and login["status"] == "active",
        school_code=school["code"],
        parent_login_phone=await _parent_login_phone(row["id"]),
    )


async def _parent_login_phone(student_id: str) -> str | None:
    row = await fetch_one(
        """
        SELECT u.login_id FROM parent_students ps JOIN users u ON u.id = ps.parent_user_id
        WHERE ps.student_id = %s AND u.status = 'active' AND u.role = 'parent' LIMIT 1
        """,
        (student_id,),
    )
    return row["login_id"].removeprefix("parent:91") if row else None


# --- Writes -------------------------------------------------------------------


async def _write_guardian(cur, school_id: str, student_id: str, relation: str, guardian: GuardianIn | None) -> None:
    if guardian is None:
        await cur.execute("DELETE FROM student_guardians WHERE student_id = %s AND relation = %s", (student_id, relation))
        return
    await cur.execute(
        """
        INSERT INTO student_guardians (id, school_id, student_id, relation, relation_label, full_name, phone, email, occupation)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE relation_label = VALUES(relation_label), full_name = VALUES(full_name),
            phone = VALUES(phone), email = VALUES(email), occupation = VALUES(occupation)
        """,
        (
            str(uuid.uuid4()),
            school_id,
            student_id,
            relation,
            guardian.relation_label if relation == "guardian" else "",
            guardian.full_name,
            guardian.phone,
            str(guardian.email).lower(),
            guardian.occupation,
        ),
    )


async def _sync_contact_fields(cur, student_id: str) -> None:
    """Keep primary_contact pointing at an existing guardian, and parent_name in step with it."""
    await cur.execute("SELECT primary_contact FROM students WHERE id = %s", (student_id,))
    primary = (await cur.fetchone())["primary_contact"]
    await cur.execute("SELECT relation, full_name FROM student_guardians WHERE student_id = %s", (student_id,))
    names = {row["relation"]: row["full_name"] for row in await cur.fetchall()}
    if primary not in names:
        primary = next((relation for relation in _RELATIONS if relation in names), "")
    await cur.execute(
        "UPDATE students SET primary_contact = %s, parent_name = %s WHERE id = %s",
        (primary, names.get(primary, ""), student_id),
    )


async def _sync_student_login(cur, row: dict, columns: dict) -> None:
    """Keep the student's own login in step: roll number is the sign-in id, and leaving switches it off."""
    if "admission_number" in columns:
        await cur.execute("SELECT code FROM schools WHERE id = %s", (row["school_id"],))
        code = (await cur.fetchone())["code"]
        await cur.execute(
            "UPDATE users SET login_id = %s WHERE id = %s", (student_login_id(code, columns["admission_number"]), row["user_id"])
        )
    if "full_name" in columns:
        await cur.execute("UPDATE users SET full_name = %s WHERE id = %s", (columns["full_name"], row["user_id"]))
    if columns.get("status") in ("left", "graduated"):
        await cur.execute("UPDATE users SET status = 'inactive' WHERE id = %s", (row["user_id"],))


async def insert_student(cur, school_id: str, payload: CreateStudentRequest) -> str:
    """Inserts a student with their guardians on an open cursor (no commit); returns the new id."""
    student_id = str(uuid.uuid4())
    await cur.execute(
        """
        INSERT INTO students (id, school_id, class_id, admission_number, full_name, date_of_birth, gender,
                              blood_group, admission_date, address, primary_contact, email, phone, quota)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            student_id,
            school_id,
            payload.class_id,
            payload.admission_number,
            payload.full_name,
            payload.date_of_birth,
            payload.gender,
            payload.blood_group,
            payload.admission_date,
            payload.address,
            payload.primary_contact,
            str(payload.email).lower() or None,
            payload.phone or None,
            payload.quota,
        ),
    )
    for relation in _RELATIONS:
        if getattr(payload, relation) is not None:
            await _write_guardian(cur, school_id, student_id, relation, getattr(payload, relation))
    await _sync_contact_fields(cur, student_id)
    return student_id


async def create_student(user: CurrentUser, payload: CreateStudentRequest) -> StudentDetail:
    await _require_class(user, payload.class_id)
    async with db.pool.acquire() as conn:
        await conn.begin()
        try:
            async with conn.cursor() as cur:
                student_id = await insert_student(cur, user.school_id, payload)
        except aiomysql.IntegrityError as exc:
            await conn.rollback()
            raise _ADMISSION_TAKEN from exc
        await conn.commit()
    return await get_student(user, student_id)


async def update_student(user: CurrentUser, student_id: str, payload: UpdateStudentRequest) -> StudentDetail:
    row = await _get_student_row(user, student_id)
    await save_profile(row, payload, user)
    return await get_student(user, student_id)


async def save_profile(row: dict, payload, user: CurrentUser) -> None:
    """Apply a staff member's partial update."""
    student_id = row["id"]
    updates = payload.model_dump(exclude_unset=True)
    if updates.get("status") and user.role != "admin":
        raise AppError(status.HTTP_403_FORBIDDEN, "forbidden", "Only an admin can change a student's status.")
    if updates.get("class_id"):
        await _require_class(user, updates["class_id"])

    columns = {
        field: updates[field]
        for field in ("admission_number", "full_name", "class_id", "status", "primary_contact", *_STUDENT_FIELDS)
        if field in updates and (updates[field] is not None or field in ("date_of_birth", "admission_date"))
    }
    async with db.pool.acquire() as conn:
        await conn.begin()
        try:
            async with conn.cursor() as cur:
                if columns:
                    if "email" in columns:
                        columns["email"] = str(columns["email"]).lower() or None
                    sets = ", ".join(f"{field} = %s" for field in columns)
                    await cur.execute(f"UPDATE students SET {sets} WHERE id = %s", (*columns.values(), student_id))
                if row["user_id"]:
                    await _sync_student_login(cur, row, columns)
                for relation in _RELATIONS:
                    if relation in updates:
                        await _write_guardian(cur, row["school_id"], student_id, relation, getattr(payload, relation))
                await _sync_contact_fields(cur, student_id)
        except aiomysql.IntegrityError as exc:
            await conn.rollback()
            raise _ADMISSION_TAKEN from exc
        await conn.commit()
