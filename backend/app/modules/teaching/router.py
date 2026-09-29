from fastapi import APIRouter, Depends, Response, status

from app.api.deps import CurrentUser, require_roles
from app.modules.teaching import service
from app.modules.teaching.service import CreateRemarkRequest, RemarkOut, RosterStudent, TeachingClass

teaching_router = APIRouter(prefix="/teaching", tags=["teaching"])
remarks_router = APIRouter(prefix="/remarks", tags=["remarks"])

_staff = require_roles("admin", "teacher")


@teaching_router.get("/classes", response_model=list[TeachingClass])
async def my_classes(current_user: CurrentUser = Depends(_staff)) -> list[TeachingClass]:
    """Classes the user teaches (class teacher or subject teacher); every class for an admin."""
    return await service.teaching_classes(current_user)


@teaching_router.get("/classes/{class_id}/students", response_model=list[RosterStudent])
async def class_roster(class_id: str, current_user: CurrentUser = Depends(_staff)) -> list[RosterStudent]:
    return await service.class_roster(current_user, class_id)


@remarks_router.get("", response_model=list[RemarkOut])
async def list_remarks(
    class_id: str | None = None, student_id: str | None = None, current_user: CurrentUser = Depends(_staff)
) -> list[RemarkOut]:
    return await service.list_remarks(current_user, class_id=class_id, student_id=student_id)


@remarks_router.post("", response_model=RemarkOut, status_code=status.HTTP_201_CREATED)
async def create_remark(payload: CreateRemarkRequest, current_user: CurrentUser = Depends(_staff)) -> RemarkOut:
    return await service.create_remark(current_user, payload)


@remarks_router.delete("/{remark_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_remark(remark_id: str, current_user: CurrentUser = Depends(_staff)) -> Response:
    await service.delete_remark(current_user, remark_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
