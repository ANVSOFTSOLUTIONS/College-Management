import uuid

import aiomysql
from fastapi import status

from app.core.errors import AppError
from app.core.security import hash_password
from app.db.database import db
from app.db.helpers import execute, fetch_all, fetch_one
from app.modules.academics.schemas import (
    AssignSubjectTeacherRequest,
    ClassDetail,
    ClassRef,
    ClassSubjectOut,
    CreateClassRequest,
    CreateTeacherRequest,
    DepartmentOut,
    DepartmentRequest,
    SubjectOut,
    SubjectRequest,
    TeacherOut,
    TeacherRef,
    TeacherSubjectRef,
    UpdateClassRequest,
    UpdateTeacherRequest,
)

_TEACHER_SELECT = """
    SELECT t.id, t.department, t.designation, t.department_id, t.employee_code, t.phone, t.qualification, t.joined_on,
           u.id AS user_id, u.email, u.full_name, u.status
    FROM teachers t JOIN users u ON u.id = t.user_id
"""


def _not_found(what: str) -> AppError:
    return AppError(status.HTTP_404_NOT_FOUND, f"{what}_not_found", f"{what.capitalize()} not found.")


# --- Teachers -----------------------------------------------------------------


async def _build_teachers(school_id: str, rows: list[dict]) -> list[TeacherOut]:
    if not rows:
        return []
    ids = tuple(row["id"] for row in rows)
    placeholders = ", ".join(["%s"] * len(ids))
    class_rows = await fetch_all(
        f"SELECT id, name, section, teacher_id FROM classes WHERE school_id = %s AND teacher_id IN ({placeholders}) ORDER BY name, section",
        (school_id, *ids),
    )
    subject_rows = await fetch_all(
        f"""
        SELECT cs.teacher_id, c.id AS class_id, c.name AS class_name, c.section, s.id AS subject_id, s.name AS subject_name
        FROM class_subjects cs
        JOIN classes c ON c.id = cs.class_id
        JOIN subjects s ON s.id = cs.subject_id
        WHERE cs.school_id = %s AND cs.teacher_id IN ({placeholders})
        ORDER BY c.name, c.section, s.name
        """,
        (school_id, *ids),
    )
    return [
        TeacherOut(
            id=row["id"],
            email=row["email"],
            full_name=row["full_name"],
            phone=row["phone"],
            department=row["department"],
            designation=row["designation"],
            department_id=row["department_id"],
            qualification=row["qualification"],
            employee_code=row["employee_code"],
            joined_on=row["joined_on"],
            status=row["status"],
            class_teacher_of=[
                ClassRef(id=c["id"], name=c["name"], section=c["section"]) for c in class_rows if c["teacher_id"] == row["id"]
            ],
            subjects=[
                TeacherSubjectRef(**{k: s[k] for k in ("class_id", "class_name", "section", "subject_id", "subject_name")})
                for s in subject_rows
                if s["teacher_id"] == row["id"]
            ],
        )
        for row in rows
    ]


async def list_teachers(school_id: str) -> list[TeacherOut]:
    rows = await fetch_all(f"{_TEACHER_SELECT} WHERE t.school_id = %s ORDER BY u.status, u.full_name", (school_id,))
    return await _build_teachers(school_id, rows)


async def _get_teacher_row(school_id: str, teacher_id: str) -> dict:
    row = await fetch_one(f"{_TEACHER_SELECT} WHERE t.school_id = %s AND t.id = %s", (school_id, teacher_id))
    if row is None:
        raise _not_found("teacher")
    return row


async def get_teacher(school_id: str, teacher_id: str) -> TeacherOut:
    return (await _build_teachers(school_id, [await _get_teacher_row(school_id, teacher_id)]))[0]


def _duplicate_teacher_error(exc: aiomysql.IntegrityError) -> AppError:
    if "employee_code" in str(exc):
        return AppError(status.HTTP_409_CONFLICT, "employee_code_taken", "Another teacher already has this employee code.")
    return AppError(status.HTTP_409_CONFLICT, "email_taken", "That email is already in use.")


async def create_teacher(school_id: str, payload: CreateTeacherRequest) -> TeacherOut:
    department = await _department_name(school_id, payload.department_id)
    user_id, teacher_id = str(uuid.uuid4()), str(uuid.uuid4())
    async with db.pool.acquire() as conn:
        await conn.begin()
        try:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO users (id, school_id, email, password_hash, role, full_name, status)
                    VALUES (%s, %s, %s, %s, 'teacher', %s, 'active')
                    """,
                    (user_id, school_id, payload.email.lower(), hash_password(payload.password), payload.full_name),
                )
                await cur.execute(
                    """
                    INSERT INTO teachers (id, school_id, user_id, department, designation, department_id, employee_code,
                                          phone, qualification, joined_on)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        teacher_id,
                        school_id,
                        user_id,
                        department or payload.department,
                        payload.designation,
                        payload.department_id,
                        payload.employee_code or None,
                        payload.phone,
                        payload.qualification,
                        payload.joined_on,
                    ),
                )
        except aiomysql.IntegrityError as exc:
            await conn.rollback()
            raise _duplicate_teacher_error(exc) from exc
        await conn.commit()
    return await get_teacher(school_id, teacher_id)


async def update_teacher(school_id: str, teacher_id: str, payload: UpdateTeacherRequest) -> TeacherOut:
    row = await _get_teacher_row(school_id, teacher_id)
    updates = payload.model_dump(exclude_unset=True)
    if updates.get("department_id"):
        updates["department"] = await _department_name(school_id, updates["department_id"])

    user_updates = {}
    for field in ("email", "full_name", "status"):
        if updates.get(field) is not None:
            user_updates[field] = updates[field].lower() if field == "email" else updates[field]
    if updates.get("password"):
        user_updates["password_hash"] = hash_password(updates["password"])
    teacher_updates = {
        field: (updates[field] or None) if field == "employee_code" else updates[field]
        for field in ("department", "designation", "department_id", "employee_code", "phone", "qualification", "joined_on")
        if field in updates and (updates[field] is not None or field in ("employee_code", "joined_on", "department_id"))
    }

    deactivating = user_updates.get("status") == "inactive" and row["status"] == "active"
    if deactivating:
        classes = await fetch_all(
            "SELECT name, section FROM classes WHERE school_id = %s AND teacher_id = %s ORDER BY name, section",
            (school_id, teacher_id),
        )
        if classes:
            names = ", ".join(f"{c['name']} - {c['section']}" for c in classes)
            raise AppError(
                status.HTTP_409_CONFLICT,
                "teacher_is_class_teacher",
                f"Assign another class teacher to {names} before removing this teacher.",
            )

    async with db.pool.acquire() as conn:
        await conn.begin()
        try:
            async with conn.cursor() as cur:
                if user_updates:
                    sets = ", ".join(f"{field} = %s" for field in user_updates)
                    await cur.execute(f"UPDATE users SET {sets} WHERE id = %s", (*user_updates.values(), row["user_id"]))
                if teacher_updates:
                    sets = ", ".join(f"{field} = %s" for field in teacher_updates)
                    await cur.execute(f"UPDATE teachers SET {sets} WHERE id = %s", (*teacher_updates.values(), teacher_id))
                if deactivating:
                    # A removed teacher no longer teaches any subject.
                    await cur.execute("DELETE FROM class_subjects WHERE teacher_id = %s", (teacher_id,))
        except aiomysql.IntegrityError as exc:
            await conn.rollback()
            raise _duplicate_teacher_error(exc) from exc
        await conn.commit()
    return await get_teacher(school_id, teacher_id)


async def _require_active_teacher(school_id: str, teacher_id: str) -> dict:
    row = await fetch_one(f"{_TEACHER_SELECT} WHERE t.school_id = %s AND t.id = %s", (school_id, teacher_id))
    if row is None or row["status"] != "active":
        raise AppError(status.HTTP_400_BAD_REQUEST, "invalid_teacher", "Choose an active teacher from this school.")
    return row


# --- Subjects -----------------------------------------------------------------


def _to_subject(row: dict) -> SubjectOut:
    return SubjectOut(
        id=row["id"],
        name=row["name"],
        code=row["code"],
        credits=float(row["credits"]),
        subject_type=row["subject_type"],
        department_id=row["department_id"],
        semester=row["semester"],
    )


async def list_subjects(school_id: str) -> list[SubjectOut]:
    rows = await fetch_all("SELECT * FROM subjects WHERE school_id = %s ORDER BY name", (school_id,))
    return [_to_subject(row) for row in rows]


async def _get_subject_row(school_id: str, subject_id: str) -> dict:
    row = await fetch_one("SELECT * FROM subjects WHERE school_id = %s AND id = %s", (school_id, subject_id))
    if row is None:
        raise _not_found("subject")
    return row


_SUBJECT_TAKEN = AppError(status.HTTP_409_CONFLICT, "subject_exists", "A subject with this name already exists.")


async def create_subject(school_id: str, payload: SubjectRequest) -> SubjectOut:
    await _department_name(school_id, payload.department_id)
    subject_id = str(uuid.uuid4())
    try:
        await execute(
            """
            INSERT INTO subjects (id, school_id, name, code, credits, subject_type, department_id, semester)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (subject_id, school_id, payload.name, payload.code, payload.credits, payload.subject_type,
             payload.department_id, payload.semester),
        )
    except aiomysql.IntegrityError as exc:
        raise _SUBJECT_TAKEN from exc
    return _to_subject(await _get_subject_row(school_id, subject_id))


async def update_subject(school_id: str, subject_id: str, payload: SubjectRequest) -> SubjectOut:
    await _get_subject_row(school_id, subject_id)
    await _department_name(school_id, payload.department_id)
    try:
        await execute(
            """
            UPDATE subjects SET name = %s, code = %s, credits = %s, subject_type = %s, department_id = %s, semester = %s
            WHERE id = %s
            """,
            (payload.name, payload.code, payload.credits, payload.subject_type, payload.department_id, payload.semester,
             subject_id),
        )
    except aiomysql.IntegrityError as exc:
        raise _SUBJECT_TAKEN from exc
    return _to_subject(await _get_subject_row(school_id, subject_id))


async def delete_subject(school_id: str, subject_id: str) -> None:
    await _get_subject_row(school_id, subject_id)
    await execute("DELETE FROM subjects WHERE id = %s", (subject_id,))


# --- Classes ------------------------------------------------------------------


async def _get_class_row(school_id: str, class_id: str) -> dict:
    row = await fetch_one("SELECT * FROM classes WHERE school_id = %s AND id = %s", (school_id, class_id))
    if row is None:
        raise _not_found("class")
    return row


async def get_class(school_id: str, class_id: str) -> ClassDetail:
    row = await _get_class_row(school_id, class_id)
    teacher = await fetch_one(f"{_TEACHER_SELECT} WHERE t.id = %s", (row["teacher_id"],))
    count = await fetch_one("SELECT COUNT(*) AS n FROM students WHERE class_id = %s AND status = 'active'", (class_id,))
    subjects = await fetch_all(
        """
        SELECT s.id AS subject_id, s.name AS subject_name, s.credits, t.id AS teacher_id, u.full_name AS teacher_name
        FROM class_subjects cs
        JOIN subjects s ON s.id = cs.subject_id
        JOIN teachers t ON t.id = cs.teacher_id
        JOIN users u ON u.id = t.user_id
        WHERE cs.class_id = %s
        ORDER BY s.name
        """,
        (class_id,),
    )
    department = None
    if row["department_id"]:
        department = await fetch_one("SELECT name FROM departments WHERE id = %s", (row["department_id"],))
    return ClassDetail(
        department_id=row["department_id"],
        department_name=department["name"] if department else None,
        program=row["program"],
        semester=row["semester"],
        regulation=row["regulation"],
        id=row["id"],
        name=row["name"],
        section=row["section"],
        academic_year=row["academic_year"],
        class_teacher=TeacherRef(id=teacher["id"], full_name=teacher["full_name"]),
        student_count=count["n"],
        subjects=[
            ClassSubjectOut(
                subject_id=s["subject_id"],
                subject_name=s["subject_name"],
                teacher=TeacherRef(id=s["teacher_id"], full_name=s["teacher_name"]),
                credits=float(s["credits"]),
            )
            for s in subjects
        ],
    )


_CLASS_TAKEN = AppError(
    status.HTTP_409_CONFLICT, "class_exists", "This class and section already exist for that academic year."
)


async def create_class(school_id: str, payload: CreateClassRequest) -> ClassDetail:
    await _require_active_teacher(school_id, payload.class_teacher_id)
    await _department_name(school_id, payload.department_id)
    class_id = str(uuid.uuid4())
    try:
        await execute(
            """
            INSERT INTO classes (id, school_id, teacher_id, department_id, program, name, section, semester, regulation,
                                 academic_year)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (class_id, school_id, payload.class_teacher_id, payload.department_id, payload.program, payload.name,
             payload.section, payload.semester, payload.regulation, payload.academic_year),
        )
    except aiomysql.IntegrityError as exc:
        raise _CLASS_TAKEN from exc
    return await get_class(school_id, class_id)


async def update_class(school_id: str, class_id: str, payload: UpdateClassRequest) -> ClassDetail:
    await _get_class_row(school_id, class_id)
    updates = payload.model_dump(exclude_unset=True, exclude_none=True)
    if "class_teacher_id" in updates:
        await _require_active_teacher(school_id, updates["class_teacher_id"])
        updates["teacher_id"] = updates.pop("class_teacher_id")
    if "department_id" in updates:
        await _department_name(school_id, updates["department_id"])
    if updates:
        sets = ", ".join(f"{field} = %s" for field in updates)
        try:
            await execute(f"UPDATE classes SET {sets} WHERE id = %s", (*updates.values(), class_id))
        except aiomysql.IntegrityError as exc:
            raise _CLASS_TAKEN from exc
    return await get_class(school_id, class_id)


async def delete_class(school_id: str, class_id: str) -> None:
    await _get_class_row(school_id, class_id)
    count = await fetch_one("SELECT COUNT(*) AS n FROM students WHERE class_id = %s", (class_id,))
    if count["n"]:
        raise AppError(
            status.HTTP_409_CONFLICT,
            "class_has_students",
            f"This class has {count['n']} student(s). Move or remove them before deleting the class.",
        )
    await execute("DELETE FROM classes WHERE id = %s", (class_id,))


async def assign_subject_teacher(
    school_id: str, class_id: str, subject_id: str, payload: AssignSubjectTeacherRequest
) -> ClassDetail:
    await _get_class_row(school_id, class_id)
    await _get_subject_row(school_id, subject_id)
    await _require_active_teacher(school_id, payload.teacher_id)
    await execute(
        """
        INSERT INTO class_subjects (id, school_id, class_id, subject_id, teacher_id)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE teacher_id = VALUES(teacher_id)
        """,
        (str(uuid.uuid4()), school_id, class_id, subject_id, payload.teacher_id),
    )
    return await get_class(school_id, class_id)


async def unassign_subject(school_id: str, class_id: str, subject_id: str) -> ClassDetail:
    await _get_class_row(school_id, class_id)
    await execute("DELETE FROM class_subjects WHERE class_id = %s AND subject_id = %s", (class_id, subject_id))
    return await get_class(school_id, class_id)


# --- Departments --------------------------------------------------------------


async def _department_name(school_id: str, department_id: str | None) -> str | None:
    """The department's name, after checking it belongs to this college; None when no department is given."""
    if not department_id:
        return None
    row = await fetch_one("SELECT name FROM departments WHERE school_id = %s AND id = %s", (school_id, department_id))
    if row is None:
        raise AppError(status.HTTP_400_BAD_REQUEST, "invalid_department", "Choose a department of this college.")
    return row["name"]


_DEPARTMENT_SELECT = """
    SELECT d.id, d.name, d.code, d.hod_teacher_id, u.full_name AS hod_name,
           (SELECT COUNT(*) FROM teachers t JOIN users tu ON tu.id = t.user_id
             WHERE t.department_id = d.id AND tu.status = 'active') AS faculty_count,
           (SELECT COUNT(*) FROM classes c WHERE c.department_id = d.id AND c.is_archived = 0) AS class_count,
           (SELECT COUNT(*) FROM students s JOIN classes c ON c.id = s.class_id
             WHERE c.department_id = d.id AND s.status = 'active') AS student_count
    FROM departments d
    LEFT JOIN teachers h ON h.id = d.hod_teacher_id
    LEFT JOIN users u ON u.id = h.user_id
"""


def _to_department(row: dict) -> DepartmentOut:
    return DepartmentOut(
        id=row["id"],
        name=row["name"],
        code=row["code"],
        hod=TeacherRef(id=row["hod_teacher_id"], full_name=row["hod_name"]) if row["hod_teacher_id"] else None,
        faculty_count=row["faculty_count"],
        class_count=row["class_count"],
        student_count=row["student_count"],
    )


async def list_departments(school_id: str) -> list[DepartmentOut]:
    rows = await fetch_all(f"{_DEPARTMENT_SELECT} WHERE d.school_id = %s ORDER BY d.name", (school_id,))
    return [_to_department(row) for row in rows]


async def get_department(school_id: str, department_id: str) -> DepartmentOut:
    row = await fetch_one(f"{_DEPARTMENT_SELECT} WHERE d.school_id = %s AND d.id = %s", (school_id, department_id))
    if row is None:
        raise _not_found("department")
    return _to_department(row)


_DEPARTMENT_TAKEN = AppError(status.HTTP_409_CONFLICT, "department_exists", "A department with this code already exists.")


async def create_department(school_id: str, payload: DepartmentRequest) -> DepartmentOut:
    if payload.hod_teacher_id:
        await _require_active_teacher(school_id, payload.hod_teacher_id)
    department_id = str(uuid.uuid4())
    try:
        await execute(
            "INSERT INTO departments (id, school_id, name, code, hod_teacher_id) VALUES (%s, %s, %s, %s, %s)",
            (department_id, school_id, payload.name, payload.code.upper(), payload.hod_teacher_id),
        )
    except aiomysql.IntegrityError as exc:
        raise _DEPARTMENT_TAKEN from exc
    return await get_department(school_id, department_id)


async def update_department(school_id: str, department_id: str, payload: DepartmentRequest) -> DepartmentOut:
    await get_department(school_id, department_id)
    if payload.hod_teacher_id:
        await _require_active_teacher(school_id, payload.hod_teacher_id)
    try:
        await execute(
            "UPDATE departments SET name = %s, code = %s, hod_teacher_id = %s WHERE id = %s",
            (payload.name, payload.code.upper(), payload.hod_teacher_id, department_id),
        )
    except aiomysql.IntegrityError as exc:
        raise _DEPARTMENT_TAKEN from exc
    # Faculty keep the department's name as text too (older screens and reports show it).
    await execute("UPDATE teachers SET department = %s WHERE department_id = %s", (payload.name, department_id))
    return await get_department(school_id, department_id)


async def delete_department(school_id: str, department_id: str) -> None:
    department = await get_department(school_id, department_id)
    if department.class_count:
        raise AppError(
            status.HTTP_409_CONFLICT,
            "department_has_classes",
            f"This department has {department.class_count} batch(es). Move or delete them first.",
        )
    await execute("DELETE FROM departments WHERE id = %s", (department_id,))
