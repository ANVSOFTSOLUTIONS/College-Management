from datetime import date as date_type
from typing import Literal

from pydantic import BaseModel, Field

AttendanceStatus = Literal["present", "absent", "late"]


class StudentSummary(BaseModel):
    id: str
    full_name: str
    admission_number: str


class ClassSummary(BaseModel):
    id: str
    name: str
    section: str
    academic_year: str
    class_teacher_id: str
    class_teacher_name: str
    student_count: int
    department_id: str | None = None
    department_name: str | None = None
    program: str = ""
    semester: int | None = None
    regulation: str = ""


class RosterResponse(BaseModel):
    class_id: str
    class_name: str
    section: str
    students: list[StudentSummary]


class AttendanceRecordIn(BaseModel):
    student_id: str
    status: AttendanceStatus


class MarkAttendanceRequest(BaseModel):
    date: date_type
    records: list[AttendanceRecordIn] = Field(min_length=1)


class AttendanceEntry(BaseModel):
    student_id: str
    full_name: str
    admission_number: str
    status: AttendanceStatus | None = None
    on_leave: bool = False


class AttendanceResponse(BaseModel):
    class_id: str
    date: date_type
    entries: list[AttendanceEntry]


class MarkAttendanceResponse(BaseModel):
    class_id: str
    date: date_type
    marked_count: int
