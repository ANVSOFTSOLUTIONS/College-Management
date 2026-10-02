"""Faculty feedback: students rate each subject's faculty, anonymously.

The admin opens a feedback round (e.g. "Odd semester 2026"). While it's open,
each student rates every subject of their batch once on five questions (1-5)
with an optional comment. Responses keep a keyed hash of (round, student,
subject) to stop repeat answers, never the student's id. The admin sees every
faculty member's averages, a HOD sees their department's faculty, and faculty
see their own once the round is closed.
"""

import hashlib
import hmac
import uuid

import aiomysql
from fastapi import status
from pydantic import BaseModel, Field, field_validator

from app.api.deps import CurrentUser
from app.core.config import get_settings
from app.core.errors import AppError
from app.db.helpers import execute, fetch_all, fetch_one
from app.modules.electives.service import elective_roster
from app.modules.hod.service import hod_departments

QUESTIONS = [
    "Knowledge of the subject",
    "Explains clearly",
    "Comes on time and completes the syllabus",
    "Clears doubts and is approachable",
    "Uses examples, practicals and real-world cases",
]


class RoundIn(BaseModel):
    title: str = Field(min_length=1, max_length=150)

    _strip = field_validator("title", mode="before")(lambda v: v.strip() if isinstance(v, str) else v)


class OpenIn(BaseModel):
    is_open: bool


class RoundOut(BaseModel):
    id: str
    title: str
    is_open: bool
    responses: int


class ResponseIn(BaseModel):
    subject_id: str
    ratings: list[int] = Field(min_length=len(QUESTIONS), max_length=len(QUESTIONS))
    comment: str | None = Field(default=None, max_length=1000)

    @field_validator("ratings")
    @classmethod
    def _range(cls, value: list[int]) -> list[int]:
        if any(r < 1 or r > 5 for r in value):
            raise ValueError("Each rating is from 1 to 5.")
        return value


class FacultyScore(BaseModel):
    teacher_id: str
    teacher_name: str
    department: str
    subject_name: str
    class_name: str
    section: str
    responses: int
    students: int
    averages: list[float]
    overall: float
    comments: list[str]


class FeedbackReport(BaseModel):
    round: RoundOut
    questions: list[str]
    faculty: list[FacultyScore]


class PendingSubject(BaseModel):
    subject_id: str
    subject_name: str
    teacher_name: str
    done: bool


class StudentRound(BaseModel):
    id: str
    title: str
    questions: list[str]
    subjects: list[PendingSubject]


def _round_out(row: dict) -> RoundOut:
    return RoundOut(id=row["id"], title=row["title"], is_open=bool(row["is_open"]), responses=row.get("responses") or 0)


async def _get_round(user: CurrentUser, round_id: str) -> dict:
    row = await fetch_one(
        "SELECT r.*, (SELECT COUNT(*) FROM feedback_responses f WHERE f.round_id = r.id) AS responses FROM feedback_rounds r WHERE r.id = %s AND r.school_id = %s",
        (round_id, user.school_id),
    )
    if row is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "round_not_found", "Feedback round not found.")
    return row


async def list_rounds(user: CurrentUser) -> list[RoundOut]:
    rows = await fetch_all(
        """
        SELECT r.*, (SELECT COUNT(*) FROM feedback_responses f WHERE f.round_id = r.id) AS responses
        FROM feedback_rounds r WHERE r.school_id = %s ORDER BY r.created_at DESC
        """,
        (user.school_id,),
    )
    return [_round_out(r) for r in rows]


async def create_round(user: CurrentUser, payload: RoundIn) -> RoundOut:
    round_id = str(uuid.uuid4())
    await execute("INSERT INTO feedback_rounds (id, school_id, title) VALUES (%s, %s, %s)", (round_id, user.school_id, payload.title))
    return _round_out(await _get_round(user, round_id))


async def set_open(user: CurrentUser, round_id: str, is_open: bool) -> RoundOut:
    await _get_round(user, round_id)
    await execute("UPDATE feedback_rounds SET is_open = %s WHERE id = %s", (is_open, round_id))
    return _round_out(await _get_round(user, round_id))


async def delete_round(user: CurrentUser, round_id: str) -> None:
    await _get_round(user, round_id)
    await execute("DELETE FROM feedback_rounds WHERE id = %s", (round_id,))


async def _scores(round_id: str, where: str = "", params: tuple = ()) -> list[FacultyScore]:
    rows = await fetch_all(
        f"""
        SELECT f.teacher_id, f.class_id, f.subject_id, f.ratings, f.comment, u.full_name AS teacher_name,
               COALESCE(d.name, t.department, '') AS department, s.name AS subject_name, c.name AS class_name, c.section
        FROM feedback_responses f JOIN teachers t ON t.id = f.teacher_id JOIN users u ON u.id = t.user_id
        LEFT JOIN departments d ON d.id = t.department_id
        JOIN subjects s ON s.id = f.subject_id JOIN classes c ON c.id = f.class_id
        WHERE f.round_id = %s {where}
        ORDER BY u.full_name, s.name, c.name, f.created_at
        """,
        (round_id, *params),
    )
    groups: dict[tuple, list[dict]] = {}
    for r in rows:
        groups.setdefault((r["teacher_id"], r["subject_id"], r["class_id"]), []).append(r)
    result = []
    for (teacher_id, subject_id, class_id), items in groups.items():
        ratings = [[int(x) for x in i["ratings"].split(",")] for i in items]
        averages = [round(sum(col) / len(col), 2) for col in zip(*ratings)]
        students = await fetch_one("SELECT COUNT(*) AS n FROM students WHERE class_id = %s AND status = 'active'", (class_id,))
        chosen = await elective_roster(class_id, subject_id)
        first = items[0]
        result.append(
            FacultyScore(
                teacher_id=teacher_id, teacher_name=first["teacher_name"], department=first["department"], subject_name=first["subject_name"],
                class_name=first["class_name"], section=first["section"], responses=len(items),
                students=len(chosen) if chosen is not None else students["n"],
                averages=averages, overall=round(sum(averages) / len(averages), 2),
                comments=[i["comment"] for i in items if i["comment"]],
            )
        )
    return result


async def report(user: CurrentUser, round_id: str) -> FeedbackReport:
    row = await _get_round(user, round_id)
    if user.role == "admin":
        faculty = await _scores(round_id)
    else:
        departments = await hod_departments(user)
        if not departments:
            raise AppError(status.HTTP_403_FORBIDDEN, "forbidden", "Only the admin or a head of department can see this report.")
        ids = [d["id"] for d in departments]
        faculty = await _scores(round_id, f"AND t.department_id IN ({', '.join(['%s'] * len(ids))})", tuple(ids))
    return FeedbackReport(round=_round_out(row), questions=QUESTIONS, faculty=faculty)


async def mine(user: CurrentUser) -> list[FeedbackReport]:
    """A faculty member's own scores, from closed rounds only."""
    teacher = await fetch_one("SELECT id FROM teachers WHERE user_id = %s AND school_id = %s", (user.id, user.school_id))
    if teacher is None:
        return []
    rounds = await fetch_all(
        """
        SELECT r.*, (SELECT COUNT(*) FROM feedback_responses f WHERE f.round_id = r.id) AS responses
        FROM feedback_rounds r WHERE r.school_id = %s AND r.is_open = 0 ORDER BY r.created_at DESC
        """,
        (user.school_id,),
    )
    result = []
    for r in rounds:
        faculty = await _scores(r["id"], "AND f.teacher_id = %s", (teacher["id"],))
        if faculty:
            result.append(FeedbackReport(round=_round_out(r), questions=QUESTIONS, faculty=faculty))
    return result


# --- Student app ----------------------------------------------------------------


def _student_hash(round_id: str, student_id: str, subject_id: str) -> str:
    settings = get_settings()
    key = (settings.data_encryption_key or settings.jwt_secret_key).encode()
    return hmac.new(key, f"feedback:{round_id}:{student_id}:{subject_id}".encode(), hashlib.sha256).hexdigest()


async def _student_subjects(student: dict) -> list[dict]:
    rows = await fetch_all(
        """
        SELECT cs.subject_id, s.name AS subject_name, cs.teacher_id, u.full_name AS teacher_name
        FROM class_subjects cs JOIN subjects s ON s.id = cs.subject_id
        JOIN teachers t ON t.id = cs.teacher_id JOIN users u ON u.id = t.user_id
        WHERE cs.class_id = %s ORDER BY s.name
        """,
        (student["class_id"],),
    )
    result = []
    for r in rows:
        chosen = await elective_roster(student["class_id"], r["subject_id"])
        if chosen is None or student["id"] in chosen:
            result.append(r)
    return result


async def student_rounds(student: dict) -> list[StudentRound]:
    rounds = await fetch_all(
        "SELECT * FROM feedback_rounds WHERE school_id = %s AND is_open = 1 ORDER BY created_at DESC", (student["school_id"],)
    )
    subjects = await _student_subjects(student)
    result = []
    for r in rounds:
        items = []
        for s in subjects:
            done = await fetch_one(
                "SELECT 1 FROM feedback_responses WHERE round_id = %s AND student_hash = %s", (r["id"], _student_hash(r["id"], student["id"], s["subject_id"]))
            )
            items.append(PendingSubject(subject_id=s["subject_id"], subject_name=s["subject_name"], teacher_name=s["teacher_name"], done=bool(done)))
        result.append(StudentRound(id=r["id"], title=r["title"], questions=QUESTIONS, subjects=items))
    return result


async def submit(student: dict, round_id: str, payload: ResponseIn) -> list[StudentRound]:
    row = await fetch_one("SELECT is_open FROM feedback_rounds WHERE id = %s AND school_id = %s", (round_id, student["school_id"]))
    if row is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "round_not_found", "Feedback round not found.")
    if not row["is_open"]:
        raise AppError(status.HTTP_409_CONFLICT, "round_closed", "This feedback round is closed.")
    subject = next((s for s in await _student_subjects(student) if s["subject_id"] == payload.subject_id), None)
    if subject is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "subject_not_found", "This subject isn't in your batch.")
    try:
        await execute(
            """
            INSERT INTO feedback_responses (id, round_id, class_id, subject_id, teacher_id, student_hash, ratings, comment)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (str(uuid.uuid4()), round_id, student["class_id"], payload.subject_id, subject["teacher_id"],
             _student_hash(round_id, student["id"], payload.subject_id), ",".join(str(r) for r in payload.ratings),
             (payload.comment or "").strip() or None),
        )
    except aiomysql.IntegrityError as exc:
        raise AppError(status.HTTP_409_CONFLICT, "already_submitted", "You already gave feedback for this subject.") from exc
    return await student_rounds(student)
