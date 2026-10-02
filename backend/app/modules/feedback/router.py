from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUser, require_roles
from app.modules.feedback import service
from app.modules.feedback.service import FeedbackReport, OpenIn, ResponseIn, RoundIn, RoundOut, StudentRound
from app.modules.parents import service as parents

router = APIRouter(prefix="/feedback", tags=["faculty feedback"])
portal_router = APIRouter(prefix="/me/parent/children", tags=["parent portal"])

_admin = require_roles("admin")


@router.get("/rounds", response_model=list[RoundOut])
async def list_rounds(current_user: CurrentUser = Depends(require_roles("admin", "teacher"))) -> list[RoundOut]:
    return await service.list_rounds(current_user)


@router.post("/rounds", response_model=RoundOut, status_code=status.HTTP_201_CREATED)
async def create_round(payload: RoundIn, current_user: CurrentUser = Depends(_admin)) -> RoundOut:
    return await service.create_round(current_user, payload)


@router.put("/rounds/{round_id}/open", response_model=RoundOut)
async def set_open(round_id: str, payload: OpenIn, current_user: CurrentUser = Depends(_admin)) -> RoundOut:
    return await service.set_open(current_user, round_id, payload.is_open)


@router.delete("/rounds/{round_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_round(round_id: str, current_user: CurrentUser = Depends(_admin)) -> None:
    await service.delete_round(current_user, round_id)


@router.get("/rounds/{round_id}/report", response_model=FeedbackReport)
async def report(round_id: str, current_user: CurrentUser = Depends(require_roles("admin", "teacher"))) -> FeedbackReport:
    """Averages per faculty and subject: all faculty for the admin, the department's for a HOD."""
    return await service.report(current_user, round_id)


@router.get("/mine", response_model=list[FeedbackReport])
async def mine(current_user: CurrentUser = Depends(require_roles("teacher"))) -> list[FeedbackReport]:
    return await service.mine(current_user)


@portal_router.get("/{student_id}/feedback", response_model=list[StudentRound])
async def student_rounds(student_id: str, current_user: CurrentUser = Depends(require_roles("student"))) -> list[StudentRound]:
    return await service.student_rounds(await parents.child_row(current_user, student_id))


@portal_router.post("/{student_id}/feedback/{round_id}", response_model=list[StudentRound])
async def submit(student_id: str, round_id: str, payload: ResponseIn, current_user: CurrentUser = Depends(require_roles("student"))) -> list[StudentRound]:
    return await service.submit(await parents.child_row(current_user, student_id), round_id, payload)
