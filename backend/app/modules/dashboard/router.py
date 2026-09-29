"""The first screen: today's school at a glance (admin) or a teacher's to-do list."""

from datetime import timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import CurrentUser, require_roles
from app.db.helpers import fetch_all, fetch_one
from app.modules.alerts.service import today_ist
from app.modules.exams import service as exams
from app.modules.fees import service as fees
from app.modules.staff_attendance import punch
from app.modules.timetable import calendar, service as timetable

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
TREND_DAYS = 7


class DayAttendance(BaseModel):
    date: str
    percent: float | None  # None: no attendance taken that day
    marked: int


class ClassToday(BaseModel):
    class_id: str
    name: str
    section: str
    class_teacher_name: str
    students: int
    marked: bool
    present: int
    absent: int
    late: int


class ExamProgress(BaseModel):
    exam_id: str
    name: str
    entered: int
    expected: int


class AdminDashboard(BaseModel):
    date: str
    holiday: str | None  # today's holiday, if the school is closed
    students: int
    teachers: int
    classes_marked: int
    classes_total: int
    present: int
    absent: int
    late: int
    unmarked_classes: list[ClassToday]
    trend: list[DayAttendance]
    staff_punched_in: int
    staff_late: int
    staff_on_leave: int
    fees_collected_today: float
    fees_collected_month: float
    fees_outstanding: float
    fees_overdue: float
    pending_leave: int
    pending_documents: int
    pending_admissions: int
    exams_in_progress: list[ExamProgress]


class PaperTodo(BaseModel):
    paper_id: str
    label: str
    entered: int
    students: int


class Lesson(BaseModel):
    period: str
    start_time: str
    end_time: str
    subject_name: str
    class_label: str


class TeacherDashboard(BaseModel):
    date: str
    holiday: str | None
    lessons_today: list[Lesson]
    punch: punch.PunchOut
    day_starts_at: str
    my_classes: list[ClassToday]
    pending_leave: int
    pending_documents: int
    marks_to_enter: list[PaperTodo]


async def _classes_today(school_id: str, day, teacher_id: str | None = None) -> list[ClassToday]:
    where, params = ["c.school_id = %s", "c.is_archived = 0"], [day, school_id]
    if teacher_id:
        where.append("c.teacher_id = %s")
        params.append(teacher_id)
    rows = await fetch_all(
        f"""
        SELECT c.id, c.name, c.section, u.full_name AS teacher_name,
               (SELECT COUNT(*) FROM students s WHERE s.class_id = c.id AND s.status = 'active') AS students,
               COUNT(a.id) AS marked,
               COALESCE(SUM(a.status = 'present'), 0) AS present,
               COALESCE(SUM(a.status = 'absent'), 0) AS absent,
               COALESCE(SUM(a.status = 'late'), 0) AS late
        FROM classes c
        JOIN teachers t ON t.id = c.teacher_id JOIN users u ON u.id = t.user_id
        LEFT JOIN attendance a ON a.class_id = c.id AND a.attendance_date = %s
        WHERE {' AND '.join(where)}
        GROUP BY c.id, c.name, c.section, u.full_name
        ORDER BY c.name, c.section
        """,
        tuple(params),
    )
    return [
        ClassToday(
            class_id=r["id"], name=r["name"], section=r["section"], class_teacher_name=r["teacher_name"],
            students=r["students"], marked=r["marked"] > 0, present=int(r["present"]), absent=int(r["absent"]), late=int(r["late"]),
        )
        for r in rows
    ]


async def _trend(school_id: str, today) -> list[DayAttendance]:
    # Today plus the school days before it (Sundays and holidays are skipped; many schools work Saturdays).
    holidays = await calendar.holidays_between(school_id, today - timedelta(days=TREND_DAYS * 3), today)
    days, day = [today], today - timedelta(days=1)
    while len(days) < TREND_DAYS:
        if day.weekday() != 6 and day not in holidays:
            days.append(day)
        day -= timedelta(days=1)
    rows = {
        r["attendance_date"]: r
        for r in await fetch_all(
            """
            SELECT attendance_date, COUNT(*) AS total, SUM(status IN ('present', 'late')) AS came, COUNT(DISTINCT class_id) AS classes
            FROM attendance WHERE school_id = %s AND attendance_date BETWEEN %s AND %s GROUP BY attendance_date
            """,
            (school_id, days[-1], days[0]),
        )
    }
    return [
        DayAttendance(
            date=d.isoformat(),
            percent=round(float(rows[d]["came"]) * 100 / rows[d]["total"], 1) if d in rows and rows[d]["total"] else None,
            marked=rows[d]["classes"] if d in rows else 0,
        )
        for d in reversed(days)
    ]


async def _count(sql: str, params: tuple) -> int:
    return int((await fetch_one(sql, params))["n"])


@router.get("/admin", response_model=AdminDashboard)
async def admin_dashboard(current_user: CurrentUser = Depends(require_roles("admin"))) -> AdminDashboard:
    school_id, today = current_user.school_id, today_ist()
    holiday = await calendar.holiday_on(school_id, today)
    classes = await _classes_today(school_id, today)
    marked = [c for c in classes if c.marked]

    punches = await punch.punches_for_day(current_user, today)
    report = await fees.fee_report(current_user, class_id=None, only_with_dues=False)
    collected = await fetch_one(
        """
        SELECT COALESCE(SUM(CASE WHEN paid_on = %s THEN amount END), 0) AS today,
               COALESCE(SUM(CASE WHEN paid_on >= %s THEN amount END), 0) AS month
        FROM fee_payments WHERE school_id = %s AND status = 'success' AND paid_on >= %s
        """,
        (today, today.replace(day=1), school_id, today.replace(day=1)),
    )

    in_progress = []
    for exam in await fetch_all("SELECT id FROM exams WHERE school_id = %s AND published_at IS NULL ORDER BY created_at DESC LIMIT 5", (school_id,)):
        detail = await exams.get_exam(current_user, exam["id"])
        in_progress.append(
            ExamProgress(exam_id=detail.id, name=detail.name, entered=sum(p.entered for p in detail.papers), expected=sum(p.students for p in detail.papers))
        )

    return AdminDashboard(
        date=today.isoformat(),
        holiday=holiday,
        students=await _count("SELECT COUNT(*) AS n FROM students WHERE school_id = %s AND status = 'active'", (school_id,)),
        teachers=len(punches),
        classes_marked=len(marked),
        classes_total=len(classes),
        present=sum(c.present for c in classes),
        absent=sum(c.absent for c in classes),
        late=sum(c.late for c in classes),
        unmarked_classes=[] if holiday else [c for c in classes if not c.marked],
        trend=await _trend(school_id, today),
        staff_punched_in=sum(1 for p in punches if p.punch),
        staff_late=sum(1 for p in punches if p.punch and p.punch.is_late),
        staff_on_leave=sum(1 for p in punches if p.on_leave),
        fees_collected_today=float(Decimal(collected["today"])),
        fees_collected_month=float(Decimal(collected["month"])),
        fees_outstanding=report.balance,
        fees_overdue=report.overdue,
        pending_leave=await _count("SELECT COUNT(*) AS n FROM leave_requests WHERE school_id = %s AND status = 'pending' AND teacher_id IS NOT NULL", (school_id,)),
        pending_documents=await _count("SELECT COUNT(*) AS n FROM student_documents WHERE school_id = %s AND status = 'pending'", (school_id,)),
        pending_admissions=await _count("SELECT COUNT(*) AS n FROM admission_applications WHERE school_id = %s AND status = 'new'", (school_id,)),
        exams_in_progress=in_progress,
    )


@router.get("/teacher", response_model=TeacherDashboard)
async def teacher_dashboard(current_user: CurrentUser = Depends(require_roles("teacher"))) -> TeacherDashboard:
    school_id, today = current_user.school_id, today_ist()
    mine = await punch.my_punches(current_user)  # also checks this is teaching staff
    teacher = await fetch_one("SELECT id FROM teachers WHERE user_id = %s AND school_id = %s", (current_user.id, school_id))
    my_classes = await _classes_today(school_id, today, teacher["id"])
    class_ids = [c.class_id for c in my_classes]
    pending_leave = pending_documents = 0
    if class_ids:
        placeholders = ", ".join(["%s"] * len(class_ids))
        pending_leave = await _count(
            f"SELECT COUNT(*) AS n FROM leave_requests WHERE status = 'pending' AND student_id IS NOT NULL AND class_id IN ({placeholders})", tuple(class_ids)
        )
        pending_documents = await _count(
            f"""
            SELECT COUNT(*) AS n FROM student_documents d JOIN students s ON s.id = d.student_id
            WHERE d.status = 'pending' AND s.class_id IN ({placeholders})
            """,
            tuple(class_ids),
        )
    papers = await exams.my_papers(current_user)
    holiday = await calendar.holiday_on(school_id, today)
    lessons = [] if holiday or today.weekday() > 5 else await timetable.today_for_teacher(current_user, today.weekday())
    return TeacherDashboard(
        date=today.isoformat(),
        holiday=holiday,
        lessons_today=[
            Lesson(period=p.label, start_time=p.start_time, end_time=p.end_time, subject_name=c.subject_name, class_label=c.class_label)
            for p, c in lessons
        ],
        punch=mine.today,
        day_starts_at=mine.day_starts_at,
        my_classes=my_classes,
        pending_leave=pending_leave,
        pending_documents=pending_documents,
        marks_to_enter=[
            PaperTodo(paper_id=p.id, label=f"{p.subject_name} · {p.class_name} - {p.section} · {p.exam_name}", entered=p.entered, students=p.students)
            for p in papers
            if p.entered < p.students
        ],
    )
