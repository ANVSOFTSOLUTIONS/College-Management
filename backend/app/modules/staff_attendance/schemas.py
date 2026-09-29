from datetime import date as date_type
from typing import Literal

from pydantic import BaseModel, Field

StaffAttendanceStatus = Literal["present", "absent", "late", "leave"]


class StaffAttendanceRecordIn(BaseModel):
    teacher_id: str
    status: StaffAttendanceStatus


class MarkStaffAttendanceRequest(BaseModel):
    date: date_type
    records: list[StaffAttendanceRecordIn] = Field(min_length=1)


class StaffAttendanceEntry(BaseModel):
    teacher_id: str
    full_name: str
    department: str
    status: StaffAttendanceStatus | None = None


class StaffAttendanceResponse(BaseModel):
    date: date_type
    entries: list[StaffAttendanceEntry]


class MarkStaffAttendanceResponse(BaseModel):
    date: date_type
    marked_count: int
