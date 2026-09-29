"""Private storage for student photos and documents.

Unlike the public `uploads/` folder (school logos, banners), nothing here is
reachable by URL: files are streamed by endpoints that check who is asking.
Paths are stored relative to PRIVATE_ROOT.
"""

import uuid
from pathlib import Path

from fastapi import UploadFile, status

from app.core.errors import AppError

PRIVATE_ROOT = Path(__file__).resolve().parents[3] / "private_uploads"

MAX_PHOTO_BYTES = 5 * 1024 * 1024
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024

PHOTO_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
DOCUMENT_TYPES = {**PHOTO_TYPES, "application/pdf": ".pdf"}


async def save_private_upload(
    *, school_id: str, student_id: str, file: UploadFile, allowed_types: dict[str, str], max_bytes: int
) -> tuple[str, int]:
    """Stores the file and returns (relative path, size in bytes)."""
    return await save_private_file(
        folder=Path(school_id) / "students" / student_id, file=file, allowed_types=allowed_types, max_bytes=max_bytes
    )


async def save_private_file(*, folder: Path, file: UploadFile, allowed_types: dict[str, str], max_bytes: int) -> tuple[str, int]:
    """Stores the file under PRIVATE_ROOT/folder and returns (relative path, size in bytes)."""
    extension = allowed_types.get(file.content_type or "")
    if extension is None:
        kinds = "PDF, JPEG, PNG, or WEBP" if "application/pdf" in allowed_types else "JPEG, PNG, or WEBP"
        raise AppError(status.HTTP_400_BAD_REQUEST, "invalid_file_type", f"Only {kinds} files are allowed.")

    contents = await file.read(max_bytes + 1)
    if len(contents) > max_bytes:
        raise AppError(status.HTTP_400_BAD_REQUEST, "file_too_large", f"Files must be {max_bytes // (1024 * 1024)}MB or smaller.")
    if not contents:
        raise AppError(status.HTTP_400_BAD_REQUEST, "empty_file", "The uploaded file is empty.")

    relative = folder / f"{uuid.uuid4().hex}{extension}"
    target = PRIVATE_ROOT / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(contents)
    return relative.as_posix(), len(contents)


def private_path(relative: str) -> Path:
    path = (PRIVATE_ROOT / relative).resolve()
    if PRIVATE_ROOT.resolve() not in path.parents or not path.is_file():
        raise AppError(status.HTTP_404_NOT_FOUND, "file_not_found", "File not found.")
    return path


def delete_private_file(relative: str | None) -> None:
    if not relative:
        return
    try:
        (PRIVATE_ROOT / relative).unlink(missing_ok=True)
    except OSError:
        pass
