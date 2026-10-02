from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from app.api.deps import CurrentUser, require_roles
from app.modules.electives import service
from app.modules.electives.service import ChooseIn, GroupIn, GroupOut, OpenIn
from app.modules.parents import service as parents

router = APIRouter(prefix="/electives", tags=["electives"])
portal_router = APIRouter(prefix="/me/parent/children", tags=["parent portal"])

_admin = require_roles("admin")


class AssignIn(BaseModel):
    student_id: str
    option_id: str | None = None


@router.get("", response_model=list[GroupOut])
async def list_groups(class_id: str, current_user: CurrentUser = Depends(_admin)) -> list[GroupOut]:
    return await service.list_groups(current_user, class_id)


@router.post("", response_model=GroupOut, status_code=status.HTTP_201_CREATED)
async def create_group(payload: GroupIn, current_user: CurrentUser = Depends(_admin)) -> GroupOut:
    return await service.create_group(current_user, payload)


@router.put("/{group_id}/open", response_model=GroupOut)
async def set_open(group_id: str, payload: OpenIn, current_user: CurrentUser = Depends(_admin)) -> GroupOut:
    return await service.set_open(current_user, group_id, payload.is_open)


@router.put("/{group_id}/assign", response_model=GroupOut)
async def assign(group_id: str, payload: AssignIn, current_user: CurrentUser = Depends(_admin)) -> GroupOut:
    return await service.assign(current_user, group_id, payload.student_id, payload.option_id)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(group_id: str, current_user: CurrentUser = Depends(_admin)) -> None:
    await service.delete_group(current_user, group_id)


@portal_router.get("/{student_id}/electives", response_model=list[GroupOut])
async def child_electives(student_id: str, current_user: CurrentUser = Depends(require_roles("parent", "student"))) -> list[GroupOut]:
    return await service.student_groups(await parents.child_row(current_user, student_id))


@portal_router.post("/{student_id}/electives/{group_id}", response_model=list[GroupOut])
async def choose_elective(student_id: str, group_id: str, payload: ChooseIn, current_user: CurrentUser = Depends(require_roles("student"))) -> list[GroupOut]:
    """Only the student picks; parents see the choice."""
    return await service.choose(await parents.child_row(current_user, student_id), group_id, payload.option_id)
