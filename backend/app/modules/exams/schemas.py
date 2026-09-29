from datetime import date
from decimal import Decimal

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

ExamType = Literal["internal", "semester"]


def _strip(value):
    return value.strip() if isinstance(value, str) else value


def _two_places(value: Decimal | None) -> Decimal | None:
    if value is not None and value.as_tuple().exponent < -2:
        raise ValueError("Use at most 2 decimal places.")
    return value


class CreateExamRequest(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    term_label: str = Field(default="", max_length=50)
    exam_type: ExamType = "semester"
    academic_year: str = Field(min_length=4, max_length=9)
    start_date: date | None = None
    end_date: date | None = None
    class_ids: list[str] = Field(min_length=1)
    # Every subject taught in the chosen classes becomes a paper with these marks;
    # adjust individual papers afterwards.
    max_marks: Decimal = Field(default=Decimal(100), gt=0, le=1000)
    pass_marks: Decimal = Field(default=Decimal(35), ge=0, le=1000)

    _strip_text = field_validator("name", "term_label", "academic_year", mode="before")(_strip)
    _money = field_validator("max_marks", "pass_marks")(_two_places)

    @model_validator(mode="after")
    def _check(self):
        if self.pass_marks > self.max_marks:
            raise ValueError("Pass marks can't be more than maximum marks.")
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("The exam can't end before it starts.")
        return self


class UpdateExamRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    term_label: str | None = Field(default=None, max_length=50)
    exam_type: ExamType | None = None
    start_date: date | None = None
    end_date: date | None = None

    _strip_text = field_validator("name", "term_label", mode="before")(_strip)


class PaperRequest(BaseModel):
    class_id: str
    subject_id: str
    max_marks: Decimal = Field(default=Decimal(100), gt=0, le=1000)
    pass_marks: Decimal = Field(default=Decimal(35), ge=0, le=1000)
    exam_date: date | None = None

    _marks = field_validator("max_marks", "pass_marks")(_two_places)


class UpdatePaperRequest(BaseModel):
    max_marks: Decimal | None = Field(default=None, gt=0, le=1000)
    pass_marks: Decimal | None = Field(default=None, ge=0, le=1000)
    exam_date: date | None = None

    _marks = field_validator("max_marks", "pass_marks")(_two_places)


class PaperOut(BaseModel):
    id: str
    exam_id: str
    exam_name: str
    class_id: str
    class_name: str
    section: str
    subject_id: str
    subject_name: str
    teacher_name: str | None
    max_marks: float
    pass_marks: float
    exam_date: date | None
    students: int
    entered: int
    published: bool
    can_enter_marks: bool


class ExamOut(BaseModel):
    id: str
    name: str
    term_label: str
    academic_year: str
    start_date: date | None
    end_date: date | None
    published: bool
    papers: list[PaperOut]
    exam_type: ExamType = "semester"


class MarkEntryIn(BaseModel):
    student_id: str
    marks: Decimal | None = Field(default=None, ge=0)
    is_absent: bool = False

    _marks = field_validator("marks")(_two_places)

    @model_validator(mode="after")
    def _check(self):
        if self.is_absent and self.marks is not None:
            raise ValueError("An absent student can't have marks.")
        return self


class SaveMarksRequest(BaseModel):
    entries: list[MarkEntryIn] = Field(min_length=1)


class MarkSheetRow(BaseModel):
    student_id: str
    full_name: str
    admission_number: str
    marks: float | None
    is_absent: bool


class MarkSheet(BaseModel):
    paper: PaperOut
    rows: list[MarkSheetRow]


class PaperResult(BaseModel):
    subject_name: str
    max_marks: float
    pass_marks: float
    marks: float | None
    is_absent: bool
    grade: str | None
    passed: bool | None
    credits: float = 0
    grade_point: int | None = None


class StudentResult(BaseModel):
    student_id: str
    full_name: str
    admission_number: str
    papers: list[PaperResult]
    total: float
    max_total: float
    percentage: float | None
    grade: str | None
    complete: bool
    passed: bool | None
    rank: int | None
    sgpa: float | None = None
    credits_total: float = 0
    credits_earned: float = 0


class SubjectStats(BaseModel):
    subject_name: str
    max_marks: float
    average: float | None
    highest: float | None
    passed: int
    appeared: int


class ClassResults(BaseModel):
    exam_id: str
    exam_name: str
    class_name: str
    section: str
    published: bool
    subjects: list[str]
    students: list[StudentResult]
    subject_stats: list[SubjectStats]


class ReportCard(BaseModel):
    school_name: str
    exam_name: str
    term_label: str
    academic_year: str
    class_name: str
    section: str
    class_teacher_name: str
    class_size: int
    result: StudentResult
    exam_type: ExamType = "semester"
    department_name: str | None = None
    program: str = ""
    semester: int | None = None
    cgpa: float | None = None


class PublishedResult(BaseModel):
    exam_id: str
    report_card: ReportCard
