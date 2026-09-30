"""The platform's marketing landing page: contact details and demo requests."""

import uuid
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from pydantic import BaseModel, EmailStr, Field, field_validator

from app.api.deps import CurrentUser, require_roles
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.mailer import send_email
from app.core.phone import normalize_indian_mobile
from app.core.rate_limit import is_rate_limited, record_attempt
from app.db.helpers import execute, fetch_all, fetch_one

public_router = APIRouter(prefix="/public", tags=["marketing"])
admin_router = APIRouter(prefix="/super-admin", tags=["super-admin"])

_super_admin = require_roles("super_admin")
LeadStatus = Literal["new", "contacted", "converted", "closed"]


def _strip(value):
    return value.strip() if isinstance(value, str) else value


class PlatformContact(BaseModel):
    whatsapp_number: str = Field(default="", max_length=20)
    phone: str = Field(default="", max_length=20)
    email: EmailStr | Literal[""] = ""

    _strip_text = field_validator("whatsapp_number", "phone", mode="before")(_strip)


class DemoRequestIn(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    institution: str = Field(min_length=2, max_length=200)
    phone: str = Field(min_length=6, max_length=20)
    email: EmailStr | Literal[""] = ""
    city: str = Field(default="", max_length=100)
    students: str = Field(default="", max_length=20)
    message: str = Field(default="", max_length=1000)
    # Hidden field real visitors leave empty; bots tend to fill it.
    website: str = ""

    _strip_text = field_validator("name", "institution", "phone", "city", "students", "message", mode="before")(_strip)


class DemoRequestOut(BaseModel):
    id: str
    name: str
    institution: str
    phone: str
    email: str
    city: str
    students: str
    message: str
    status: LeadStatus
    notes: str
    created_at: str


class UpdateLeadRequest(BaseModel):
    status: LeadStatus | None = None
    notes: str | None = Field(default=None, max_length=1000)


async def _contact() -> PlatformContact:
    row = await fetch_one("SELECT * FROM platform_settings WHERE id = 1")
    if row is None:
        return PlatformContact()
    return PlatformContact(whatsapp_number=row["whatsapp_number"], phone=row["phone"], email=row["email"])


# --- Public ---------------------------------------------------------------------


@public_router.get("/platform", response_model=PlatformContact)
async def platform_contact() -> PlatformContact:
    """Contact details shown on the landing page (empty until the super admin fills them)."""
    return await _contact()


def _demo_email(payload: DemoRequestIn) -> tuple[str, str]:
    subject = f"New demo request: {payload.institution} ({payload.city or 'city not given'})"
    lines = [
        "A new demo request came in from the ANV College ERP website.",
        "",
        f"Name:        {payload.name}",
        f"College:     {payload.institution}",
        f"Phone:       {payload.phone}",
        f"Email:       {payload.email or '-'}",
        f"City:        {payload.city or '-'}",
        f"Students:    {payload.students or '-'}",
        "",
        "Message:",
        payload.message or "-",
        "",
        "It is also listed under Super admin > Demo requests.",
    ]
    return subject, "\n".join(lines)


async def _notify_team(payload: DemoRequestIn) -> None:
    recipients = [a.strip() for a in get_settings().demo_request_emails.split(",") if a.strip()]
    subject, body = _demo_email(payload)
    await send_email(recipients, subject, body, reply_to=str(payload.email) or None)


@public_router.post("/demo-requests", status_code=status.HTTP_202_ACCEPTED)
async def request_demo(payload: DemoRequestIn, request: Request, background: BackgroundTasks) -> dict:
    client = request.client.host if request.client else "unknown"
    key = f"demo:{client}"
    if is_rate_limited(key, max_attempts=5, window_seconds=3600):
        raise AppError(status.HTTP_429_TOO_MANY_REQUESTS, "too_many_requests", "Too many requests. Please try again later.")
    record_attempt(key)
    if payload.website:
        return {"received": True}  # quietly drop bot submissions
    if normalize_indian_mobile(payload.phone) is None and len("".join(c for c in payload.phone if c.isdigit())) < 8:
        raise AppError(status.HTTP_400_BAD_REQUEST, "invalid_phone", "Enter a valid phone number.")
    await execute(
        """
        INSERT INTO demo_requests (id, name, institution, phone, email, city, students, message)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (str(uuid.uuid4()), payload.name, payload.institution, payload.phone, str(payload.email).lower(), payload.city,
         payload.students, payload.message),
    )
    # After the lead is saved, so a mail problem never loses it.
    background.add_task(_notify_team, payload)
    return {"received": True}


# --- Super admin ----------------------------------------------------------------


def _lead_out(row: dict) -> DemoRequestOut:
    return DemoRequestOut(**{k: row[k] for k in DemoRequestOut.model_fields if k != "created_at"}, created_at=row["created_at"].isoformat())


@admin_router.get("/leads", response_model=list[DemoRequestOut])
async def list_leads(current_user: CurrentUser = Depends(_super_admin)) -> list[DemoRequestOut]:
    rows = await fetch_all("SELECT * FROM demo_requests ORDER BY status = 'new' DESC, created_at DESC LIMIT 500")
    return [_lead_out(r) for r in rows]


@admin_router.patch("/leads/{lead_id}", response_model=DemoRequestOut)
async def update_lead(lead_id: str, payload: UpdateLeadRequest, current_user: CurrentUser = Depends(_super_admin)) -> DemoRequestOut:
    updates = payload.model_dump(exclude_unset=True, exclude_none=True)
    if updates:
        sets = ", ".join(f"{k} = %s" for k in updates)
        await execute(f"UPDATE demo_requests SET {sets} WHERE id = %s", (*updates.values(), lead_id))
    row = await fetch_one("SELECT * FROM demo_requests WHERE id = %s", (lead_id,))
    if row is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "lead_not_found", "Lead not found.")
    return _lead_out(row)


@admin_router.get("/platform-settings", response_model=PlatformContact)
async def get_platform_settings(current_user: CurrentUser = Depends(_super_admin)) -> PlatformContact:
    return await _contact()


@admin_router.put("/platform-settings", response_model=PlatformContact)
async def save_platform_settings(payload: PlatformContact, current_user: CurrentUser = Depends(_super_admin)) -> PlatformContact:
    await execute(
        """
        INSERT INTO platform_settings (id, whatsapp_number, phone, email) VALUES (1, %s, %s, %s)
        ON DUPLICATE KEY UPDATE whatsapp_number = VALUES(whatsapp_number), phone = VALUES(phone), email = VALUES(email)
        """,
        (payload.whatsapp_number, payload.phone, str(payload.email).lower()),
    )
    return await _contact()
