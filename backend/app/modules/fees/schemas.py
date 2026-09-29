from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

ManualMethod = Literal["cash", "upi", "cheque", "bank_transfer", "card"]
FeeStatus = Literal["paid", "partial", "due", "overdue"]
Money = Decimal


def _strip(value):
    return value.strip() if isinstance(value, str) else value


def _two_places(value: Decimal | None) -> Decimal | None:
    if value is not None and value.as_tuple().exponent < -2:
        raise ValueError("Use at most 2 decimal places.")
    return value


FeeCategory = Literal["tuition", "transport", "hostel", "library", "exam", "books", "uniform", "admission", "other"]


class CreateFeeItemRequest(BaseModel):
    """A fee for whole classes (class_ids), or only for chosen students (student_ids), e.g. bus users."""

    name: str = Field(min_length=1, max_length=150)
    category: FeeCategory = "tuition"
    term_label: str = Field(default="", max_length=50)
    academic_year: str = Field(min_length=4, max_length=9)
    amount: Money = Field(gt=0, le=Decimal("10000000"))
    due_date: date
    class_ids: list[str] = Field(default_factory=list, max_length=200)
    student_ids: list[str] = Field(default_factory=list, max_length=5000)

    _strip_text = field_validator("name", "term_label", "academic_year", mode="before")(_strip)
    _money = field_validator("amount")(_two_places)

    @model_validator(mode="after")
    def _who(self):
        if bool(self.class_ids) == bool(self.student_ids):
            raise ValueError("Choose either classes or students.")
        return self


class AddStudentsRequest(BaseModel):
    student_ids: list[str] = Field(min_length=1, max_length=5000)


class UpdateFeeItemRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    category: FeeCategory | None = None
    term_label: str | None = Field(default=None, max_length=50)
    amount: Money | None = Field(default=None, gt=0, le=Decimal("10000000"))
    due_date: date | None = None

    _strip_text = field_validator("name", "term_label", mode="before")(_strip)
    _money = field_validator("amount")(_two_places)


class FeeItemOut(BaseModel):
    id: str
    class_id: str
    class_name: str
    section: str
    name: str
    category: str = "other"
    applies_to: str = "class"  # class: every student in it; selected: only the chosen students
    term_label: str
    academic_year: str
    amount: float
    due_date: date
    student_count: int
    collected: float
    pending: float


class DiscountRequest(BaseModel):
    discount: Money = Field(ge=0)
    note: str = Field(default="", max_length=200)

    _strip_note = field_validator("note", mode="before")(_strip)
    _money = field_validator("discount")(_two_places)


class RecordPaymentRequest(BaseModel):
    student_fee_id: str
    amount: Money = Field(gt=0)
    method: ManualMethod
    reference: str = Field(default="", max_length=100)
    paid_on: date | None = None
    notes: str = Field(default="", max_length=300)

    _strip_text = field_validator("reference", "notes", mode="before")(_strip)
    _money = field_validator("amount")(_two_places)


class CancelPaymentRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=300)

    _strip_reason = field_validator("reason", mode="before")(_strip)


class PaymentOut(BaseModel):
    id: str
    amount: float
    method: str
    reference: str
    paid_on: date
    status: str
    receipt_number: str | None
    notes: str
    cancel_reason: str
    received_by_name: str


class StudentFeeLine(BaseModel):
    id: str
    fee_item_id: str
    name: str
    category: str = "other"
    term_label: str
    academic_year: str
    due_date: date
    amount: float
    discount: float
    discount_note: str
    paid: float
    balance: float
    status: FeeStatus
    payments: list[PaymentOut]


class StudentFeeAccount(BaseModel):
    student_id: str
    full_name: str
    admission_number: str
    class_name: str
    section: str
    total: float
    paid: float
    balance: float
    overdue: float
    lines: list[StudentFeeLine]


class StudentFeeSummary(BaseModel):
    student_id: str
    full_name: str
    admission_number: str
    class_name: str
    section: str
    total: float
    paid: float
    balance: float
    overdue: float
    next_due_date: date | None
    primary_contact_phone: str


class FeeReport(BaseModel):
    total: float
    collected: float
    balance: float
    overdue: float
    students: list[StudentFeeSummary]


class ReceiptOut(BaseModel):
    receipt_number: str
    paid_on: date
    school_name: str
    school_code: str
    school_address: str
    school_phone: str
    student_name: str
    admission_number: str
    class_name: str
    section: str
    fee_name: str
    term_label: str
    academic_year: str
    amount: float
    method: str
    reference: str
    received_by_name: str
    balance_after: float
    status: str


class ReminderRequest(BaseModel):
    class_id: str | None = None
    only_overdue: bool = True


class ReminderResult(BaseModel):
    students_with_dues: int
    alerts_created: int
