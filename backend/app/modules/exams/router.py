from fastapi import APIRouter, Depends, Response, status

from app.api.deps import CurrentUser, require_roles
from app.modules.exams import service
from app.modules.exams.schemas import (
    BacklogOut,
    ClassResults,
    CreateExamRequest,
    ExamOut,
    MarkSheet,
    PaperOut,
    PaperRequest,
    PublishedResult,
    ReportCard,
    SaveMarksRequest,
    StudentBacklogs,
    UpdateExamRequest,
    UpdatePaperRequest,
)
from app.modules.parents import service as parents

router = APIRouter(prefix="/exams", tags=["exams"])
papers_router = APIRouter(prefix="/exam-papers", tags=["exams"])
parent_results_router = APIRouter(prefix="/me/parent/children", tags=["parent portal"])

_admin_only = require_roles("admin")
_staff = require_roles("admin", "teacher")


# --- Exams (admin) ------------------------------------------------------------


@router.get("", response_model=list[ExamOut])
async def list_exams(current_user: CurrentUser = Depends(_staff)) -> list[ExamOut]:
    return await service.list_exams(current_user)


@router.post("", response_model=ExamOut, status_code=status.HTTP_201_CREATED)
async def create_exam(payload: CreateExamRequest, current_user: CurrentUser = Depends(_admin_only)) -> ExamOut:
    """Creates the exam with a paper for every subject taught in each chosen class."""
    return await service.create_exam(current_user, payload)


@router.get("/backlogs", response_model=list[StudentBacklogs])
async def class_backlogs(class_id: str, current_user: CurrentUser = Depends(_staff)) -> list[StudentBacklogs]:
    """Students of the batch with uncleared backlogs (failed or absent in their latest attempt)."""
    return await service.class_backlogs(current_user, class_id)


@router.get("/{exam_id}", response_model=ExamOut)
async def get_exam(exam_id: str, current_user: CurrentUser = Depends(_staff)) -> ExamOut:
    return await service.get_exam(current_user, exam_id)


@router.patch("/{exam_id}", response_model=ExamOut)
async def update_exam(exam_id: str, payload: UpdateExamRequest, current_user: CurrentUser = Depends(_admin_only)) -> ExamOut:
    return await service.update_exam(current_user, exam_id, payload)


@router.delete("/{exam_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_exam(exam_id: str, current_user: CurrentUser = Depends(_admin_only)) -> Response:
    await service.delete_exam(current_user, exam_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{exam_id}/publish", response_model=ExamOut)
async def publish(exam_id: str, current_user: CurrentUser = Depends(_admin_only)) -> ExamOut:
    """Shows results to students and parents, and locks marks."""
    return await service.set_published(current_user, exam_id, True)


@router.post("/{exam_id}/unpublish", response_model=ExamOut)
async def unpublish(exam_id: str, current_user: CurrentUser = Depends(_admin_only)) -> ExamOut:
    return await service.set_published(current_user, exam_id, False)


@router.post("/{exam_id}/papers", response_model=ExamOut, status_code=status.HTTP_201_CREATED)
async def add_paper(exam_id: str, payload: PaperRequest, current_user: CurrentUser = Depends(_admin_only)) -> ExamOut:
    return await service.add_paper(current_user, exam_id, payload)


@router.get("/{exam_id}/classes/{class_id}/results", response_model=ClassResults)
async def class_results(exam_id: str, class_id: str, current_user: CurrentUser = Depends(_staff)) -> ClassResults:
    return await service.class_results(current_user, exam_id, class_id)


@router.get("/{exam_id}/students/{student_id}/report-card", response_model=ReportCard)
async def report_card(exam_id: str, student_id: str, current_user: CurrentUser = Depends(_staff)) -> ReportCard:
    return await service.report_card(current_user, exam_id, student_id)


# --- Papers and marks ---------------------------------------------------------


@papers_router.get("/mine", response_model=list[PaperOut])
async def my_papers(current_user: CurrentUser = Depends(_staff)) -> list[PaperOut]:
    """Papers in unpublished exams the user can enter marks for."""
    return await service.my_papers(current_user)


@papers_router.patch("/{paper_id}", response_model=PaperOut)
async def update_paper(paper_id: str, payload: UpdatePaperRequest, current_user: CurrentUser = Depends(_admin_only)) -> PaperOut:
    return await service.update_paper(current_user, paper_id, payload)


@papers_router.delete("/{paper_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_paper(paper_id: str, current_user: CurrentUser = Depends(_admin_only)) -> Response:
    await service.delete_paper(current_user, paper_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@papers_router.get("/{paper_id}/marks", response_model=MarkSheet)
async def mark_sheet(paper_id: str, current_user: CurrentUser = Depends(_staff)) -> MarkSheet:
    return await service.mark_sheet(current_user, paper_id)


@papers_router.put("/{paper_id}/marks", response_model=MarkSheet)
async def save_marks(paper_id: str, payload: SaveMarksRequest, current_user: CurrentUser = Depends(_staff)) -> MarkSheet:
    """Saves marks (or absent) for the listed students; an empty entry clears it. Absence alerts the parent once."""
    return await service.save_marks(current_user, paper_id, payload)


# --- Published results for parents ---------------------------------------------


@parent_results_router.get("/{student_id}/backlogs", response_model=list[BacklogOut])
async def child_backlogs(student_id: str, current_user: CurrentUser = Depends(require_roles("parent", "student"))) -> list[BacklogOut]:
    child = await parents.child_row(current_user, student_id)
    return await service.backlogs(child["id"])


@parent_results_router.get("/{student_id}/results", response_model=list[PublishedResult])
async def child_results(student_id: str, current_user: CurrentUser = Depends(require_roles("parent", "student"))) -> list[PublishedResult]:
    child = await parents.child_row(current_user, student_id)
    return await service.published_results(child["id"])
