from datetime import date as date_type
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

Gender = Literal["male", "female", "other", ""]
StudentStatus = Literal["active", "left", "graduated"]
Relation = Literal["father", "mother", "guardian"]


def _strip(value):
    return value.strip() if isinstance(value, str) else value


class GuardianIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    phone: str = Field(default="", max_length=20)
    email: EmailStr | Literal[""] = ""
    occupation: str = Field(default="", max_length=100)
    # Only used for relation "guardian", e.g. "Grandfather".
    relation_label: str = Field(default="", max_length=50)

    _strip_text = field_validator("full_name", "phone", "occupation", "relation_label", mode="before")(_strip)


class GuardianOut(BaseModel):
    relation: Relation
    relation_label: str
    full_name: str
    phone: str
    email: str
    occupation: str


class _StudentFields(BaseModel):
    date_of_birth: date_type | None = None
    gender: Gender = ""
    blood_group: str = Field(default="", max_length=5)
    admission_date: date_type | None = None
    address: str = Field(default="", max_length=500)
    email: EmailStr | Literal[""] = ""
    phone: str = Field(default="", max_length=15)
    quota: str = Field(default="", max_length=20)
    father: GuardianIn | None = None
    mother: GuardianIn | None = None
    guardian: GuardianIn | None = None
    primary_contact: Relation | Literal[""] = ""

    _strip_text = field_validator("blood_group", "address", "phone", "quota", mode="before")(_strip)


def _check_primary_contact(model):
    if model.primary_contact and getattr(model, model.primary_contact) is None:
        raise ValueError(f"Primary contact is {model.primary_contact}, but no {model.primary_contact} details were given.")
    return model


class CreateStudentRequest(_StudentFields):
    admission_number: str = Field(min_length=1, max_length=50)
    full_name: str = Field(min_length=1, max_length=200)
    class_id: str

    _strip_ids = field_validator("admission_number", "full_name", mode="before")(_strip)
    _primary = model_validator(mode="after")(_check_primary_contact)


class UpdateStudentRequest(BaseModel):
    """Every field optional; for father/mother/guardian, null removes that contact."""

    admission_number: str | None = Field(default=None, min_length=1, max_length=50)
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    class_id: str | None = None
    date_of_birth: date_type | None = None
    gender: Gender | None = None
    blood_group: str | None = Field(default=None, max_length=5)
    admission_date: date_type | None = None
    address: str | None = Field(default=None, max_length=500)
    email: EmailStr | Literal[""] | None = None
    phone: str | None = Field(default=None, max_length=15)
    quota: str | None = Field(default=None, max_length=20)
    father: GuardianIn | None = None
    mother: GuardianIn | None = None
    guardian: GuardianIn | None = None
    primary_contact: Relation | Literal[""] | None = None
    status: StudentStatus | None = None

    _strip_text = field_validator("admission_number", "full_name", "blood_group", "address", "phone", "quota", mode="before")(_strip)


class ClassRef(BaseModel):
    id: str
    name: str
    section: str


class StudentSummary(BaseModel):
    id: str
    admission_number: str
    full_name: str
    gender: str
    status: StudentStatus
    class_: ClassRef = Field(serialization_alias="class")
    primary_contact_name: str
    primary_contact_phone: str
    has_login: bool = False
    has_photo: bool = False
    pending_documents: int = 0


class StudentDetail(BaseModel):
    id: str
    admission_number: str
    full_name: str
    date_of_birth: date_type | None
    gender: str
    blood_group: str
    admission_date: date_type | None
    address: str
    email: str = ""
    phone: str = ""
    quota: str = ""
    status: StudentStatus
    class_: ClassRef = Field(serialization_alias="class")
    primary_contact: str
    guardians: list[GuardianOut]
    has_photo: bool = False
    login_enabled: bool = False
    school_code: str = ""
    parent_login_phone: str | None = None


# --- Logins, photo, documents -------------------------------------------------

DocumentStatus = Literal["pending", "approved", "rejected"]
DOCUMENT_TYPES = {
    "birth_certificate": "Birth certificate",
    "aadhaar": "Aadhaar card",
    "transfer_certificate": "Transfer certificate",
    "marks_memo": "Marks memo",
    "caste_certificate": "Caste certificate",
    "income_certificate": "Income certificate",
    "other": "Other",
}
DocumentType = Literal[
    "birth_certificate", "aadhaar", "transfer_certificate", "marks_memo", "caste_certificate", "income_certificate", "other"
]


class EnableLoginRequest(BaseModel):
    """Omit the password to generate one. The student must change it at first sign-in."""

    password: str | None = Field(default=None, min_length=8, max_length=72)


class BulkLoginsRequest(BaseModel):
    class_id: str


class LoginCredentials(BaseModel):
    student_id: str
    full_name: str
    school_code: str
    admission_number: str
    password: str


class StudentDocumentOut(BaseModel):
    id: str
    doc_type: DocumentType
    doc_type_label: str
    title: str
    original_name: str
    content_type: str
    size_bytes: int
    status: DocumentStatus
    review_note: str
    uploaded_at: str
    reviewed_at: str | None


class ReviewDocumentRequest(BaseModel):
    status: Literal["approved", "rejected"]
    note: str = Field(default="", max_length=300)

    _strip_note = field_validator("note", mode="before")(_strip)


class UpdateOwnProfileRequest(BaseModel):
    """What a student may change themselves; name, class, and admission number stay with the school."""

    blood_group: str | None = Field(default=None, max_length=5)
    address: str | None = Field(default=None, max_length=500)
    father: GuardianIn | None = None
    mother: GuardianIn | None = None
    guardian: GuardianIn | None = None
    primary_contact: Relation | Literal[""] | None = None

    _strip_text = field_validator("blood_group", "address", mode="before")(_strip)
