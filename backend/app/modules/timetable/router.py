from datetime import date

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import CurrentUser, require_roles
from app.modules.timetable import calendar, service
from app.modules.timetable.calendar import HolidayIn, HolidayOut
from app.modules.timetable.service import ClassGridIn, PeriodOut, PeriodsIn, TimetableOut

timetable_router = APIRouter(prefix="/timetable", tags=["timetable"])
calendar_router = APIRouter(prefix="/calendar", tags=["calendar"])

_everyone = require_roles("admin", "teacher", "parent", "student")
_staff = require_roles("admin", "teacher")
_admin = require_roles("admin")


# --- Timetable -------------------------------------------------------------------


@timetable_router.get("/periods", response_model=list[PeriodOut])
async def list_periods(current_user: CurrentUser = Depends(_staff)) -> list[PeriodOut]:
    return await service.list_periods(current_user.school_id)


@timetable_router.put("/periods", response_model=list[PeriodOut])
async def save_periods(payload: PeriodsIn, current_user: CurrentUser = Depends(_admin)) -> list[PeriodOut]:
    """Replaces the bell schedule. Send existing ids to keep their timetable cells; periods left out are removed."""
    return await service.save_periods(current_user, payload)


@timetable_router.get("/mine", response_model=TimetableOut)
async def my_timetable(student_id: str | None = None, current_user: CurrentUser = Depends(_everyone)) -> TimetableOut:
    """A teacher's week, a student's class, or (with `student_id`) a parent's child's class."""
    return await service.my_timetable(current_user, student_id)


@timetable_router.get("/classes/{class_id}", response_model=TimetableOut)
async def class_timetable(class_id: str, current_user: CurrentUser = Depends(_staff)) -> TimetableOut:
    return await service.class_timetable(current_user, class_id)


@timetable_router.put("/classes/{class_id}", response_model=TimetableOut)
async def save_class_timetable(class_id: str, payload: ClassGridIn, current_user: CurrentUser = Depends(_admin)) -> TimetableOut:
    """Replaces the class's weekly grid. Refused (409) if a teacher would be in two classes at once."""
    return await service.save_class_timetable(current_user, class_id, payload)


# --- Calendar --------------------------------------------------------------------


@calendar_router.get("", response_model=list[HolidayOut])
async def list_holidays(start: date, end: date, current_user: CurrentUser = Depends(_everyone)) -> list[HolidayOut]:
    """Holidays and events overlapping start..end (at most ~13 months)."""
    return await calendar.list_holidays(current_user, start, end)


@calendar_router.post("", response_model=HolidayOut, status_code=status.HTTP_201_CREATED)
async def create_holiday(payload: HolidayIn, current_user: CurrentUser = Depends(_admin)) -> HolidayOut:
    return await calendar.create_holiday(current_user, payload)


@calendar_router.put("/{holiday_id}", response_model=HolidayOut)
async def update_holiday(holiday_id: str, payload: HolidayIn, current_user: CurrentUser = Depends(_admin)) -> HolidayOut:
    return await calendar.update_holiday(current_user, holiday_id, payload)


@calendar_router.delete("/{holiday_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_holiday(holiday_id: str, current_user: CurrentUser = Depends(_admin)) -> Response:
    await calendar.delete_holiday(current_user, holiday_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
