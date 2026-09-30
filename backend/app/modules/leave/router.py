from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUser, require_roles
from app.modules.leave import service
from app.modules.leave.service import ApplyLeaveRequest, LeaveOut, ReviewLeaveRequest

router = APIRouter(prefix="/leave", tags=["leave"])

_applicants = require_roles("teacher", "parent", "student")
_reviewers = require_roles("admin", "teacher")


@router.post("", response_model=LeaveOut, status_code=status.HTTP_201_CREATED)
async def apply(payload: ApplyLeaveRequest, current_user: CurrentUser = Depends(_applicants)) -> LeaveOut:
    """Teachers' requests go to admins; students' to their class teacher."""
    return await service.apply(current_user, payload)


@router.get("/mine", response_model=list[LeaveOut])
async def my_leaves(current_user: CurrentUser = Depends(_applicants)) -> list[LeaveOut]:
    return await service.my_leaves(current_user)


@router.get("/inbox", response_model=list[LeaveOut])
async def inbox(only_pending: bool = False, current_user: CurrentUser = Depends(_reviewers)) -> list[LeaveOut]:
    return await service.inbox(current_user, only_pending=only_pending)


@router.post("/{leave_id}/cancel", response_model=LeaveOut)
async def cancel(leave_id: str, current_user: CurrentUser = Depends(_applicants)) -> LeaveOut:
    return await service.cancel(current_user, leave_id)


@router.post("/{leave_id}/review", response_model=LeaveOut)
async def review(leave_id: str, payload: ReviewLeaveRequest, current_user: CurrentUser = Depends(_reviewers)) -> LeaveOut:
    return await service.review(current_user, leave_id, payload)
