from datetime import date as date_type
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ContactInfo(BaseModel):
    address: str = ""
    phone: str = ""
    email: str = ""
    map_url: str = ""


class BannerItem(BaseModel):
    id: str
    url: str
    caption: str


class GalleryItem(BaseModel):
    id: str
    url: str
    caption: str


class ActivityItem(BaseModel):
    id: str
    title: str
    date: str
    description: str


class NoticeItem(BaseModel):
    id: str
    title: str
    date: str


class HighlightItem(BaseModel):
    value: str = Field(min_length=1, max_length=20)
    label: str = Field(min_length=1, max_length=60)


class ProgramItem(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    level: str = Field(default="", max_length=40)  # UG, PG, Diploma, Ph.D
    duration: str = Field(default="", max_length=40)
    seats: str = Field(default="", max_length=20)
    description: str = Field(default="", max_length=400)


class DepartmentItem(BaseModel):
    name: str
    code: str


class PlacementSummary(BaseModel):
    recruiters: list[str]
    students_placed: int
    highest_package: float | None
    average_package: float | None


class SchoolSiteResponse(BaseModel):
    school_id: str
    name: str
    code: str
    subdomain: str
    template: str
    logo_url: str | None = None
    banners: list[BannerItem] = []
    about: str = ""
    contact: ContactInfo = ContactInfo()
    gallery: list[GalleryItem] = []
    activities: list[ActivityItem] = []
    notices: list[NoticeItem] = []
    admissions_open: bool = False  # public site only: shows the "Apply for admission" button
    tagline: str = ""
    primary_color: str | None = None  # None: the template's own colour
    accent_color: str | None = None
    hidden_sections: list[str] = []
    pro_templates: bool = False  # whether the school may choose Pro templates
    established: str = ""
    accreditation: str = ""
    highlights: list[HighlightItem] = []
    programs: list[ProgramItem] = []
    principal_name: str = ""
    principal_title: str = ""
    principal_message: str = ""
    departments: list[DepartmentItem] = []  # from the college's departments
    placements: PlacementSummary | None = None  # public site, when the placements module is on and someone is placed


class CollegeInfoRequest(BaseModel):
    established: str = Field(default="", max_length=10)
    accreditation: str = Field(default="", max_length=300)
    highlights: list[HighlightItem] = Field(default_factory=list, max_length=6)
    programs: list[ProgramItem] = Field(default_factory=list, max_length=40)
    principal_name: str = Field(default="", max_length=150)
    principal_title: str = Field(default="", max_length=100)
    principal_message: str = Field(default="", max_length=3000)


class AboutContactRequest(BaseModel):
    about: str = Field(default="", max_length=4000)
    contact: ContactInfo


class TemplateRequest(BaseModel):
    template: str

    @field_validator("template")
    @classmethod
    def _known(cls, value: str) -> str:
        from app.modules.super_admin.schemas import ALLOWED_TEMPLATES

        if value not in ALLOWED_TEMPLATES:
            raise ValueError("Unknown template.")
        return value


_HEX = r"^#[0-9a-fA-F]{6}$"


class CustomizeRequest(BaseModel):
    tagline: str = Field(default="", max_length=200)
    primary_color: str | None = Field(default=None, pattern=_HEX)
    accent_color: str | None = Field(default=None, pattern=_HEX)
    hidden_sections: list[Literal["about", "events", "gallery", "notices", "highlights", "programs", "placements", "principal"]] = Field(
        default_factory=list
    )

    @field_validator("tagline", mode="before")
    @classmethod
    def _strip(cls, value):
        return value.strip() if isinstance(value, str) else value


class NoticeRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    date: date_type


class ActivityRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    date: date_type
    description: str = Field(default="", max_length=2000)
