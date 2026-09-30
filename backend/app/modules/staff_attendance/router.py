from datetime import date as date_type

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, require_roles
from app.modules.staff_attendance import punch, service
from app.modules.staff_attendance.schemas import (
    MarkStaffAttendanceRequest,
    MarkStaffAttendanceResponse,
    StaffAttendanceEntry,
    StaffAttendanceResponse,
)

router = APIRouter(prefix="/staff-attendance", tags=["staff-attendance"])

_admin_only = require_roles("admin")


@router.get("", response_model=StaffAttendanceResponse)
async def get_staff_attendance(
    date: date_type,
    current_user: CurrentUser = Depends(_admin_only),
) -> StaffAttendanceResponse:
    teachers = await service.list_teachers(current_user.school_id)
    status_by_teacher = await service.get_attendance_map(current_user.school_id, date.isoformat())

    entries = [
        StaffAttendanceEntry(
            teacher_id=t["id"],
            full_name=t["full_name"],
            department=t["department"],
            status=status_by_teacher.get(t["id"]),
        )
        for t in teachers
    ]
    return StaffAttendanceResponse(date=date, entries=entries)


@router.post("", response_model=MarkStaffAttendanceResponse)
async def mark_staff_attendance(
    payload: MarkStaffAttendanceRequest,
    current_user: CurrentUser = Depends(_admin_only),
) -> MarkStaffAttendanceResponse:
    marked_count = await service.mark_attendance(
        school_id=current_user.school_id,
        iso_date=payload.date.isoformat(),
        records=payload.records,
        marked_by_user_id=current_user.id,
    )
    return MarkStaffAttendanceResponse(date=payload.date, marked_count=marked_count)


# --- Punch in / out -------------------------------------------------------------

punch_router = APIRouter(prefix="/staff-punch", tags=["staff punch"])
settings_router = APIRouter(prefix="/school-settings", tags=["school settings"])

_teacher_only = require_roles("teacher")


@punch_router.get("/me", response_model=punch.MyPunches)
async def my_punches(current_user: CurrentUser = Depends(_teacher_only)) -> punch.MyPunches:
    return await punch.my_punches(current_user)


@punch_router.post("/in", response_model=punch.PunchOut)
async def punch_in(current_user: CurrentUser = Depends(_teacher_only)) -> punch.PunchOut:
    """Records the time and marks today's staff attendance present (or late)."""
    return await punch.punch_in(current_user)


@punch_router.post("/out", response_model=punch.PunchOut)
async def punch_out(current_user: CurrentUser = Depends(_teacher_only)) -> punch.PunchOut:
    return await punch.punch_out(current_user)


@punch_router.get("", response_model=list[punch.StaffPunchRow])
async def punches_for_day(date: date_type, current_user: CurrentUser = Depends(_admin_only)) -> list[punch.StaffPunchRow]:
    return await punch.punches_for_day(current_user, date)


@settings_router.get("", response_model=punch.SchoolSettingsOut)
async def get_settings(current_user: CurrentUser = Depends(require_roles("admin", "teacher"))) -> punch.SchoolSettingsOut:
    return await punch.get_settings(current_user.school_id)


@settings_router.put("", response_model=punch.SchoolSettingsOut)
async def save_settings(payload: punch.SchoolSettingsIn, current_user: CurrentUser = Depends(_admin_only)) -> punch.SchoolSettingsOut:
    return await punch.save_settings(current_user.school_id, payload)
