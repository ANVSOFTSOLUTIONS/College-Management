"""Question bank: previous and model question papers per subject (PDF or image).

Admins and faculty upload; students see papers of the subjects taught in
their batch, and parents of their child's batch.
"""

import hashlib
import hmac
import time
import uuid
from datetime import datetime

from fastapi import UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.api.deps import CurrentUser
from app.core.config import get_settings
from app.core.errors import AppError
from app.db.helpers import execute, fetch_all, fetch_one
from app.modules.board import audience
from app.modules.students.files import delete_private_file


class PaperOut(BaseModel):
    id: str
    subject_id: str
    subject_name: str
    subject_code: str
    title: str
    exam_year: str
    regulation: str
    attachment_name: str
    attachment_type: str
    uploaded_by_name: str | None
    created_at: datetime


_SELECT = """
    SELECT q.*, s.name AS subject_name, s.code AS subject_code, u.full_name AS uploaded_by_name
    FROM question_papers q JOIN subjects s ON s.id = q.subject_id LEFT JOIN users u ON u.id = q.uploaded_by
"""


def _out(row: dict) -> PaperOut:
    return PaperOut(**{k: row[k] for k in PaperOut.model_fields})


async def list_papers(user: CurrentUser, subject_id: str | None) -> list[PaperOut]:
    where, params = "q.school_id = %s", [user.school_id]
    if subject_id:
        where += " AND q.subject_id = %s"
        params.append(subject_id)
    rows = await fetch_all(f"{_SELECT} WHERE {where} ORDER BY s.name, q.exam_year DESC, q.created_at DESC", tuple(params))
    return [_out(r) for r in rows]


async def upload(user: CurrentUser, subject_id: str, title: str, exam_year: str, regulation: str, file: UploadFile) -> PaperOut:
    title = title.strip()
    if not 2 <= len(title) <= 150 or len(exam_year.strip()) > 9 or len(regulation.strip()) > 20:
        raise AppError(status.HTTP_400_BAD_REQUEST, "invalid_paper", "Give a title (2-150 characters), a year and regulation of normal length.")
    if not await fetch_one("SELECT id FROM subjects WHERE id = %s AND school_id = %s", (subject_id, user.school_id)):
        raise AppError(status.HTTP_404_NOT_FOUND, "subject_not_found", "Subject not found.")
    path, name, content_type = await audience.save_attachment(user.school_id, "question-papers", file)
    paper_id = str(uuid.uuid4())
    await execute(
        """
        INSERT INTO question_papers (id, school_id, subject_id, title, exam_year, regulation, attachment_path, attachment_name, attachment_type, uploaded_by)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (paper_id, user.school_id, subject_id, title, exam_year.strip(), regulation.strip(), path, name, content_type, user.id),
    )
    return _out(await fetch_one(f"{_SELECT} WHERE q.id = %s", (paper_id,)))


async def _row(school_id: str, paper_id: str) -> dict:
    row = await fetch_one("SELECT * FROM question_papers WHERE id = %s AND school_id = %s", (paper_id, school_id))
    if row is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "paper_not_found", "Question paper not found.")
    return row


async def delete(user: CurrentUser, paper_id: str) -> None:
    row = await _row(user.school_id, paper_id)
    if user.role != "admin" and row["uploaded_by"] != user.id:
        raise AppError(status.HTTP_403_FORBIDDEN, "forbidden", "Only the admin or the uploader can delete this.")
    await execute("DELETE FROM question_papers WHERE id = %s", (paper_id,))
    delete_private_file(row["attachment_path"])


async def file(user: CurrentUser, paper_id: str) -> FileResponse:
    return audience.attachment_response(await _row(user.school_id, paper_id))


async def for_student(student: dict) -> list[PaperOut]:
    rows = await fetch_all(
        f"""{_SELECT} WHERE q.school_id = %s AND q.subject_id IN (SELECT subject_id FROM class_subjects WHERE class_id = %s)
        ORDER BY s.name, q.exam_year DESC, q.created_at DESC""",
        (student["school_id"], student["class_id"]),
    )
    return [_out(r) for r in rows]


async def student_file(student: dict, paper_id: str) -> FileResponse:
    row = await _row(student["school_id"], paper_id)
    if not await fetch_one("SELECT 1 FROM class_subjects WHERE class_id = %s AND subject_id = %s", (student["class_id"], row["subject_id"])):
        raise AppError(status.HTTP_404_NOT_FOUND, "paper_not_found", "Question paper not found.")
    return audience.attachment_response(row)


# The app opens papers in the phone's browser, which can't send the login token,
# so it asks for a link signed for five minutes instead.
LINK_SECONDS = 300


def _signature(paper_id: str, expires: int) -> str:
    settings = get_settings()
    key = (settings.data_encryption_key or settings.jwt_secret_key).encode()
    return hmac.new(key, f"question-paper:{paper_id}:{expires}".encode(), hashlib.sha256).hexdigest()


class FileLink(BaseModel):
    path: str
    expires_in: int


async def student_link(student: dict, paper_id: str) -> FileLink:
    await student_file(student, paper_id)  # checks the student may see it
    expires = int(time.time()) + LINK_SECONDS
    return FileLink(path=f"/question-papers/download/{paper_id}?expires={expires}&sig={_signature(paper_id, expires)}", expires_in=LINK_SECONDS)


async def signed_file(paper_id: str, expires: int, sig: str) -> FileResponse:
    if expires < time.time() or not hmac.compare_digest(sig, _signature(paper_id, expires)):
        raise AppError(status.HTTP_403_FORBIDDEN, "link_expired", "This link has expired. Open the paper again from the app.")
    row = await fetch_one("SELECT * FROM question_papers WHERE id = %s", (paper_id,))
    if row is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "paper_not_found", "Question paper not found.")
    return audience.attachment_response(row)
