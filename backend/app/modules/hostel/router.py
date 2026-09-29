from fastapi import APIRouter, Depends, Response, status

from app.api.deps import CurrentUser, require_roles
from app.modules.hostel import service
from app.modules.hostel.service import AllocateIn, HostelIn, HostelOut, RoomIn, StayOut
from app.modules.parents import service as parents

router = APIRouter(prefix="/hostels", tags=["hostel"])
portal_router = APIRouter(prefix="/me/parent/children", tags=["parent portal"])

_admin_only = require_roles("admin")


def _done() -> Response:
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("", response_model=list[HostelOut])
async def list_hostels(current_user: CurrentUser = Depends(require_roles("admin", "teacher"))) -> list[HostelOut]:
    return await service.list_hostels(current_user.school_id)


@router.post("", status_code=status.HTTP_204_NO_CONTENT)
async def create_hostel(payload: HostelIn, current_user: CurrentUser = Depends(_admin_only)) -> Response:
    await service.create_hostel(current_user.school_id, payload)
    return _done()


@router.put("/{hostel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_hostel(hostel_id: str, payload: HostelIn, current_user: CurrentUser = Depends(_admin_only)) -> Response:
    await service.update_hostel(current_user.school_id, hostel_id, payload)
    return _done()


@router.delete("/{hostel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_hostel(hostel_id: str, current_user: CurrentUser = Depends(_admin_only)) -> Response:
    await service.delete_hostel(current_user.school_id, hostel_id)
    return _done()


@router.post("/{hostel_id}/rooms", status_code=status.HTTP_204_NO_CONTENT)
async def add_room(hostel_id: str, payload: RoomIn, current_user: CurrentUser = Depends(_admin_only)) -> Response:
    await service.add_room(current_user.school_id, hostel_id, payload)
    return _done()


@router.put("/rooms/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_room(room_id: str, payload: RoomIn, current_user: CurrentUser = Depends(_admin_only)) -> Response:
    await service.update_room(current_user.school_id, room_id, payload)
    return _done()


@router.delete("/rooms/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_room(room_id: str, current_user: CurrentUser = Depends(_admin_only)) -> Response:
    await service.delete_room(current_user.school_id, room_id)
    return _done()


@router.post("/allocations", status_code=status.HTTP_204_NO_CONTENT)
async def allocate(payload: AllocateIn, current_user: CurrentUser = Depends(_admin_only)) -> Response:
    await service.allocate(current_user.school_id, payload)
    return _done()


@router.delete("/allocations/{allocation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def vacate(allocation_id: str, current_user: CurrentUser = Depends(_admin_only)) -> Response:
    await service.vacate(current_user.school_id, allocation_id)
    return _done()


@portal_router.get("/{student_id}/hostel", response_model=StayOut | None)
async def child_stay(student_id: str, current_user: CurrentUser = Depends(require_roles("parent", "student"))) -> StayOut | None:
    child = await parents.child_row(current_user, student_id)
    return await service.student_stay(child["id"])
