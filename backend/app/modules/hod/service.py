"""Head of department: a daily view of their department(s) for the mobile app.

Faculty punch-in status today, each batch's attendance today, students whose
attendance over the last 30 days is below the 75% most universities require,
and how many leave requests wait for the HOD (department faculty's leave).
"""

from datetime import timedelta

from fastapi import status
from pydantic import BaseModel

from app.api.deps import CurrentUser
from app.core.errors import AppError
from app.db.helpers import fetch_all, fetch_one
from app.modules.alerts.service import today_ist
from app.modules.staff_attendance.punch import _utc_iso

LOW_ATTENDANCE = 75.0


class FacultyToday(BaseModel):
    teacher_id: str
    full_name: str
    designation: str
    phone: str
    status: str  # 'in', 'late', 'not_in', 'on_leave'
    punch_in_at: str | None


class BatchToday(BaseModel):
    class_id: str
    name: str
    section: str
    semester: int | None
    students: int
    marked: bool
    present: int
    absent: int


class LowAttendance(BaseModel):
    student_id: str
    full_name: str
    admission_number: str
    batch: str
    percent: float
    days: int


class DepartmentToday(BaseModel):
    id: str
    name: str
    code: str
    faculty: list[FacultyToday]
    batches: list[BatchToday]
    low_attendance: list[LowAttendance]
    students: int


class HodOverview(BaseModel):
    date: str
    pending_leaves: int
    departments: list[DepartmentToday]


async def hod_departments(user: CurrentUser) -> list[dict]:
    return await fetch_all(
        """
        SELECT d.* FROM departments d JOIN teachers t ON t.id = d.hod_teacher_id
        WHERE t.user_id = %s AND d.school_id = %s ORDER BY d.name
        """,
        (user.id, user.school_id),
    )


async def overview(user: CurrentUser) -> HodOverview:
    departments = await hod_departments(user)
    if not departments:
        raise AppError(status.HTTP_403_FORBIDDEN, "not_hod", "Only a head of department can see this.")
    today = today_ist()
    since = today - timedelta(days=30)
    result = []
    for d in departments:
        faculty = await fetch_all(
            """
            SELECT t.id, u.full_name, t.designation, t.phone, p.punch_in_at, p.is_late, sa.status AS attendance_status
            FROM teachers t JOIN users u ON u.id = t.user_id
            LEFT JOIN staff_punches p ON p.teacher_id = t.id AND p.punch_date = %s
            LEFT JOIN staff_attendance sa ON sa.teacher_id = t.id AND sa.attendance_date = %s
            WHERE t.department_id = %s AND u.status = 'active'
            ORDER BY u.full_name
            """,
            (today, today, d["id"]),
        )
        batches = await fetch_all(
            """
            SELECT c.id, c.name, c.section, c.semester,
                   (SELECT COUNT(*) FROM students s WHERE s.class_id = c.id AND s.status = 'active') AS students,
                   (SELECT COUNT(*) FROM attendance a WHERE a.class_id = c.id AND a.attendance_date = %s) AS marked,
                   (SELECT COUNT(*) FROM attendance a WHERE a.class_id = c.id AND a.attendance_date = %s AND a.status IN ('present', 'late')) AS present,
                   (SELECT COUNT(*) FROM attendance a WHERE a.class_id = c.id AND a.attendance_date = %s AND a.status = 'absent') AS absent
            FROM classes c WHERE c.department_id = %s AND c.is_archived = 0 ORDER BY c.semester, c.name, c.section
            """,
            (today, today, today, d["id"]),
        )
        low = await fetch_all(
            """
            SELECT s.id, s.full_name, s.admission_number, CONCAT(c.name, ' - ', c.section) AS batch,
                   COUNT(*) AS days, SUM(a.status IN ('present', 'late')) AS attended
            FROM attendance a JOIN students s ON s.id = a.student_id JOIN classes c ON c.id = s.class_id
            WHERE c.department_id = %s AND s.status = 'active' AND a.attendance_date >= %s
            GROUP BY s.id, s.full_name, s.admission_number, batch
            HAVING SUM(a.status IN ('present', 'late')) * 100 < %s * COUNT(*)
            ORDER BY SUM(a.status IN ('present', 'late')) / COUNT(*), s.full_name
            LIMIT 50
            """,
            (d["id"], since, LOW_ATTENDANCE),
        )
        result.append(
            DepartmentToday(
                id=d["id"],
                name=d["name"],
                code=d["code"],
                faculty=[
                    FacultyToday(
                        teacher_id=f["id"],
                        full_name=f["full_name"],
                        designation=f["designation"],
                        phone=f["phone"],
                        status="on_leave" if f["attendance_status"] == "leave" else ("late" if f["is_late"] else "in") if f["punch_in_at"] else "not_in",
                        punch_in_at=_utc_iso(f["punch_in_at"]),
                    )
                    for f in faculty
                ],
                batches=[
                    BatchToday(
                        class_id=b["id"], name=b["name"], section=b["section"], semester=b["semester"], students=b["students"],
                        marked=b["marked"] > 0, present=b["present"], absent=b["absent"],
                    )
                    for b in batches
                ],
                low_attendance=[
                    LowAttendance(
                        student_id=r["id"], full_name=r["full_name"], admission_number=r["admission_number"], batch=r["batch"],
                        percent=round(float(r["attended"]) * 100 / r["days"], 1), days=r["days"],
                    )
                    for r in low
                ],
                students=sum(b["students"] for b in batches),
            )
        )
    ids = [d["id"] for d in departments]
    placeholders = ", ".join(["%s"] * len(ids))
    pending = await fetch_one(
        f"""
        SELECT COUNT(*) AS n FROM leave_requests l JOIN teachers t ON t.id = l.teacher_id
        WHERE l.status = 'pending' AND t.department_id IN ({placeholders}) AND l.applicant_user_id <> %s
        """,
        (*ids, user.id),
    )
    return HodOverview(date=today.isoformat(), pending_leaves=pending["n"], departments=result)
