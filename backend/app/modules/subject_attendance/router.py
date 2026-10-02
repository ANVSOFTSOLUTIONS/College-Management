from datetime import date

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, require_roles
from app.modules.parents import service as parents
from app.modules.subject_attendance import service
from app.modules.subject_attendance.service import SaveSheetIn, Sheet, StudentSummary, SubjectPercent, TeachingSubject

router = APIRouter(prefix="/subject-attendance", tags=["subject attendance"])
portal_router = APIRouter(prefix="/me/parent/children", tags=["parent portal"])

_staff = require_roles("admin", "teacher")


@router.get("/my-subjects", response_model=list[TeachingSubject])
async def my_subjects(current_user: CurrentUser = Depends(_staff)) -> list[TeachingSubject]:
    """Batch + subject pairs the user can mark (all of them for an admin)."""
    return await service.my_subjects(current_user)


@router.get("/sheet", response_model=Sheet)
async def sheet(class_id: str, subject_id: str, day: date, period: int = 1, current_user: CurrentUser = Depends(_staff)) -> Sheet:
    return await service.sheet(current_user, class_id, subject_id, day, period)


@router.post("", response_model=Sheet)
async def save(payload: SaveSheetIn, current_user: CurrentUser = Depends(_staff)) -> Sheet:
    return await service.save(current_user, payload)


@router.get("/summary", response_model=list[StudentSummary])
async def summary(class_id: str, current_user: CurrentUser = Depends(_staff)) -> list[StudentSummary]:
    """Each student's attendance percentage per subject; `short` marks below 75%."""
    return await service.class_summary(current_user, class_id)


@portal_router.get("/{student_id}/subject-attendance", response_model=list[SubjectPercent])
async def child_subject_attendance(student_id: str, current_user: CurrentUser = Depends(require_roles("parent", "student"))) -> list[SubjectPercent]:
    child = await parents.child_row(current_user, student_id)
    return await service.student_percentages(child["id"])
