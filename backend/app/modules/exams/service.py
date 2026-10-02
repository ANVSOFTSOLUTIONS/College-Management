"""Exams: papers per batch and subject, marks entry, results, report cards.

Grades use the UGC-style 10-point scale on percentage (O, A+, A, B+, B, C, F),
each with a grade point. A paper below its pass mark is F, absent is AB; both
earn 0 points and no credits. SGPA is the credit-weighted mean of grade points
over an exam's papers; CGPA is the same over every published semester-end exam.
A student passes an exam when every paper has marks at or above its pass mark.
Rank uses standard competition ranking (1, 2, 2, 4) on percentage, among
students whose every paper is entered.
"""

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import aiomysql
from fastapi import status

from app.api.deps import CurrentUser
from app.core.errors import AppError
from app.db.database import db
from app.db.helpers import execute, fetch_all, fetch_one
from app.modules.alerts import service as alerts
from app.modules.audit import service as audit
from app.modules.electives.service import elective_roster
from app.modules.exams.schemas import (
    BacklogOut,
    ClassResults,
    CreateExamRequest,
    ExamOut,
    MarkSheet,
    MarkSheetRow,
    PaperOut,
    PaperRequest,
    PaperResult,
    PublishedResult,
    ReportCard,
    SaveMarksRequest,
    StudentBacklogs,
    StudentResult,
    SubjectStats,
    UpdateExamRequest,
    UpdatePaperRequest,
)

GRADE_SCALE = [(90, "O"), (80, "A+"), (70, "A"), (60, "B+"), (50, "B"), (40, "C"), (0, "F")]
GRADE_POINTS = {"O": 10, "A+": 9, "A": 8, "B+": 7, "B": 6, "C": 5, "F": 0, "AB": 0}


def grade_for(percentage: float | None) -> str | None:
    if percentage is None:
        return None
    return next(grade for floor, grade in GRADE_SCALE if percentage >= floor)


def gpa(papers: list[PaperResult]) -> float | None:
    """Credit-weighted mean grade point of graded papers (SGPA for one exam, CGPA over several)."""
    graded = [p for p in papers if p.grade_point is not None and p.credits > 0]
    credits = sum(p.credits for p in graded)
    if not credits:
        return None
    return round(sum(p.credits * p.grade_point for p in graded) / credits, 2)


def _f(value) -> float:
    return float(Decimal(value).quantize(Decimal("0.01")))


def _not_found(what: str) -> AppError:
    return AppError(status.HTTP_404_NOT_FOUND, f"{what}_not_found", f"{what.capitalize()} not found.")


_LOCKED = AppError(
    status.HTTP_409_CONFLICT, "exam_published", "Results are published, so marks are locked. An admin can unpublish to make changes."
)


# --- Access -------------------------------------------------------------------


async def _teacher_id(user: CurrentUser) -> str | None:
    if user.role != "teacher":
        return None
    row = await fetch_one("SELECT id FROM teachers WHERE user_id = %s AND school_id = %s", (user.id, user.school_id))
    return row["id"] if row else None


def _can_mark(user: CurrentUser, teacher_id: str | None, paper: dict) -> bool:
    """Admins mark anything; a teacher marks papers they teach, or any paper of a class they are class teacher of."""
    if user.role == "admin":
        return True
    return teacher_id is not None and teacher_id in (paper["subject_teacher_id"], paper["class_teacher_id"])


_PAPER_SELECT = """
    SELECT es.*, e.name AS exam_name, e.published_at, c.name AS class_name, c.section, c.teacher_id AS class_teacher_id,
           sub.name AS subject_name, cs.teacher_id AS subject_teacher_id, tu.full_name AS teacher_name,
           (SELECT COUNT(*) FROM students s WHERE s.class_id = es.class_id AND s.status = 'active') AS students,
           (SELECT COUNT(*) FROM exam_marks m JOIN students s ON s.id = m.student_id
             WHERE m.exam_subject_id = es.id AND s.status = 'active') AS entered
    FROM exam_subjects es
    JOIN exams e ON e.id = es.exam_id
    JOIN classes c ON c.id = es.class_id
    JOIN subjects sub ON sub.id = es.subject_id
    LEFT JOIN class_subjects cs ON cs.class_id = es.class_id AND cs.subject_id = es.subject_id
    LEFT JOIN teachers t ON t.id = cs.teacher_id
    LEFT JOIN users tu ON tu.id = t.user_id
"""


def _paper_out(row: dict, user: CurrentUser, teacher_id: str | None) -> PaperOut:
    return PaperOut(
        id=row["id"],
        exam_id=row["exam_id"],
        exam_name=row["exam_name"],
        class_id=row["class_id"],
        class_name=row["class_name"],
        section=row["section"],
        subject_id=row["subject_id"],
        subject_name=row["subject_name"],
        teacher_name=row["teacher_name"],
        max_marks=_f(row["max_marks"]),
        pass_marks=_f(row["pass_marks"]),
        exam_date=row["exam_date"],
        students=row["students"],
        entered=row["entered"],
        published=row["published_at"] is not None,
        can_enter_marks=row["published_at"] is None and _can_mark(user, teacher_id, row),
    )


# --- Exams (admin) ------------------------------------------------------------


async def _get_exam(user: CurrentUser, exam_id: str) -> dict:
    row = await fetch_one("SELECT * FROM exams WHERE id = %s AND school_id = %s", (exam_id, user.school_id))
    if row is None:
        raise _not_found("exam")
    return row


async def get_exam(user: CurrentUser, exam_id: str) -> ExamOut:
    exam = await _get_exam(user, exam_id)
    teacher_id = await _teacher_id(user)
    papers = await fetch_all(f"{_PAPER_SELECT} WHERE es.exam_id = %s ORDER BY c.name, c.section, sub.name", (exam_id,))
    return ExamOut(
        id=exam["id"],
        name=exam["name"],
        term_label=exam["term_label"],
        exam_type=exam["exam_type"],
        internal_exam_ids=_internal_ids(exam),
        internal_weight=exam["internal_weight"],
        academic_year=exam["academic_year"],
        start_date=exam["start_date"],
        end_date=exam["end_date"],
        published=exam["published_at"] is not None,
        papers=[_paper_out(p, user, teacher_id) for p in papers],
    )


def _internal_ids(exam: dict) -> list[str]:
    try:
        return json.loads(exam["internal_exam_ids"] or "[]")
    except (TypeError, ValueError):
        return []


async def _check_internals(user: CurrentUser, exam_type: str, ids: list[str], weight: int, exam_id: str | None = None) -> str | None:
    """Validates the internal exams a semester-end exam draws on; returns them as JSON (None when not used)."""
    ids = list(dict.fromkeys(ids))
    if not ids and not weight:
        return None
    if exam_type != "semester":
        raise AppError(status.HTTP_400_BAD_REQUEST, "internals_only_for_semester", "Only a semester-end exam can include internal marks.")
    if not ids or not weight:
        raise AppError(status.HTTP_400_BAD_REQUEST, "internals_incomplete", "Choose the internal exams and the marks they carry.")
    placeholders = ", ".join(["%s"] * len(ids))
    found = await fetch_all(
        f"SELECT id FROM exams WHERE school_id = %s AND exam_type = 'internal' AND id IN ({placeholders})", (user.school_id, *ids)
    )
    if len(found) != len(ids) or (exam_id and exam_id in ids):
        raise AppError(status.HTTP_400_BAD_REQUEST, "invalid_internal_exam", "Choose internal exams of this college.")
    return json.dumps(ids)


async def list_exams(user: CurrentUser) -> list[ExamOut]:
    rows = await fetch_all(
        "SELECT id FROM exams WHERE school_id = %s ORDER BY COALESCE(start_date, created_at) DESC, created_at DESC",
        (user.school_id,),
    )
    return [await get_exam(user, row["id"]) for row in rows]


async def create_exam(user: CurrentUser, payload: CreateExamRequest) -> ExamOut:
    class_ids = list(dict.fromkeys(payload.class_ids))
    placeholders = ", ".join(["%s"] * len(class_ids))
    found = await fetch_all(f"SELECT id FROM classes WHERE school_id = %s AND id IN ({placeholders})", (user.school_id, *class_ids))
    if len(found) != len(class_ids):
        raise AppError(status.HTTP_400_BAD_REQUEST, "invalid_class", "Choose classes from this school.")
    subjects = await fetch_all(
        f"SELECT class_id, subject_id FROM class_subjects WHERE class_id IN ({placeholders})", tuple(class_ids)
    )
    internals = await _check_internals(user, payload.exam_type, payload.internal_exam_ids, payload.internal_weight)

    exam_id = str(uuid.uuid4())
    async with db.pool.acquire() as conn:
        await conn.begin()
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO exams (id, school_id, name, term_label, exam_type, internal_exam_ids, internal_weight, academic_year,
                                   start_date, end_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (exam_id, user.school_id, payload.name, payload.term_label, payload.exam_type, internals,
                 payload.internal_weight if internals else 0, payload.academic_year, payload.start_date, payload.end_date),
            )
            for row in subjects:
                await cur.execute(
                    """
                    INSERT INTO exam_subjects (id, school_id, exam_id, class_id, subject_id, max_marks, pass_marks)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (str(uuid.uuid4()), user.school_id, exam_id, row["class_id"], row["subject_id"], payload.max_marks, payload.pass_marks),
                )
        await conn.commit()
    return await get_exam(user, exam_id)


async def update_exam(user: CurrentUser, exam_id: str, payload: UpdateExamRequest) -> ExamOut:
    exam = await _get_exam(user, exam_id)
    updates = payload.model_dump(exclude_unset=True)
    updates = {k: v for k, v in updates.items() if v is not None or k in ("start_date", "end_date")}
    if {"internal_exam_ids", "internal_weight", "exam_type"} & updates.keys():
        exam_type = updates.get("exam_type", exam["exam_type"])
        ids = updates.pop("internal_exam_ids", _internal_ids(exam))
        weight = updates.pop("internal_weight", exam["internal_weight"])
        internals = await _check_internals(user, exam_type, ids, weight, exam_id)
        updates["internal_exam_ids"], updates["internal_weight"] = internals, weight if internals else 0
    if updates:
        sets = ", ".join(f"{k} = %s" for k in updates)
        await execute(f"UPDATE exams SET {sets} WHERE id = %s", (*updates.values(), exam_id))
    return await get_exam(user, exam_id)


async def _has_marks(where: str, value: str) -> bool:
    return bool(await fetch_one(f"SELECT m.id FROM exam_marks m JOIN exam_subjects es ON es.id = m.exam_subject_id WHERE {where} = %s LIMIT 1", (value,)))


async def delete_exam(user: CurrentUser, exam_id: str) -> None:
    await _get_exam(user, exam_id)
    if await _has_marks("es.exam_id", exam_id):
        raise AppError(status.HTTP_409_CONFLICT, "exam_has_marks", "Marks were already entered for this exam, so it can't be deleted.")
    await execute("DELETE FROM exams WHERE id = %s", (exam_id,))


async def set_published(user: CurrentUser, exam_id: str, published: bool) -> ExamOut:
    exam = await _get_exam(user, exam_id)
    await execute("UPDATE exams SET published_at = %s WHERE id = %s", (datetime.now(timezone.utc) if published else None, exam_id))
    if bool(exam["published_at"]) != published:
        await audit.record(
            user, "marks.published" if published else "marks.unpublished",
            f"{'Published' if published else 'Unpublished'} results of {exam['name']}", entity_type="exam", entity_id=exam_id,
        )
    return await get_exam(user, exam_id)


async def add_paper(user: CurrentUser, exam_id: str, payload: PaperRequest) -> ExamOut:
    exam = await _get_exam(user, exam_id)
    if exam["published_at"]:
        raise _LOCKED
    if payload.pass_marks > payload.max_marks:
        raise AppError(status.HTTP_400_BAD_REQUEST, "invalid_marks", "Pass marks can't be more than maximum marks.")
    valid = await fetch_one(
        """
        SELECT c.id FROM classes c JOIN subjects s ON s.school_id = c.school_id
        WHERE c.id = %s AND s.id = %s AND c.school_id = %s
        """,
        (payload.class_id, payload.subject_id, user.school_id),
    )
    if valid is None:
        raise AppError(status.HTTP_400_BAD_REQUEST, "invalid_paper", "Choose a class and subject from this school.")
    try:
        await execute(
            """
            INSERT INTO exam_subjects (id, school_id, exam_id, class_id, subject_id, max_marks, pass_marks, exam_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (str(uuid.uuid4()), user.school_id, exam_id, payload.class_id, payload.subject_id, payload.max_marks, payload.pass_marks, payload.exam_date),
        )
    except aiomysql.IntegrityError as exc:
        raise AppError(status.HTTP_409_CONFLICT, "paper_exists", "This subject is already in the exam for that class.") from exc
    return await get_exam(user, exam_id)


async def _get_paper(user: CurrentUser, paper_id: str) -> dict:
    row = await fetch_one(f"{_PAPER_SELECT} WHERE es.id = %s AND es.school_id = %s", (paper_id, user.school_id))
    if row is None:
        raise _not_found("paper")
    return row


async def update_paper(user: CurrentUser, paper_id: str, payload: UpdatePaperRequest) -> PaperOut:
    paper = await _get_paper(user, paper_id)
    if paper["published_at"]:
        raise _LOCKED
    updates = payload.model_dump(exclude_unset=True)
    max_marks = updates.get("max_marks") or paper["max_marks"]
    pass_marks = updates.get("pass_marks") if updates.get("pass_marks") is not None else paper["pass_marks"]
    if pass_marks > max_marks:
        raise AppError(status.HTTP_400_BAD_REQUEST, "invalid_marks", "Pass marks can't be more than maximum marks.")
    top = await fetch_one("SELECT MAX(marks) AS m FROM exam_marks WHERE exam_subject_id = %s", (paper_id,))
    if top["m"] is not None and Decimal(top["m"]) > Decimal(max_marks):
        raise AppError(status.HTTP_409_CONFLICT, "marks_above_max", f"A student already has {top['m']} marks; the maximum can't be lower.")
    updates = {k: v for k, v in updates.items() if v is not None or k == "exam_date"}
    if updates:
        sets = ", ".join(f"{k} = %s" for k in updates)
        await execute(f"UPDATE exam_subjects SET {sets} WHERE id = %s", (*updates.values(), paper_id))
    return _paper_out(await _get_paper(user, paper_id), user, None)


async def delete_paper(user: CurrentUser, paper_id: str) -> None:
    paper = await _get_paper(user, paper_id)
    if paper["published_at"]:
        raise _LOCKED
    if await _has_marks("es.id", paper_id):
        raise AppError(status.HTTP_409_CONFLICT, "paper_has_marks", "Marks were already entered for this paper.")
    await execute("DELETE FROM exam_subjects WHERE id = %s", (paper_id,))


# --- Marks entry --------------------------------------------------------------


async def _roster(paper: dict) -> list[str]:
    """Who writes this paper: the batch's active students; for a supplementary exam, students with a backlog in the subject."""
    exam = await fetch_one("SELECT exam_type, published_at FROM exams WHERE id = %s", (paper["exam_id"],))
    if exam["exam_type"] != "supplementary":
        rows = await fetch_all("SELECT id FROM students WHERE class_id = %s AND status = 'active'", (paper["class_id"],))
        chosen = await elective_roster(paper["class_id"], paper["subject_id"])
        return [r["id"] for r in rows if chosen is None or r["id"] in chosen]
    rows = await fetch_all(
        """
        SELECT DISTINCT m.student_id AS id FROM exam_marks m
        JOIN exam_subjects es ON es.id = m.exam_subject_id JOIN exams e ON e.id = es.exam_id
        JOIN students s ON s.id = m.student_id
        WHERE es.subject_id = %s AND e.school_id = %s AND s.status = 'active' AND e.id <> %s
          AND e.published_at IS NOT NULL AND e.exam_type IN ('semester', 'supplementary')
          AND (m.is_absent = 1 OR m.marks < es.pass_marks)
          AND NOT EXISTS (
              SELECT 1 FROM exam_marks m2 JOIN exam_subjects es2 ON es2.id = m2.exam_subject_id JOIN exams e2 ON e2.id = es2.exam_id
              WHERE m2.student_id = m.student_id AND es2.subject_id = es.subject_id AND e2.published_at IS NOT NULL
                AND e2.exam_type IN ('semester', 'supplementary') AND e2.published_at > e.published_at
                AND m2.is_absent = 0 AND m2.marks >= es2.pass_marks
          )
        UNION SELECT student_id AS id FROM exam_marks WHERE exam_subject_id = %s
        """,
        (paper["subject_id"], paper["school_id"], paper["exam_id"], paper["id"]),
    )
    return [r["id"] for r in rows]


async def my_papers(user: CurrentUser) -> list[PaperOut]:
    """Papers the user may enter marks for, in unpublished exams (most recent exams first)."""
    teacher_id = await _teacher_id(user)
    rows = await fetch_all(
        f"{_PAPER_SELECT} WHERE es.school_id = %s AND e.published_at IS NULL ORDER BY e.created_at DESC, c.name, c.section, sub.name",
        (user.school_id,),
    )
    return [_paper_out(r, user, teacher_id) for r in rows if _can_mark(user, teacher_id, r)]


async def mark_sheet(user: CurrentUser, paper_id: str) -> MarkSheet:
    paper = await _get_paper(user, paper_id)
    teacher_id = await _teacher_id(user)
    if not _can_mark(user, teacher_id, paper):
        raise _not_found("paper")
    student_ids = await _roster(paper)
    rows = []
    if student_ids:
        placeholders = ", ".join(["%s"] * len(student_ids))
        rows = await fetch_all(
            f"""
            SELECT s.id, s.full_name, s.admission_number, m.marks, m.is_absent
            FROM students s LEFT JOIN exam_marks m ON m.student_id = s.id AND m.exam_subject_id = %s
            WHERE s.id IN ({placeholders}) ORDER BY s.full_name
            """,
            (paper_id, *student_ids),
        )
    return MarkSheet(
        paper=_paper_out(paper, user, teacher_id),
        rows=[
            MarkSheetRow(
                student_id=r["id"],
                full_name=r["full_name"],
                admission_number=r["admission_number"],
                marks=_f(r["marks"]) if r["marks"] is not None else None,
                is_absent=bool(r["is_absent"]),
            )
            for r in rows
        ],
    )


async def save_marks(user: CurrentUser, paper_id: str, payload: SaveMarksRequest) -> MarkSheet:
    paper = await _get_paper(user, paper_id)
    teacher_id = await _teacher_id(user)
    if not _can_mark(user, teacher_id, paper):
        raise _not_found("paper")
    if paper["published_at"]:
        raise _LOCKED
    roster = set(await _roster(paper))
    unknown = [e.student_id for e in payload.entries if e.student_id not in roster]
    if unknown:
        raise AppError(status.HTTP_400_BAD_REQUEST, "unknown_student", "Some students aren't in this class.")
    too_high = [e for e in payload.entries if e.marks is not None and e.marks > Decimal(paper["max_marks"])]
    if too_high:
        raise AppError(status.HTTP_400_BAD_REQUEST, "marks_above_max", f"Marks can't be more than {_f(paper['max_marks']):g}.")

    before = {
        r["student_id"]: r for r in await fetch_all("SELECT student_id, marks, is_absent FROM exam_marks WHERE exam_subject_id = %s", (paper_id,))
    }
    previously_absent = {sid for sid, r in before.items() if r["is_absent"]}
    async with db.pool.acquire() as conn:
        await conn.begin()
        async with conn.cursor() as cur:
            for entry in payload.entries:
                if entry.marks is None and not entry.is_absent:
                    # Cleared: no longer entered.
                    await cur.execute("DELETE FROM exam_marks WHERE exam_subject_id = %s AND student_id = %s", (paper_id, entry.student_id))
                    continue
                await cur.execute(
                    """
                    INSERT INTO exam_marks (id, school_id, exam_subject_id, student_id, marks, is_absent, entered_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE marks = VALUES(marks), is_absent = VALUES(is_absent), entered_by = VALUES(entered_by)
                    """,
                    (str(uuid.uuid4()), user.school_id, paper_id, entry.student_id, entry.marks, entry.is_absent, user.id),
                )
        await conn.commit()

    for entry in payload.entries:
        if entry.is_absent and entry.student_id not in previously_absent:
            await _alert_exam_absence(paper, entry.student_id, user.id)
    await _audit_mark_changes(user, paper, before, payload)
    return await mark_sheet(user, paper_id)


def _mark_text(marks, is_absent) -> str:
    if is_absent:
        return "AB"
    return "—" if marks is None else f"{Decimal(marks).normalize():f}"


async def _audit_mark_changes(user: CurrentUser, paper: dict, before: dict, payload: SaveMarksRequest) -> None:
    """Only changes to marks already entered go to the audit log (first entries are ordinary work)."""
    changed = []
    for entry in payload.entries:
        old = before.get(entry.student_id)
        if old is None:
            continue
        old_text, new_text = _mark_text(old["marks"], old["is_absent"]), _mark_text(entry.marks, entry.is_absent)
        if old_text != new_text:
            changed.append({"student_id": entry.student_id, "from": old_text, "to": new_text})
    if not changed:
        return
    names = {
        r["id"]: r["full_name"]
        for r in await fetch_all(
            "SELECT id, full_name FROM students WHERE id IN ({})".format(", ".join(["%s"] * len(changed))), tuple(c["student_id"] for c in changed)
        )
    }
    for c in changed:
        c["student"] = names.get(c["student_id"], "")
    info = await fetch_one(
        """
        SELECT e.name AS exam_name, sub.name AS subject_name, c.name AS class_name, c.section
        FROM exam_subjects es JOIN exams e ON e.id = es.exam_id JOIN subjects sub ON sub.id = es.subject_id JOIN classes c ON c.id = es.class_id
        WHERE es.id = %s
        """,
        (paper["id"],),
    )
    listed = ", ".join(f"{c['student']} {c['from']}→{c['to']}" for c in changed[:5]) + (" …" if len(changed) > 5 else "")
    await audit.record(
        user, "marks.changed",
        f"Changed {info['subject_name']} marks in {info['exam_name']} ({info['class_name']} - {info['section']}): {listed}",
        entity_type="exam_paper", entity_id=paper["id"], details=changed,
    )


async def _alert_exam_absence(paper: dict, student_id: str, author_id: str) -> None:
    day = paper["exam_date"] or alerts.today_ist()

    def build(ctx: dict):
        text = (
            f"Dear Parent, {ctx['full_name']} was absent for the {paper['subject_name']} exam "
            f"({paper['exam_name']}) on {day:%d %b %Y}. - {ctx['school_name']}"
        )
        variables = {
            "student": ctx["full_name"], "class": f"{ctx['class_name']} {ctx['section']}", "date": f"{day:%d %b %Y}",
            "school": ctx["school_name"], "category": "missed an exam", "subject": paper["subject_name"], "note": paper["exam_name"],
        }
        return text, variables

    await alerts.create_alert(
        student_id=student_id, kind="remark", dedupe_key=f"exam_absent:{paper['id']}:{student_id}", build_message=build, created_by=author_id
    )


# --- Results ------------------------------------------------------------------


async def _class_results(exam: dict, class_row: dict) -> ClassResults:
    papers = await fetch_all(
        """
        SELECT es.id, es.subject_id, es.max_marks, es.pass_marks, sub.name AS subject_name, sub.credits FROM exam_subjects es
        JOIN subjects sub ON sub.id = es.subject_id WHERE es.exam_id = %s AND es.class_id = %s ORDER BY sub.name
        """,
        (exam["id"], class_row["id"]),
    )
    # Who sat the exam in this class: its current students, plus anyone with marks here
    # (they may since have moved up a year, left, or graduated).
    students = await fetch_all(
        """
        SELECT s.id, s.full_name, s.admission_number FROM students s
        WHERE (s.class_id = %s AND s.status = 'active')
           OR s.id IN (SELECT m.student_id FROM exam_marks m JOIN exam_subjects es ON es.id = m.exam_subject_id
                       WHERE es.exam_id = %s AND es.class_id = %s)
        ORDER BY s.full_name
        """,
        (class_row["id"], exam["id"], class_row["id"]),
    )
    marks = {}
    if papers:
        placeholders = ", ".join(["%s"] * len(papers))
        for m in await fetch_all(
            f"SELECT exam_subject_id, student_id, marks, is_absent FROM exam_marks WHERE exam_subject_id IN ({placeholders})",
            tuple(p["id"] for p in papers),
        ):
            marks[(m["exam_subject_id"], m["student_id"])] = m

    supplementary = exam["exam_type"] == "supplementary"
    weight = Decimal(exam["internal_weight"] or 0) if exam["exam_type"] == "semester" else Decimal(0)
    internals = await _internal_percentages(_internal_ids(exam), class_row["id"]) if weight else {}
    electives = {p["id"]: await elective_roster(class_row["id"], p["subject_id"]) for p in papers}

    results = []
    for student in students:
        paper_results, total, max_total, complete, passed = [], Decimal(0), Decimal(0), True, True
        for paper in papers:
            entry = marks.get((paper["id"], student["id"]))
            if entry is None and supplementary:
                continue  # only backlog subjects are written in a supplementary exam
            if entry is None and electives[paper["id"]] is not None and student["id"] not in electives[paper["id"]]:
                continue  # an elective the student didn't choose
            if entry is None:
                complete, passed = False, False
                paper_results.append(PaperResult(subject_name=paper["subject_name"], max_marks=_f(paper["max_marks"]),
                                                 pass_marks=_f(paper["pass_marks"]), marks=None, is_absent=False, grade=None,
                                                 passed=None, credits=float(paper["credits"])))
                continue
            got = Decimal(entry["marks"] or 0)
            paper_passed = not entry["is_absent"] and got >= Decimal(paper["pass_marks"])
            internal = external = combined = None
            if weight:
                # Internal marks (average of the internal exams) plus the semester-end paper, out of 100.
                internal = Decimal(internals.get((paper["subject_id"], student["id"]), 0)) * weight / 100
                external = got / Decimal(paper["max_marks"]) * (100 - weight)
                combined = internal + external
                paper_passed = paper_passed and combined >= 40
                total += combined
                max_total += 100
            else:
                total += got
                max_total += Decimal(paper["max_marks"])
            passed = passed and paper_passed
            if entry["is_absent"]:
                grade = "AB"
            elif not paper_passed:
                grade = "F"
            else:
                grade = grade_for(float(combined if weight else got * 100 / Decimal(paper["max_marks"])))
            paper_results.append(
                PaperResult(
                    subject_name=paper["subject_name"],
                    max_marks=_f(paper["max_marks"]),
                    pass_marks=_f(paper["pass_marks"]),
                    marks=None if entry["is_absent"] else _f(got),
                    is_absent=bool(entry["is_absent"]),
                    grade=grade,
                    passed=paper_passed,
                    credits=float(paper["credits"]),
                    grade_point=GRADE_POINTS[grade],
                    internal=_f(internal) if internal is not None else None,
                    external=_f(external) if external is not None else None,
                    combined=_f(combined) if combined is not None else None,
                )
            )
        percentage = round(float(total * 100 / max_total), 2) if max_total else None
        is_complete = complete and bool(paper_results)
        if supplementary and not paper_results:
            continue  # not writing anything in this supplementary exam
        results.append(
            StudentResult(
                student_id=student["id"],
                full_name=student["full_name"],
                admission_number=student["admission_number"],
                papers=paper_results,
                total=_f(total),
                max_total=_f(max_total),
                percentage=percentage,
                grade=grade_for(percentage) if complete else None,
                complete=is_complete,
                passed=passed if complete and papers else None,
                rank=None,
                sgpa=gpa(paper_results) if is_complete else None,
                credits_total=sum(p.credits for p in paper_results),
                credits_earned=sum(p.credits for p in paper_results if p.passed),
            )
        )

    ranked = sorted((r for r in results if r.complete), key=lambda r: r.percentage, reverse=True)
    for position, result in enumerate(ranked):
        previous = ranked[position - 1] if position else None
        result.rank = previous.rank if previous and previous.percentage == result.percentage else position + 1

    stats = []
    for paper in papers:
        values = [p for r in results for p in r.papers if p.subject_name == paper["subject_name"] and (p.marks is not None or p.is_absent)]
        scored = [p.marks for p in values if p.marks is not None]
        stats.append(
            SubjectStats(
                subject_name=paper["subject_name"],
                max_marks=_f(paper["max_marks"]),
                average=round(sum(scored) / len(scored), 2) if scored else None,
                highest=max(scored) if scored else None,
                passed=sum(1 for p in values if p.passed),
                appeared=len(values),
            )
        )
    return ClassResults(
        exam_id=exam["id"],
        exam_name=exam["name"],
        class_name=class_row["name"],
        section=class_row["section"],
        published=exam["published_at"] is not None,
        subjects=[p["subject_name"] for p in papers],
        students=results,
        subject_stats=stats,
    )


async def _require_class_view(user: CurrentUser, class_id: str) -> dict:
    """Admins see every class's results; a teacher sees those of classes they are class teacher of."""
    class_row = await fetch_one("SELECT * FROM classes WHERE id = %s AND school_id = %s", (class_id, user.school_id))
    if class_row is None:
        raise _not_found("class")
    if user.role != "admin" and class_row["teacher_id"] != await _teacher_id(user):
        raise AppError(status.HTTP_403_FORBIDDEN, "forbidden", "Only the class teacher or an admin can see the whole class's results.")
    return class_row


async def class_results(user: CurrentUser, exam_id: str, class_id: str) -> ClassResults:
    exam = await _get_exam(user, exam_id)
    return await _class_results(exam, await _require_class_view(user, class_id))


async def _report_card(exam: dict, class_row: dict, student_id: str) -> ReportCard:
    results = await _class_results(exam, class_row)
    result = next((r for r in results.students if r.student_id == student_id), None)
    if result is None:
        raise _not_found("student")
    info = await fetch_one(
        """
        SELECT sc.name AS school_name, u.full_name AS class_teacher_name, d.name AS department_name FROM classes c
        JOIN schools sc ON sc.id = c.school_id JOIN teachers t ON t.id = c.teacher_id JOIN users u ON u.id = t.user_id
        LEFT JOIN departments d ON d.id = c.department_id
        WHERE c.id = %s
        """,
        (class_row["id"],),
    )
    return ReportCard(
        exam_type=exam["exam_type"],
        department_name=info["department_name"],
        program=class_row["program"],
        semester=class_row["semester"],
        school_name=info["school_name"],
        exam_name=exam["name"],
        term_label=exam["term_label"],
        academic_year=exam["academic_year"],
        class_name=class_row["name"],
        section=class_row["section"],
        class_teacher_name=info["class_teacher_name"],
        class_size=len(results.students),
        result=result,
    )


async def _exam_class_for(student: dict, exam_id: str) -> str:
    """The class the student sat this exam in: where their marks are, else their current class."""
    row = await fetch_one(
        """
        SELECT es.class_id FROM exam_marks m JOIN exam_subjects es ON es.id = m.exam_subject_id
        WHERE es.exam_id = %s AND m.student_id = %s LIMIT 1
        """,
        (exam_id, student["id"]),
    )
    return row["class_id"] if row else student["class_id"]


async def report_card(user: CurrentUser, exam_id: str, student_id: str) -> ReportCard:
    exam = await _get_exam(user, exam_id)
    student = await fetch_one("SELECT id, class_id FROM students WHERE id = %s AND school_id = %s", (student_id, user.school_id))
    if student is None:
        raise _not_found("student")
    card = await _report_card(exam, await _require_class_view(user, await _exam_class_for(student, exam_id)), student_id)
    card.cgpa = await cgpa(student_id)
    return card


async def published_results(student_id: str) -> list[PublishedResult]:
    """A student's report cards for published exams that include their class (for the student and their parents)."""
    student = await fetch_one("SELECT * FROM students WHERE id = %s", (student_id,))
    # Published exams of their current class, and any earlier exam they have marks in (previous years).
    rows = await fetch_all(
        """
        SELECT DISTINCT e.id AS exam_id, es.class_id, e.published_at FROM exams e JOIN exam_subjects es ON es.exam_id = e.id
        WHERE e.school_id = %s AND e.published_at IS NOT NULL
          AND (es.class_id = %s OR es.id IN (SELECT exam_subject_id FROM exam_marks WHERE student_id = %s))
        ORDER BY e.published_at DESC
        """,
        (student["school_id"], student["class_id"], student_id),
    )
    results, seen = [], set()
    for row in rows:
        if row["exam_id"] in seen:
            continue
        seen.add(row["exam_id"])
        exam = await fetch_one("SELECT * FROM exams WHERE id = %s", (row["exam_id"],))
        class_id = await _exam_class_for(student, exam["id"])
        class_row = await fetch_one("SELECT * FROM classes WHERE id = %s", (class_id,))
        results.append(PublishedResult(exam_id=exam["id"], report_card=await _report_card(exam, class_row, student_id)))
    # CGPA on each semester-end / supplementary card: cumulative over it and every earlier one,
    # a subject counting once with its latest attempt (a supplementary pass replaces the F).
    latest: dict[str, PaperResult] = {}
    for published in reversed(results):
        card = published.report_card
        if card.exam_type == "semester" and card.result.complete or card.exam_type == "supplementary":
            latest.update({p.subject_name: p for p in card.result.papers if p.grade is not None})
            card.cgpa = gpa(list(latest.values()))
    return results


async def backlogs(student_id: str) -> list[BacklogOut]:
    """Subjects whose latest published semester-end or supplementary attempt is F or AB."""
    latest: dict[str, tuple[PaperResult, str]] = {}
    for published in reversed(await published_results(student_id)):
        card = published.report_card
        if card.exam_type in ("semester", "supplementary"):
            for p in card.result.papers:
                if p.grade is not None:
                    latest[p.subject_name] = (p, card.exam_name)
    return [
        BacklogOut(subject_name=name, exam_name=exam_name, grade=p.grade)
        for name, (p, exam_name) in sorted(latest.items())
        if p.passed is False
    ]


async def class_backlogs(user: CurrentUser, class_id: str) -> list[StudentBacklogs]:
    await _require_class_view(user, class_id)
    students = await fetch_all(
        "SELECT id, full_name, admission_number FROM students WHERE class_id = %s AND status = 'active' ORDER BY admission_number",
        (class_id,),
    )
    result = []
    for s in students:
        items = await backlogs(s["id"])
        if items:
            result.append(StudentBacklogs(student_id=s["id"], full_name=s["full_name"], admission_number=s["admission_number"], backlogs=items))
    return result


async def _internal_percentages(exam_ids: list[str], class_id: str) -> dict[tuple[str, str], Decimal]:
    """Average internal percentage per (subject, student) over the internal exams' papers for the batch."""
    if not exam_ids:
        return {}
    placeholders = ", ".join(["%s"] * len(exam_ids))
    rows = await fetch_all(
        f"""
        SELECT es.subject_id, m.student_id, m.marks, m.is_absent, es.max_marks
        FROM exam_marks m JOIN exam_subjects es ON es.id = m.exam_subject_id
        WHERE es.exam_id IN ({placeholders}) AND es.class_id = %s
        """,
        (*exam_ids, class_id),
    )
    sums: dict[tuple[str, str], list[Decimal]] = {}
    for r in rows:
        pct = Decimal(0) if r["is_absent"] else Decimal(r["marks"] or 0) * 100 / Decimal(r["max_marks"])
        sums.setdefault((r["subject_id"], r["student_id"]), []).append(pct)
    return {key: sum(values) / len(values) for key, values in sums.items()}


async def cgpa(student_id: str) -> float | None:
    """CGPA over every published semester-end exam the student has complete marks in."""
    results = await published_results(student_id)
    return next((r.report_card.cgpa for r in results if r.report_card.cgpa is not None), None)
