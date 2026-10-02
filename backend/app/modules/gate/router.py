from datetime import date

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUser, require_roles
from app.modules.gate import service
from app.modules.gate.service import DecisionIn, PassIn, PassOut, VisitorIn, VisitorOut
from app.modules.parents import service as parents

router = APIRouter(prefix="/gate", tags=["gate"])
portal_router = APIRouter(prefix="/me/parent/children", tags=["parent portal"])

_admin = require_roles("admin")
_family = require_roles("parent", "student")


@router.get("/passes", response_model=list[PassOut])
async def list_passes(status: str | None = "active", day: date | None = None, current_user: CurrentUser = Depends(_admin)) -> list[PassOut]:
    """`status=active` (default) lists pending, approved and out passes."""
    return await service.list_passes(current_user, status, day)


@router.post("/passes/{pass_id}/decide", response_model=PassOut)
async def decide(pass_id: str, payload: DecisionIn, current_user: CurrentUser = Depends(_admin)) -> PassOut:
    return await service.decide(current_user, pass_id, payload)


@router.post("/passes/{pass_id}/out", response_model=PassOut)
async def mark_out(pass_id: str, current_user: CurrentUser = Depends(_admin)) -> PassOut:
    return await service.mark_out(current_user, pass_id)


@router.post("/passes/{pass_id}/returned", response_model=PassOut)
async def mark_returned(pass_id: str, current_user: CurrentUser = Depends(_admin)) -> PassOut:
    return await service.mark_returned(current_user, pass_id)


@router.get("/visitors", response_model=list[VisitorOut])
async def list_visitors(day: date | None = None, inside_only: bool = False, current_user: CurrentUser = Depends(_admin)) -> list[VisitorOut]:
    return await service.list_visitors(current_user, day, inside_only)


@router.post("/visitors", response_model=VisitorOut, status_code=status.HTTP_201_CREATED)
async def add_visitor(payload: VisitorIn, current_user: CurrentUser = Depends(_admin)) -> VisitorOut:
    return await service.add_visitor(current_user, payload)


@router.post("/visitors/{visitor_id}/out", response_model=VisitorOut)
async def visitor_out(visitor_id: str, current_user: CurrentUser = Depends(_admin)) -> VisitorOut:
    return await service.visitor_out(current_user, visitor_id)


@portal_router.get("/{student_id}/gate-passes", response_model=list[PassOut])
async def child_passes(student_id: str, current_user: CurrentUser = Depends(_family)) -> list[PassOut]:
    child = await parents.child_row(current_user, student_id)
    return await service.for_student(child["id"])


@portal_router.post("/{student_id}/gate-passes", response_model=list[PassOut], status_code=status.HTTP_201_CREATED)
async def request_pass(student_id: str, payload: PassIn, current_user: CurrentUser = Depends(_family)) -> list[PassOut]:
    return await service.request(current_user, await parents.child_row(current_user, student_id), payload)


@portal_router.post("/{student_id}/gate-passes/{pass_id}/cancel", response_model=list[PassOut])
async def cancel_pass(student_id: str, pass_id: str, current_user: CurrentUser = Depends(_family)) -> list[PassOut]:
    return await service.cancel(current_user, await parents.child_row(current_user, student_id), pass_id)
