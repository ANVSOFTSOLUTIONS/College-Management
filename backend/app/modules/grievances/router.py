from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUser, require_roles
from app.modules.grievances import service
from app.modules.grievances.service import GrievanceIn, GrievanceOut, GrievanceSummary, ReplyIn, StatusIn

router = APIRouter(prefix="/grievances", tags=["grievances"])

_raisers = require_roles("student", "parent", "teacher")
_anyone = require_roles("admin", "student", "parent", "teacher")
_admin = require_roles("admin")


@router.post("", response_model=GrievanceOut, status_code=status.HTTP_201_CREATED)
async def create(payload: GrievanceIn, current_user: CurrentUser = Depends(_raisers)) -> GrievanceOut:
    return await service.create(current_user, payload)


@router.get("/mine", response_model=list[GrievanceOut])
async def mine(current_user: CurrentUser = Depends(_raisers)) -> list[GrievanceOut]:
    return await service.mine(current_user)


@router.get("/summary", response_model=GrievanceSummary)
async def summary(current_user: CurrentUser = Depends(_admin)) -> GrievanceSummary:
    return await service.summary(current_user)


@router.get("", response_model=list[GrievanceOut])
async def list_all(status: str | None = None, category: str | None = None, current_user: CurrentUser = Depends(_admin)) -> list[GrievanceOut]:
    return await service.list_all(current_user, status, category)


@router.get("/{grievance_id}", response_model=GrievanceOut)
async def get(grievance_id: str, current_user: CurrentUser = Depends(_anyone)) -> GrievanceOut:
    return await service.get(current_user, grievance_id)


@router.post("/{grievance_id}/replies", response_model=GrievanceOut)
async def reply(grievance_id: str, payload: ReplyIn, current_user: CurrentUser = Depends(_anyone)) -> GrievanceOut:
    return await service.reply(current_user, grievance_id, payload)


@router.put("/{grievance_id}/status", response_model=GrievanceOut)
async def set_status(grievance_id: str, payload: StatusIn, current_user: CurrentUser = Depends(_admin)) -> GrievanceOut:
    return await service.set_status(current_user, grievance_id, payload)
