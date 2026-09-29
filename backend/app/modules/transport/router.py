from fastapi import APIRouter, Depends, Response, status

from app.api.deps import CurrentUser, require_roles
from app.modules.parents import service as parents
from app.modules.transport import service
from app.modules.transport.service import AssignIn, RideOut, RouteIn, RouteOut

router = APIRouter(prefix="/transport", tags=["transport"])
portal_router = APIRouter(prefix="/me/parent/children", tags=["parent portal"])

_admin_only = require_roles("admin")


def _done() -> Response:
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/routes", response_model=list[RouteOut])
async def list_routes(current_user: CurrentUser = Depends(require_roles("admin", "teacher"))) -> list[RouteOut]:
    return await service.list_routes(current_user.school_id)


@router.post("/routes", status_code=status.HTTP_204_NO_CONTENT)
async def create_route(payload: RouteIn, current_user: CurrentUser = Depends(_admin_only)) -> Response:
    await service.create_route(current_user.school_id, payload)
    return _done()


@router.put("/routes/{route_id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_route(route_id: str, payload: RouteIn, current_user: CurrentUser = Depends(_admin_only)) -> Response:
    await service.update_route(current_user.school_id, route_id, payload)
    return _done()


@router.delete("/routes/{route_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_route(route_id: str, current_user: CurrentUser = Depends(_admin_only)) -> Response:
    await service.delete_route(current_user.school_id, route_id)
    return _done()


@router.post("/assignments", status_code=status.HTTP_204_NO_CONTENT)
async def assign(payload: AssignIn, current_user: CurrentUser = Depends(_admin_only)) -> Response:
    await service.assign(current_user.school_id, payload)
    return _done()


@router.delete("/assignments/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unassign(student_id: str, current_user: CurrentUser = Depends(_admin_only)) -> Response:
    await service.unassign(current_user.school_id, student_id)
    return _done()


@portal_router.get("/{student_id}/transport", response_model=RideOut | None)
async def child_ride(student_id: str, current_user: CurrentUser = Depends(require_roles("parent", "student"))) -> RideOut | None:
    child = await parents.child_row(current_user, student_id)
    return await service.student_ride(child["id"])
