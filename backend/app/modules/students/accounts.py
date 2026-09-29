"""Students' photos, documents and own logins, and the random first passwords for logins."""

import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path

import aiomysql
from fastapi import UploadFile, status

from app.api.deps import CurrentUser
from app.core.errors import AppError
from app.core.security import hash_password, student_login_id
from app.db.database import db
from app.db.helpers import execute, fetch_all, fetch_one
from app.modules.students import files
from app.modules.students.schemas import DOCUMENT_TYPES, LoginCredentials, StudentDocumentOut

# No 0/O, 1/l/I: these passwords get read off printed slips.
_PASSWORD_ALPHABET = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789"


def generate_password(length: int = 8) -> str:
    return "".join(secrets.choice(_PASSWORD_ALPHABET) for _ in range(length))


# --- Photo --------------------------------------------------------------------


async def set_photo(student: dict, file: UploadFile) -> None:
    path, _ = await files.save_private_upload(
        school_id=student["school_id"],
        student_id=student["id"],
        file=file,
        allowed_types=files.PHOTO_TYPES,
        max_bytes=files.MAX_PHOTO_BYTES,
    )
    await execute("UPDATE students SET photo_path = %s WHERE id = %s", (path, student["id"]))
    files.delete_private_file(student["photo_path"])


def photo_file(student: dict) -> Path:
    if not student["photo_path"]:
        raise AppError(status.HTTP_404_NOT_FOUND, "photo_not_found", "No photo uploaded yet.")
    return files.private_path(student["photo_path"])


# --- Documents ----------------------------------------------------------------


def _document_out(row: dict) -> StudentDocumentOut:
    return StudentDocumentOut(
        id=row["id"],
        doc_type=row["doc_type"],
        doc_type_label=DOCUMENT_TYPES[row["doc_type"]],
        title=row["title"],
        original_name=row["original_name"],
        content_type=row["content_type"],
        size_bytes=row["size_bytes"],
        status=row["status"],
        review_note=row["review_note"],
        uploaded_at=row["created_at"].isoformat(),
        reviewed_at=row["reviewed_at"].isoformat() if row["reviewed_at"] else None,
    )


async def list_documents(student: dict) -> list[StudentDocumentOut]:
    rows = await fetch_all(
        "SELECT * FROM student_documents WHERE student_id = %s ORDER BY created_at DESC, id", (student["id"],)
    )
    return [_document_out(row) for row in rows]


async def add_document(student: dict, uploader: CurrentUser, doc_type: str, title: str, file: UploadFile) -> StudentDocumentOut:
    if doc_type not in DOCUMENT_TYPES:
        raise AppError(status.HTTP_400_BAD_REQUEST, "invalid_document_type", "Choose a valid document type.")
    path, size = await files.save_private_upload(
        school_id=student["school_id"],
        student_id=student["id"],
        file=file,
        allowed_types=files.DOCUMENT_TYPES,
        max_bytes=files.MAX_DOCUMENT_BYTES,
    )
    document_id = str(uuid.uuid4())
    # Staff uploads are trusted; a parent's upload waits for review.
    is_staff = uploader.role in ("admin", "teacher")
    await execute(
        """
        INSERT INTO student_documents (id, school_id, student_id, doc_type, title, file_path, content_type, size_bytes,
                                       original_name, status, uploaded_by, reviewed_by, reviewed_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            document_id,
            student["school_id"],
            student["id"],
            doc_type,
            title.strip()[:200],
            path,
            file.content_type,
            size,
            (file.filename or "")[:255],
            "approved" if is_staff else "pending",
            uploader.id,
            uploader.id if is_staff else None,
            datetime.now(timezone.utc) if is_staff else None,
        ),
    )
    return _document_out(await _get_document_row(student, document_id))


async def _get_document_row(student: dict, document_id: str) -> dict:
    row = await fetch_one(
        "SELECT * FROM student_documents WHERE id = %s AND student_id = %s", (document_id, student["id"])
    )
    if row is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "document_not_found", "Document not found.")
    return row


async def review_document(student: dict, reviewer: CurrentUser, document_id: str, new_status: str, note: str) -> StudentDocumentOut:
    await _get_document_row(student, document_id)
    if new_status == "rejected" and not note:
        raise AppError(status.HTTP_400_BAD_REQUEST, "note_required", "Say why the document was rejected so the student can fix it.")
    await execute(
        "UPDATE student_documents SET status = %s, review_note = %s, reviewed_by = %s, reviewed_at = %s WHERE id = %s",
        (new_status, note, reviewer.id, datetime.now(timezone.utc), document_id),
    )
    return _document_out(await _get_document_row(student, document_id))


async def delete_document(student: dict, requester: CurrentUser, document_id: str) -> None:
    row = await _get_document_row(student, document_id)
    if requester.role in ("parent", "student") and row["status"] == "approved":
        raise AppError(status.HTTP_409_CONFLICT, "document_approved", "An approved document can only be removed by the school.")
    await execute("DELETE FROM student_documents WHERE id = %s", (document_id,))
    files.delete_private_file(row["file_path"])


async def document_file(student: dict, document_id: str) -> tuple[Path, str, str]:
    row = await _get_document_row(student, document_id)
    return files.private_path(row["file_path"]), row["content_type"], row["original_name"] or f"document-{document_id}"


# --- Student logins -------------------------------------------------------------
# A college student signs in with the college code and their roll number
# (admission number). Their account is linked to their own record in
# parent_students, so they get the same portal a parent has.


async def _enable_login(cur, student: dict, code: str, password: str | None) -> LoginCredentials:
    login_id = student_login_id(code, student["admission_number"])
    password = password or generate_password()
    if student["user_id"]:
        user_id = student["user_id"]
        await cur.execute(
            """
            UPDATE users SET login_id = %s, password_hash = %s, must_change_password = 1, status = 'active', full_name = %s
            WHERE id = %s
            """,
            (login_id, hash_password(password), student["full_name"], user_id),
        )
    else:
        user_id = str(uuid.uuid4())
        await cur.execute(
            """
            INSERT INTO users (id, school_id, email, login_id, password_hash, must_change_password, role, full_name, status)
            VALUES (%s, %s, NULL, %s, %s, 1, 'student', %s, 'active')
            """,
            (user_id, student["school_id"], login_id, hash_password(password), student["full_name"]),
        )
        await cur.execute("UPDATE students SET user_id = %s WHERE id = %s", (user_id, student["id"]))
    await cur.execute(
        """
        INSERT INTO parent_students (parent_user_id, student_id, school_id) VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE school_id = VALUES(school_id)
        """,
        (user_id, student["id"], student["school_id"]),
    )
    return LoginCredentials(
        student_id=student["id"],
        full_name=student["full_name"],
        school_code=code,
        admission_number=student["admission_number"],
        password=password,
    )


_LOGIN_TAKEN = AppError(status.HTTP_409_CONFLICT, "login_taken", "Another account already uses this roll number to sign in.")


async def enable_login(student: dict, password: str | None) -> LoginCredentials:
    """Creates the student's login, or resets its password; they choose a new one at first sign-in."""
    if student["status"] != "active":
        raise AppError(status.HTTP_409_CONFLICT, "student_left", "This student has left.")
    school = await fetch_one("SELECT code FROM schools WHERE id = %s", (student["school_id"],))
    async with db.pool.acquire() as conn:
        await conn.begin()
        try:
            async with conn.cursor() as cur:
                credentials = await _enable_login(cur, student, school["code"], password)
        except aiomysql.IntegrityError as exc:
            await conn.rollback()
            raise _LOGIN_TAKEN from exc
        await conn.commit()
    return credentials


async def disable_login(student: dict) -> None:
    if student["user_id"]:
        await execute("UPDATE users SET status = 'inactive' WHERE id = %s", (student["user_id"],))


async def enable_class_logins(school_id: str, class_id: str) -> list[LoginCredentials]:
    """Logins for every active student in the batch who has none yet (or whose login is switched off)."""
    school = await fetch_one("SELECT code FROM schools WHERE id = %s", (school_id,))
    rows = await fetch_all(
        """
        SELECT s.* FROM students s LEFT JOIN users u ON u.id = s.user_id
        WHERE s.school_id = %s AND s.class_id = %s AND s.status = 'active' AND (u.id IS NULL OR u.status <> 'active')
        ORDER BY s.admission_number
        """,
        (school_id, class_id),
    )
    results = []
    async with db.pool.acquire() as conn:
        await conn.begin()
        try:
            async with conn.cursor() as cur:
                for student in rows:
                    results.append(await _enable_login(cur, student, school["code"], None))
        except aiomysql.IntegrityError as exc:
            await conn.rollback()
            raise _LOGIN_TAKEN from exc
        await conn.commit()
    return results
