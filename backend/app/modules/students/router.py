from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from fastapi.responses import FileResponse

from app.api.deps import CurrentUser, require_roles
from app.core.errors import AppError
from app.modules.audit import service as audit
from app.modules.students import accounts, importer, service
from app.modules.students.schemas import (
    BulkLoginsRequest,
    CreateStudentRequest,
    EnableLoginRequest,
    LoginCredentials,
    ReviewDocumentRequest,
    StudentDetail,
    StudentDocumentOut,
    StudentSummary,
    UpdateStudentRequest,
)

# Staff manage students here; students and parents use the portal (parents/router.py).
router = APIRouter(prefix="/students", tags=["students"])


def _private_file(path: Path, content_type: str, filename: str | None = None) -> FileResponse:
    return FileResponse(
        path,
        media_type=content_type,
        filename=filename,
        content_disposition_type="inline",
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )


def photo_response(student: dict) -> FileResponse:
    path = accounts.photo_file(student)
    media_type = {".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}[path.suffix]
    return _private_file(path, media_type)

# Admins manage every class; a teacher manages the classes they are class teacher of.
_staff = require_roles("admin", "teacher")
_admin_only = require_roles("admin")


@router.get("", response_model=list[StudentSummary])
async def list_students(
    class_id: str | None = None,
    q: str | None = Query(default=None, max_length=100),
    include_left: bool = False,
    current_user: CurrentUser = Depends(_staff),
) -> list[StudentSummary]:
    return await service.list_students(current_user, class_id=class_id, search=q, include_left=include_left)


@router.post("", response_model=StudentDetail, status_code=status.HTTP_201_CREATED)
async def create_student(payload: CreateStudentRequest, current_user: CurrentUser = Depends(_staff)) -> StudentDetail:
    return await service.create_student(current_user, payload)


@router.get("/{student_id}", response_model=StudentDetail)
async def get_student(student_id: str, current_user: CurrentUser = Depends(_staff)) -> StudentDetail:
    return await service.get_student(current_user, student_id)


@router.patch("/{student_id}", response_model=StudentDetail)
async def update_student(
    student_id: str, payload: UpdateStudentRequest, current_user: CurrentUser = Depends(_staff)
) -> StudentDetail:
    before = await service.get_student_row(current_user, student_id)
    student = await service.update_student(current_user, student_id, payload)
    await _audit_student_change(current_user, before, student)
    return student


@router.delete("/{student_id}", response_model=StudentDetail)
async def mark_student_left(student_id: str, current_user: CurrentUser = Depends(_admin_only)) -> StudentDetail:
    """Marks the student as left; their records are kept."""
    before = await service.get_student_row(current_user, student_id)
    student = await service.update_student(current_user, student_id, UpdateStudentRequest(status="left"))
    await _audit_student_change(current_user, before, student)
    return student


async def _audit_student_change(user: CurrentUser, before: dict, student: StudentDetail) -> None:
    """Status, class and admission number changes are logged; other profile edits aren't."""
    changes = []
    if before["status"] != student.status:
        changes.append(f"status {before['status']} → {student.status}")
    if before["class_id"] != student.class_.id:
        changes.append(f"class → {student.class_.name} - {student.class_.section}")
    if before["admission_number"] != student.admission_number:
        changes.append(f"admission no. {before['admission_number']} → {student.admission_number}")
    if changes:
        await audit.record(
            user, "students.changed", f"{student.full_name} ({student.admission_number}): {', '.join(changes)}",
            entity_type="student", entity_id=student.id,
        )


# --- Bulk import (admin) -------------------------------------------------------


@router.get("/import/template")
async def import_template(current_user: CurrentUser = Depends(_admin_only)) -> Response:
    """An Excel template with the right columns and this school's classes."""
    return Response(
        content=await importer.template_bytes(current_user.school_id),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="students-import-template.xlsx"'},
    )


@router.post("/import", response_model=importer.ImportResult)
async def import_students(
    file: UploadFile = File(...),
    dry_run: bool = True,
    skip_invalid: bool = False,
    current_user: CurrentUser = Depends(_admin_only),
) -> importer.ImportResult:
    """dry_run (default) checks every row without saving; otherwise saves all valid rows in one go."""
    return await importer.run_import(current_user, file, dry_run=dry_run, skip_invalid=skip_invalid)


# --- Photo and documents (staff) ----------------------------------------------


@router.put("/{student_id}/photo", response_model=StudentDetail)
async def upload_photo(
    student_id: str, file: UploadFile = File(...), current_user: CurrentUser = Depends(_staff)
) -> StudentDetail:
    await accounts.set_photo(await service.get_student_row(current_user, student_id), file)
    return await service.get_student(current_user, student_id)


@router.get("/{student_id}/photo", response_class=FileResponse)
async def get_photo(student_id: str, current_user: CurrentUser = Depends(_staff)) -> FileResponse:
    return photo_response(await service.get_student_row(current_user, student_id))


@router.get("/{student_id}/documents", response_model=list[StudentDocumentOut])
async def list_documents(student_id: str, current_user: CurrentUser = Depends(_staff)) -> list[StudentDocumentOut]:
    return await accounts.list_documents(await service.get_student_row(current_user, student_id))


@router.post("/{student_id}/documents", response_model=StudentDocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    student_id: str,
    doc_type: str = Form(...),
    title: str = Form(""),
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(_staff),
) -> StudentDocumentOut:
    student = await service.get_student_row(current_user, student_id)
    return await accounts.add_document(student, current_user, doc_type, title, file)


@router.patch("/{student_id}/documents/{document_id}", response_model=StudentDocumentOut)
async def review_document(
    student_id: str, document_id: str, payload: ReviewDocumentRequest, current_user: CurrentUser = Depends(_staff)
) -> StudentDocumentOut:
    student = await service.get_student_row(current_user, student_id)
    return await accounts.review_document(student, current_user, document_id, payload.status, payload.note)


@router.delete("/{student_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(student_id: str, document_id: str, current_user: CurrentUser = Depends(_staff)) -> Response:
    await accounts.delete_document(await service.get_student_row(current_user, student_id), current_user, document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{student_id}/documents/{document_id}/file", response_class=FileResponse)
async def get_document_file(student_id: str, document_id: str, current_user: CurrentUser = Depends(_staff)) -> FileResponse:
    student = await service.get_student_row(current_user, student_id)
    return _private_file(*await accounts.document_file(student, document_id))


# --- Student logins ---------------------------------------------------------------


@router.post("/logins", response_model=list[LoginCredentials])
async def enable_class_logins(payload: BulkLoginsRequest, current_user: CurrentUser = Depends(_staff)) -> list[LoginCredentials]:
    """Sign-in details for every student in the batch without an active login (print and hand out)."""
    allowed = await service.managed_class_ids(current_user)
    if allowed is not None and payload.class_id not in allowed:
        raise AppError(status.HTTP_403_FORBIDDEN, "forbidden", "Only this batch's class teacher or an admin can do that.")
    credentials = await accounts.enable_class_logins(current_user.school_id, payload.class_id)
    if credentials:
        await audit.record(
            current_user, "student.logins", f"Enabled {len(credentials)} student login(s)", entity_type="class", entity_id=payload.class_id
        )
    return credentials


@router.post("/{student_id}/login", response_model=LoginCredentials)
async def enable_login(
    student_id: str, payload: EnableLoginRequest, current_user: CurrentUser = Depends(_staff)
) -> LoginCredentials:
    student = await service.get_student_row(current_user, student_id)
    credentials = await accounts.enable_login(student, payload.password)
    await audit.record(
        current_user, "student.login", f"Login enabled / reset for {student['full_name']}", entity_type="student", entity_id=student_id
    )
    return credentials


@router.delete("/{student_id}/login", status_code=status.HTTP_204_NO_CONTENT)
async def disable_login(student_id: str, current_user: CurrentUser = Depends(_staff)) -> Response:
    await accounts.disable_login(await service.get_student_row(current_user, student_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
