import uuid
from pathlib import Path

from fastapi import UploadFile, status

from app.core.errors import AppError

UPLOAD_ROOT = Path(__file__).resolve().parents[3] / "uploads"

_EXTENSION_BY_CONTENT_TYPE = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024


async def save_image_upload(school_id: str, file: UploadFile) -> str:
    extension = _EXTENSION_BY_CONTENT_TYPE.get(file.content_type)
    if extension is None:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            "invalid_file_type",
            "Only JPEG, PNG, WEBP, or GIF images are allowed.",
        )

    contents = await file.read()
    if len(contents) > MAX_UPLOAD_BYTES:
        raise AppError(status.HTTP_400_BAD_REQUEST, "file_too_large", "Images must be 5MB or smaller.")
    if len(contents) == 0:
        raise AppError(status.HTTP_400_BAD_REQUEST, "empty_file", "The uploaded file is empty.")

    school_dir = UPLOAD_ROOT / school_id
    school_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{extension}"
    (school_dir / filename).write_bytes(contents)

    return f"/uploads/{school_id}/{filename}"


def delete_uploaded_file(url: str) -> None:
    if not url or not url.startswith("/uploads/"):
        return
    file_path = UPLOAD_ROOT / Path(url).relative_to("/uploads")
    try:
        file_path.unlink(missing_ok=True)
    except OSError:
        pass
