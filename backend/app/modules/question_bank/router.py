from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import FileResponse

from app.api.deps import CurrentUser, require_roles
from app.modules.parents import service as parents
from app.modules.question_bank import service
from app.modules.question_bank.service import FileLink, PaperOut

router = APIRouter(prefix="/question-papers", tags=["question bank"])
portal_router = APIRouter(prefix="/me/parent/children", tags=["parent portal"])

_staff = require_roles("admin", "teacher")
_family = require_roles("parent", "student")


@router.get("", response_model=list[PaperOut])
async def list_papers(subject_id: str | None = None, current_user: CurrentUser = Depends(_staff)) -> list[PaperOut]:
    return await service.list_papers(current_user, subject_id)


@router.post("", response_model=PaperOut, status_code=status.HTTP_201_CREATED)
async def upload(
    subject_id: str = Form(...), title: str = Form(...), exam_year: str = Form(""), regulation: str = Form(""), file: UploadFile = File(...),
    current_user: CurrentUser = Depends(_staff),
) -> PaperOut:
    """A PDF or image of a previous / model question paper."""
    return await service.upload(current_user, subject_id, title, exam_year, regulation, file)


@router.get("/download/{paper_id}", response_class=FileResponse)
async def signed_download(paper_id: str, expires: int, sig: str) -> FileResponse:
    """No login: the signed, five-minute link the app opens in the phone's browser."""
    return await service.signed_file(paper_id, expires, sig)


@router.get("/{paper_id}/file", response_class=FileResponse)
async def paper_file(paper_id: str, current_user: CurrentUser = Depends(_staff)) -> FileResponse:
    return await service.file(current_user, paper_id)


@router.delete("/{paper_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(paper_id: str, current_user: CurrentUser = Depends(_staff)) -> None:
    await service.delete(current_user, paper_id)


@portal_router.get("/{student_id}/question-papers", response_model=list[PaperOut])
async def child_papers(student_id: str, current_user: CurrentUser = Depends(_family)) -> list[PaperOut]:
    return await service.for_student(await parents.child_row(current_user, student_id))


@portal_router.get("/{student_id}/question-papers/{paper_id}/file", response_class=FileResponse)
async def child_paper_file(student_id: str, paper_id: str, current_user: CurrentUser = Depends(_family)) -> FileResponse:
    return await service.student_file(await parents.child_row(current_user, student_id), paper_id)


@portal_router.post("/{student_id}/question-papers/{paper_id}/link", response_model=FileLink)
async def child_paper_link(student_id: str, paper_id: str, current_user: CurrentUser = Depends(_family)) -> FileLink:
    return await service.student_link(await parents.child_row(current_user, student_id), paper_id)
