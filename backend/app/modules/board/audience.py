"""Who belongs to which class: shared by notices and homework."""

from pathlib import Path

from fastapi import UploadFile, status
from fastapi.responses import FileResponse

from app.api.deps import CurrentUser
from app.core.errors import AppError
from app.db.helpers import fetch_all, fetch_one
from app.modules.students.files import DOCUMENT_TYPES, MAX_DOCUMENT_BYTES, private_path, save_private_file

ATTACHMENT_NAME_MAX = 150


async def teacher_id(user: CurrentUser) -> str | None:
    row = await fetch_one("SELECT id FROM teachers WHERE user_id = %s AND school_id = %s", (user.id, user.school_id))
    return row["id"] if row else None


async def teaching_class_ids(user: CurrentUser) -> set[str]:
    """Current classes a teacher is class teacher or a subject teacher of."""
    tid = await teacher_id(user)
    if tid is None:
        return set()
    rows = await fetch_all(
        """
        SELECT DISTINCT c.id FROM classes c
        LEFT JOIN class_subjects cs ON cs.class_id = c.id AND cs.teacher_id = %s
        WHERE c.school_id = %s AND c.is_archived = 0 AND (c.teacher_id = %s OR cs.id IS NOT NULL)
        """,
        (tid, user.school_id, tid),
    )
    return {r["id"] for r in rows}


async def children(user: CurrentUser) -> list[dict]:
    return await fetch_all(
        """
        SELECT s.id, s.class_id, s.school_id, s.full_name FROM parent_students ps JOIN students s ON s.id = ps.student_id
        WHERE ps.parent_user_id = %s AND s.status = 'active'
        """,
        (user.id,),
    )


async def school_class_ids(school_id: str, class_ids: list[str]) -> list[str]:
    """Validates that every class is a current class of the school."""
    class_ids = list(dict.fromkeys(class_ids))
    if not class_ids:
        return []
    placeholders = ", ".join(["%s"] * len(class_ids))
    rows = await fetch_all(
        f"SELECT id FROM classes WHERE school_id = %s AND is_archived = 0 AND id IN ({placeholders})", (school_id, *class_ids)
    )
    if len(rows) != len(class_ids):
        raise AppError(status.HTTP_404_NOT_FOUND, "class_not_found", "Class not found.")
    return class_ids


async def recipients(school_id: str, class_ids: list[str], *, staff: bool, parents: bool, students: bool = False) -> list[str]:
    """User ids to notify; no class ids means the whole college."""
    where, params = ("s.class_id IN ({})".format(", ".join(["%s"] * len(class_ids))), tuple(class_ids)) if class_ids else ("s.school_id = %s", (school_id,))
    ids: list[str] = []
    roles = [role for role, wanted in (("parent", parents), ("student", students)) if wanted]
    if roles:
        # Portal logins linked to the students: parents, and students' own accounts.
        role_placeholders = ", ".join(["%s"] * len(roles))
        ids += [
            r["parent_user_id"]
            for r in await fetch_all(
                f"""
                SELECT DISTINCT ps.parent_user_id FROM parent_students ps
                JOIN students s ON s.id = ps.student_id JOIN users u ON u.id = ps.parent_user_id
                WHERE {where} AND s.status = 'active' AND u.role IN ({role_placeholders})
                """,
                (*params, *roles),
            )
        ]
    if staff:
        if class_ids:
            placeholders = ", ".join(["%s"] * len(class_ids))
            rows = await fetch_all(
                f"""
                SELECT t.user_id FROM classes c JOIN teachers t ON t.id = c.teacher_id WHERE c.id IN ({placeholders})
                UNION SELECT t.user_id FROM class_subjects cs JOIN teachers t ON t.id = cs.teacher_id WHERE cs.class_id IN ({placeholders})
                """,
                (*class_ids, *class_ids),
            )
        else:
            rows = await fetch_all(
                "SELECT u.id AS user_id FROM teachers t JOIN users u ON u.id = t.user_id WHERE t.school_id = %s AND u.status = 'active'",
                (school_id,),
            )
        ids += [r["user_id"] for r in rows]
    return ids


async def save_attachment(school_id: str, kind: str, file: UploadFile) -> tuple[str, str, str]:
    """Stores a PDF or image and returns (path, original name, content type)."""
    path, _ = await save_private_file(folder=Path(school_id) / kind, file=file, allowed_types=DOCUMENT_TYPES, max_bytes=MAX_DOCUMENT_BYTES)
    name = (file.filename or "attachment").rsplit("/", 1)[-1].rsplit("\\", 1)[-1][:ATTACHMENT_NAME_MAX]
    return path, name, file.content_type


def attachment_response(row: dict) -> FileResponse:
    if not row["attachment_path"]:
        raise AppError(status.HTTP_404_NOT_FOUND, "file_not_found", "File not found.")
    return FileResponse(
        private_path(row["attachment_path"]),
        media_type=row["attachment_type"],
        filename=row["attachment_name"],
        content_disposition_type="inline",
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )
