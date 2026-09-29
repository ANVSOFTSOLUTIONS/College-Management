import uuid
from datetime import datetime, timezone

from fastapi import status

from app.api.deps import CurrentUser
from app.core.errors import AppError
from app.db.database import db
from app.db.helpers import fetch_all, fetch_one
from app.modules.attendance.schemas import AttendanceRecordIn


async def get_class_for_school(class_id: str, school_id: str) -> dict:
    class_doc = await fetch_one(
        "SELECT * FROM classes WHERE id = %s AND school_id = %s", (class_id, school_id)
    )
    if class_doc is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "class_not_found", "Class not found.")
    return class_doc


async def ensure_class_access(current_user: CurrentUser, class_doc: dict) -> None:
    if current_user.role == "admin":
        return

    teacher = await fetch_one(
        "SELECT * FROM teachers WHERE user_id = %s AND school_id = %s",
        (current_user.id, current_user.school_id),
    )
    if teacher is None or class_doc["teacher_id"] != teacher["id"]:
        raise AppError(
            status.HTTP_403_FORBIDDEN,
            "forbidden",
            "You are not assigned to this class.",
        )


_CLASS_LIST_SELECT = """
    SELECT c.*, u.full_name AS class_teacher_name, d.name AS department_name,
           (SELECT COUNT(*) FROM students s WHERE s.class_id = c.id AND s.status = 'active') AS student_count
    FROM classes c
    JOIN teachers t ON t.id = c.teacher_id
    JOIN users u ON u.id = t.user_id
    LEFT JOIN departments d ON d.id = c.department_id
"""


async def list_classes_for_user(current_user: CurrentUser) -> list[dict]:
    if current_user.role == "admin":
        return await fetch_all(
            f"{_CLASS_LIST_SELECT} WHERE c.school_id = %s AND c.is_archived = 0 ORDER BY c.name, c.section", (current_user.school_id,)
        )

    teacher = await fetch_one(
        "SELECT * FROM teachers WHERE user_id = %s AND school_id = %s",
        (current_user.id, current_user.school_id),
    )
    if teacher is None:
        return []

    return await fetch_all(
        f"{_CLASS_LIST_SELECT} WHERE c.school_id = %s AND c.teacher_id = %s AND c.is_archived = 0 ORDER BY c.name, c.section",
        (current_user.school_id, teacher["id"]),
    )


async def list_roster(class_id: str) -> list[dict]:
    return await fetch_all(
        "SELECT * FROM students WHERE class_id = %s AND status = 'active' ORDER BY full_name", (class_id,)
    )


async def get_attendance_map(class_id: str, iso_date: str) -> dict[str, str]:
    records = await fetch_all(
        "SELECT student_id, status FROM attendance WHERE class_id = %s AND attendance_date = %s",
        (class_id, iso_date),
    )
    return {record["student_id"]: record["status"] for record in records}


async def mark_attendance(
    *,
    school_id: str,
    class_id: str,
    iso_date: str,
    records: list[AttendanceRecordIn],
    marked_by_user_id: str,
) -> int:
    roster_ids = {student["id"] for student in await list_roster(class_id)}
    unknown = [record.student_id for record in records if record.student_id not in roster_ids]
    if unknown:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            "unknown_student",
            f"Student(s) not in this class: {', '.join(unknown)}",
        )

    marked_at = datetime.now(timezone.utc)
    async with db.pool.acquire() as conn:
        async with conn.cursor() as cur:
            for record in records:
                await cur.execute(
                    """
                    INSERT INTO attendance (id, school_id, class_id, student_id, attendance_date, status, marked_by, marked_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE status = VALUES(status), marked_by = VALUES(marked_by), marked_at = VALUES(marked_at)
                    """,
                    (
                        str(uuid.uuid4()),
                        school_id,
                        class_id,
                        record.student_id,
                        iso_date,
                        record.status,
                        marked_by_user_id,
                        marked_at,
                    ),
                )
    return len(records)
