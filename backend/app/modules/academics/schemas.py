from datetime import date as date_type
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

TeacherStatus = Literal["active", "inactive"]


def _strip(value: str | None) -> str | None:
    return value.strip() if isinstance(value, str) else value


# --- Teachers -----------------------------------------------------------------


class CreateTeacherRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=8, max_length=72)
    phone: str = Field(default="", max_length=20)
    department: str = Field(default="General", min_length=1, max_length=100)
    designation: str = Field(default="", max_length=60)
    department_id: str | None = None
    qualification: str = Field(default="", max_length=200)
    employee_code: str | None = Field(default=None, max_length=30)
    joined_on: date_type | None = None

    _strip_text = field_validator("full_name", "phone", "department", "designation", "qualification", "employee_code")(_strip)


class UpdateTeacherRequest(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    password: str | None = Field(default=None, min_length=8, max_length=72)
    phone: str | None = Field(default=None, max_length=20)
    department: str | None = Field(default=None, min_length=1, max_length=100)
    designation: str | None = Field(default=None, max_length=60)
    department_id: str | None = None
    qualification: str | None = Field(default=None, max_length=200)
    employee_code: str | None = Field(default=None, max_length=30)
    joined_on: date_type | None = None
    status: TeacherStatus | None = None

    _strip_text = field_validator("full_name", "phone", "department", "designation", "qualification", "employee_code")(_strip)


class ClassRef(BaseModel):
    id: str
    name: str
    section: str


class TeacherSubjectRef(BaseModel):
    class_id: str
    class_name: str
    section: str
    subject_id: str
    subject_name: str


class TeacherOut(BaseModel):
    id: str
    email: str
    full_name: str
    phone: str
    department: str
    designation: str = ""
    department_id: str | None = None
    qualification: str
    employee_code: str | None
    joined_on: date_type | None
    status: TeacherStatus
    class_teacher_of: list[ClassRef]
    subjects: list[TeacherSubjectRef]


# --- Subjects -----------------------------------------------------------------


SubjectType = Literal["theory", "lab", "project", "elective"]


class SubjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    code: str = Field(default="", max_length=20)
    credits: float = Field(default=3.0, ge=0, le=20)
    subject_type: SubjectType = "theory"
    department_id: str | None = None
    semester: int | None = Field(default=None, ge=1, le=12)

    _strip_text = field_validator("name", "code")(_strip)


class SubjectOut(BaseModel):
    id: str
    name: str
    code: str
    credits: float = 3.0
    subject_type: SubjectType = "theory"
    department_id: str | None = None
    semester: int | None = None


# --- Classes ------------------------------------------------------------------


class CreateClassRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    section: str = Field(min_length=1, max_length=20)
    academic_year: str = Field(min_length=4, max_length=9)
    class_teacher_id: str
    department_id: str | None = None
    program: str = Field(default="", max_length=60)
    semester: int | None = Field(default=None, ge=1, le=12)
    regulation: str = Field(default="", max_length=20)

    _strip_text = field_validator("name", "section", "academic_year", "program", "regulation")(_strip)


class UpdateClassRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    section: str | None = Field(default=None, min_length=1, max_length=20)
    academic_year: str | None = Field(default=None, min_length=4, max_length=9)
    class_teacher_id: str | None = None
    department_id: str | None = None
    program: str | None = Field(default=None, max_length=60)
    semester: int | None = Field(default=None, ge=1, le=12)
    regulation: str | None = Field(default=None, max_length=20)

    _strip_text = field_validator("name", "section", "academic_year", "program", "regulation")(_strip)


class AssignSubjectTeacherRequest(BaseModel):
    teacher_id: str


class TeacherRef(BaseModel):
    id: str
    full_name: str


class ClassSubjectOut(BaseModel):
    subject_id: str
    subject_name: str
    teacher: TeacherRef
    credits: float = 3.0


class ClassDetail(BaseModel):
    id: str
    name: str
    section: str
    academic_year: str
    class_teacher: TeacherRef
    student_count: int
    subjects: list[ClassSubjectOut]
    department_id: str | None = None
    department_name: str | None = None
    program: str = ""
    semester: int | None = None
    regulation: str = ""


# --- Departments --------------------------------------------------------------


class DepartmentRequest(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    code: str = Field(min_length=1, max_length=20)
    hod_teacher_id: str | None = None

    _strip_text = field_validator("name", "code")(_strip)


class DepartmentOut(BaseModel):
    id: str
    name: str
    code: str
    hod: TeacherRef | None
    faculty_count: int
    class_count: int
    student_count: int
