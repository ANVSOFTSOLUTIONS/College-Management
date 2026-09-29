"""Exam performance at a glance, built on the exam module's class results.

Admins see every class in the exam; a teacher sees the classes they are class
teacher of (the same rule as class results).
"""

from collections import Counter, defaultdict
from datetime import timedelta

from fastapi import status
from pydantic import BaseModel

from app.api.deps import CurrentUser
from app.core.errors import AppError
from app.db.helpers import fetch_all
from app.modules.alerts.service import today_ist
from app.modules.board import audience
from app.modules.exams import service as exams
from app.modules.exams.service import GRADE_SCALE

TOPPERS = 10
ATTENDANCE_DAYS = 90
LOW_ATTENDANCE = 75.0


class ClassPerformance(BaseModel):
    class_id: str
    label: str
    students: int
    appeared: int  # all marks entered
    average_percent: float | None
    pass_percent: float | None
    topper: str | None


class SubjectPerformance(BaseModel):
    subject_name: str
    average_percent: float | None
    pass_percent: float | None
    appeared: int


class Topper(BaseModel):
    student_id: str
    full_name: str
    class_label: str
    percentage: float
    grade: str | None


class NeedsAttention(BaseModel):
    student_id: str
    full_name: str
    admission_number: str
    class_label: str
    percentage: float | None
    failed_subjects: list[str]
    absent_subjects: list[str]
    attendance_percent: float | None  # last 90 days


class ExamPerformance(BaseModel):
    exam_id: str
    exam_name: str
    published: bool
    classes: list[ClassPerformance]
    subjects: list[SubjectPerformance]
    grades: dict[str, int]  # grade -> students, best first
    toppers: list[Topper]
    needs_attention: list[NeedsAttention]


def _pct(part: float, whole: float) -> float | None:
    return round(part * 100 / whole, 1) if whole else None


async def _attendance(student_ids: list[str]) -> dict[str, float | None]:
    if not student_ids:
        return {}
    since = today_ist() - timedelta(days=ATTENDANCE_DAYS)
    placeholders = ", ".join(["%s"] * len(student_ids))
    rows = await fetch_all(
        f"""
        SELECT student_id, COUNT(*) AS marked, SUM(status IN ('present', 'late')) AS came
        FROM attendance WHERE attendance_date >= %s AND student_id IN ({placeholders}) GROUP BY student_id
        """,
        (since, *student_ids),
    )
    return {r["student_id"]: _pct(float(r["came"]), r["marked"]) for r in rows}


async def exam_performance(user: CurrentUser, exam_id: str) -> ExamPerformance:
    exam = await exams._get_exam(user, exam_id)
    classes = await fetch_all(
        """
        SELECT DISTINCT c.* FROM exam_subjects es JOIN classes c ON c.id = es.class_id
        WHERE es.exam_id = %s ORDER BY c.name, c.section
        """,
        (exam_id,),
    )
    if user.role != "admin":
        teacher_id = await audience.teacher_id(user)
        classes = [c for c in classes if teacher_id and c["teacher_id"] == teacher_id]
        if not classes:
            raise AppError(status.HTTP_403_FORBIDDEN, "forbidden", "Only class teachers of classes in this exam can see its performance.")

    class_rows, subject_scores, grades, toppers, attention = [], defaultdict(lambda: [0.0, 0, 0]), Counter(), [], []
    for cls in classes:
        label = f"{cls['name']} - {cls['section']}"
        results = await exams._class_results(exam, cls)
        complete = [r for r in results.students if r.complete]
        best = min(complete, key=lambda r: r.rank or 0, default=None)
        class_rows.append(
            ClassPerformance(
                class_id=cls["id"], label=label, students=len(results.students), appeared=len(complete),
                average_percent=round(sum(r.percentage for r in complete) / len(complete), 1) if complete else None,
                pass_percent=_pct(sum(1 for r in complete if r.passed), len(complete)),
                topper=best.full_name if best else None,
            )
        )
        for r in results.students:
            for paper in r.papers:
                if paper.marks is not None or paper.is_absent:
                    score = subject_scores[paper.subject_name]
                    score[0] += (paper.marks or 0) * 100 / paper.max_marks
                    score[1] += 1
                    score[2] += 1 if paper.passed else 0
            if r.complete:
                grades[r.grade] += 1
                toppers.append(Topper(student_id=r.student_id, full_name=r.full_name, class_label=label, percentage=r.percentage, grade=r.grade))
            failed = [p.subject_name for p in r.papers if p.passed is False and not p.is_absent]
            absent = [p.subject_name for p in r.papers if p.is_absent]
            if failed or absent:
                attention.append(
                    NeedsAttention(
                        student_id=r.student_id, full_name=r.full_name, admission_number=r.admission_number, class_label=label,
                        percentage=r.percentage, failed_subjects=failed, absent_subjects=absent, attendance_percent=None,
                    )
                )

    attendance = await _attendance([a.student_id for a in attention])
    for a in attention:
        a.attendance_percent = attendance.get(a.student_id)
    attention.sort(key=lambda a: (-(len(a.failed_subjects) + len(a.absent_subjects)), a.percentage if a.percentage is not None else 0))
    toppers.sort(key=lambda t: t.percentage, reverse=True)

    return ExamPerformance(
        exam_id=exam["id"],
        exam_name=exam["name"],
        published=exam["published_at"] is not None,
        classes=class_rows,
        subjects=[
            SubjectPerformance(subject_name=name, average_percent=round(total / count, 1) if count else None, pass_percent=_pct(passed, count), appeared=count)
            for name, (total, count, passed) in sorted(subject_scores.items())
        ],
        grades={grade: grades.get(grade, 0) for _, grade in GRADE_SCALE},
        toppers=toppers[:TOPPERS],
        needs_attention=attention,
    )
