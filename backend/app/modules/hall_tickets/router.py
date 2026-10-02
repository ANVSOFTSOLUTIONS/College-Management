from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, require_roles
from app.modules.hall_tickets import service
from app.modules.hall_tickets.service import HallTicketSheet, OverrideIn, RoomIn, SettingsIn, StudentHallTicket
from app.modules.parents import service as parents

router = APIRouter(prefix="/exams", tags=["hall tickets"])
portal_router = APIRouter(prefix="/me/parent/children", tags=["parent portal"])

_admin = require_roles("admin")


@router.get("/{exam_id}/hall-tickets", response_model=HallTicketSheet)
async def sheet(exam_id: str, current_user: CurrentUser = Depends(_admin)) -> HallTicketSheet:
    """Who gets a hall ticket (attendance rule and overrides), and each student's room and seat."""
    return await service.sheet(current_user, exam_id)


@router.put("/{exam_id}/hall-tickets/settings", response_model=HallTicketSheet)
async def save_settings(exam_id: str, payload: SettingsIn, current_user: CurrentUser = Depends(_admin)) -> HallTicketSheet:
    return await service.save_settings(current_user, exam_id, payload)


@router.put("/{exam_id}/hall-tickets/rooms", response_model=HallTicketSheet)
async def save_rooms(exam_id: str, payload: list[RoomIn], current_user: CurrentUser = Depends(_admin)) -> HallTicketSheet:
    return await service.save_rooms(current_user, exam_id, payload)


@router.put("/{exam_id}/hall-tickets/override", response_model=HallTicketSheet)
async def save_override(exam_id: str, payload: OverrideIn, current_user: CurrentUser = Depends(_admin)) -> HallTicketSheet:
    return await service.save_override(current_user, exam_id, payload)


@portal_router.get("/{student_id}/hall-tickets", response_model=list[StudentHallTicket])
async def child_hall_tickets(student_id: str, current_user: CurrentUser = Depends(require_roles("parent", "student"))) -> list[StudentHallTicket]:
    return await service.student_tickets(await parents.child_row(current_user, student_id))
