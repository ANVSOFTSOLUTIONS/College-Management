"""Reports: student attendance, staff attendance and fee dues, on screen or as Excel.

Admins see the whole school; a class teacher sees their own class's student
attendance.
"""

import io
from datetime import date, timedelta

from fastapi import status
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Font
from pydantic import BaseModel

from app.api.deps import CurrentUser
from app.core.errors import AppError
from app.db.helpers import fetch_all
from app.modules.board import audience
from app.modules.fees import service as fees

MAX_RANGE_DAYS = 400
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class StudentAttendanceRow(BaseModel):
    student_id: str
    full_name: str
    admission_number: str
    class_name: str
    section: str
    present: int
    late: int
    absent: int
    marked: int
    percent: float | None  # (present + late) / marked


class StudentAttendanceReport(BaseModel):
    start: date
    end: date
    working_days: int  # days any attendance was taken in the chosen classes
    average_percent: float | None
    rows: list[StudentAttendanceRow]


class StaffAttendanceRow(BaseModel):
    teacher_id: str
    full_name: str
    department: str
    present: int
    late: int
    leave: int
    absent: int


class StaffAttendanceReport(BaseModel):
    month: str  # "2026-09"
    rows: list[StaffAttendanceRow]


def _check_range(start: date, end: date) -> None:
    if end < start or (end - start).days > MAX_RANGE_DAYS:
        raise AppError(status.HTTP_400_BAD_REQUEST, "invalid_range", f"Choose a range of at most {MAX_RANGE_DAYS} days.")


async def _report_class_ids(user: CurrentUser, class_id: str | None) -> list[str] | None:
    """None: every class (admin). Teachers get the classes they are class teacher of."""
    if user.role == "admin":
        if class_id:
            await audience.school_class_ids(user.school_id, [class_id])
            return [class_id]
        return None
    teacher_id = await audience.teacher_id(user)
    mine = [r["id"] for r in await fetch_all("SELECT id FROM classes WHERE teacher_id = %s AND is_archived = 0", (teacher_id,))] if teacher_id else []
    if class_id:
        if class_id not in mine:
            raise AppError(status.HTTP_404_NOT_FOUND, "class_not_found", "Class not found.")
        return [class_id]
    return mine


async def student_attendance(user: CurrentUser, *, class_id: str | None, start: date, end: date) -> StudentAttendanceReport:
    _check_range(start, end)
    class_ids = await _report_class_ids(user, class_id)
    where, params = ["c.school_id = %s", "c.is_archived = 0", "s.status = 'active'"], [start, end, user.school_id]
    if class_ids is not None:
        if not class_ids:
            return StudentAttendanceReport(start=start, end=end, working_days=0, average_percent=None, rows=[])
        where.append("c.id IN ({})".format(", ".join(["%s"] * len(class_ids))))
        params += class_ids
    rows = await fetch_all(
        f"""
        SELECT s.id, s.full_name, s.admission_number, c.name AS class_name, c.section,
               COALESCE(SUM(a.status = 'present'), 0) AS present,
               COALESCE(SUM(a.status = 'late'), 0) AS late,
               COALESCE(SUM(a.status = 'absent'), 0) AS absent,
               COUNT(a.id) AS marked
        FROM students s
        JOIN classes c ON c.id = s.class_id
        -- A student's attendance counts even if taken in last year's class (before promotion).
        LEFT JOIN attendance a ON a.student_id = s.id AND a.attendance_date BETWEEN %s AND %s
        WHERE {' AND '.join(where)}
        GROUP BY s.id, s.full_name, s.admission_number, c.name, c.section
        ORDER BY c.name, c.section, s.full_name
        """,
        tuple(params),
    )
    days = await fetch_all(
        f"""
        SELECT COUNT(DISTINCT a.attendance_date) AS n FROM attendance a
        JOIN students s ON s.id = a.student_id JOIN classes c ON c.id = s.class_id
        WHERE a.attendance_date BETWEEN %s AND %s AND {' AND '.join(where)}
        """,
        tuple(params),
    )
    out = [
        StudentAttendanceRow(
            student_id=r["id"], full_name=r["full_name"], admission_number=r["admission_number"], class_name=r["class_name"],
            section=r["section"], present=int(r["present"]), late=int(r["late"]), absent=int(r["absent"]), marked=r["marked"],
            percent=round((int(r["present"]) + int(r["late"])) * 100 / r["marked"], 1) if r["marked"] else None,
        )
        for r in rows
    ]
    marked = sum(r.marked for r in out)
    came = sum(r.present + r.late for r in out)
    return StudentAttendanceReport(
        start=start, end=end, working_days=days[0]["n"], average_percent=round(came * 100 / marked, 1) if marked else None, rows=out
    )


async def staff_attendance(user: CurrentUser, month: date) -> StaffAttendanceReport:
    first = month.replace(day=1)
    last = (first + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    rows = await fetch_all(
        """
        SELECT t.id, u.full_name, t.department,
               COALESCE(SUM(sa.status = 'present'), 0) AS present,
               COALESCE(SUM(sa.status = 'late'), 0) AS late,
               COALESCE(SUM(sa.status = 'leave'), 0) AS on_leave,
               COALESCE(SUM(sa.status = 'absent'), 0) AS absent
        FROM teachers t JOIN users u ON u.id = t.user_id
        LEFT JOIN staff_attendance sa ON sa.teacher_id = t.id AND sa.attendance_date BETWEEN %s AND %s
        WHERE t.school_id = %s AND u.status = 'active'
        GROUP BY t.id, u.full_name, t.department
        ORDER BY u.full_name
        """,
        (first, last, user.school_id),
    )
    return StaffAttendanceReport(
        month=f"{first:%Y-%m}",
        rows=[
            StaffAttendanceRow(
                teacher_id=r["id"], full_name=r["full_name"], department=r["department"], present=int(r["present"]),
                late=int(r["late"]), leave=int(r["on_leave"]), absent=int(r["absent"]),
            )
            for r in rows
        ],
    )


def xlsx_response(filename: str, title: str, headers: list[str], rows: list[list]) -> StreamingResponse:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = title[:31]
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for row in rows:
        sheet.append(row)
    for column in sheet.columns:
        width = max(len(str(c.value)) if c.value is not None else 0 for c in column)
        sheet.column_dimensions[column[0].column_letter].width = min(max(width + 2, 8), 40)
    sheet.freeze_panes = "A2"
    buffer = io.BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return StreamingResponse(buffer, media_type=XLSX, headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"})


def student_attendance_xlsx(report: StudentAttendanceReport) -> StreamingResponse:
    return xlsx_response(
        f"student-attendance-{report.start}-to-{report.end}.xlsx",
        "Student attendance",
        ["Class", "Section", "Admission no.", "Student", "Present", "Late", "Absent", "Days marked", "Attendance %"],
        [[r.class_name, r.section, r.admission_number, r.full_name, r.present, r.late, r.absent, r.marked, r.percent] for r in report.rows],
    )


def staff_attendance_xlsx(report: StaffAttendanceReport) -> StreamingResponse:
    return xlsx_response(
        f"staff-attendance-{report.month}.xlsx",
        "Staff attendance",
        ["Teacher", "Department", "Present", "Late", "Leave", "Absent"],
        [[r.full_name, r.department, r.present, r.late, r.leave, r.absent] for r in report.rows],
    )


async def fee_dues_xlsx(user: CurrentUser, class_id: str | None, only_with_dues: bool) -> StreamingResponse:
    report = await fees.fee_report(user, class_id=class_id, only_with_dues=only_with_dues)
    return xlsx_response(
        "fee-dues.xlsx",
        "Fee dues",
        ["Class", "Section", "Admission no.", "Student", "Total", "Paid", "Balance", "Overdue", "Next due", "Contact"],
        [
            [s.class_name, s.section, s.admission_number, s.full_name, s.total, s.paid, s.balance, s.overdue, s.next_due_date, s.primary_contact_phone]
            for s in report.students
        ],
    )
