import uuid
from datetime import datetime, timezone

from fastapi import status

from app.core.errors import AppError
from app.db.database import db
from app.db.helpers import fetch_all
from app.modules.staff_attendance.schemas import StaffAttendanceRecordIn


async def list_teachers(school_id: str) -> list[dict]:
    return await fetch_all(
        """
        SELECT t.id, t.department, u.full_name
        FROM teachers t JOIN users u ON u.id = t.user_id
        WHERE t.school_id = %s AND u.status = 'active'
        ORDER BY u.full_name
        """,
        (school_id,),
    )


async def get_attendance_map(school_id: str, iso_date: str) -> dict[str, str]:
    records = await fetch_all(
        "SELECT teacher_id, status FROM staff_attendance WHERE school_id = %s AND attendance_date = %s",
        (school_id, iso_date),
    )
    return {record["teacher_id"]: record["status"] for record in records}


async def mark_attendance(
    *,
    school_id: str,
    iso_date: str,
    records: list[StaffAttendanceRecordIn],
    marked_by_user_id: str,
) -> int:
    teacher_ids = {teacher["id"] for teacher in await list_teachers(school_id)}
    unknown = [record.teacher_id for record in records if record.teacher_id not in teacher_ids]
    if unknown:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            "unknown_teacher",
            f"Teacher(s) not in this school: {', '.join(unknown)}",
        )

    marked_at = datetime.now(timezone.utc)
    async with db.pool.acquire() as conn:
        async with conn.cursor() as cur:
            for record in records:
                await cur.execute(
                    """
                    INSERT INTO staff_attendance (id, school_id, teacher_id, attendance_date, status, marked_by, marked_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE status = VALUES(status), marked_by = VALUES(marked_by), marked_at = VALUES(marked_at)
                    """,
                    (str(uuid.uuid4()), school_id, record.teacher_id, iso_date, record.status, marked_by_user_id, marked_at),
                )
    return len(records)
