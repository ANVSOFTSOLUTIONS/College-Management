"""Transfer certificates (TC), bonafide certificates and student ID cards.

A certificate stores a snapshot of what it says, so a reprint always matches
the original even if the student's details change later. Issuing a TC marks
the student as left (records kept, login switched off). A certificate issued
by mistake is cancelled, not deleted, so its serial number is never reused.
"""

import json
import uuid
from datetime import date, datetime, timezone
from typing import Literal

from fastapi import status
from pydantic import BaseModel, Field, field_validator

from app.api.deps import CurrentUser
from app.core.errors import AppError
from app.core.words import date_in_words
from app.db.database import db
from app.db.helpers import execute, fetch_all, fetch_one
from app.modules.alerts.service import today_ist
from app.modules.audit import service as audit
from app.modules.fees import service as fees
from app.modules.students import service as students
from app.modules.students.schemas import UpdateStudentRequest

KIND_PREFIX = {"tc": "TC", "bonafide": "BON"}
KIND_TITLE = {"tc": "Transfer Certificate", "bonafide": "Bonafide Certificate"}

class IssueCertificateRequest(BaseModel):
    kind: Literal["tc", "bonafide"]
    # TC fields
    leaving_date: date | None = None
    reason: str = Field(default="", max_length=200)
    conduct: str = Field(default="Good", max_length=50)
    promotion: str = Field(default="", max_length=100)  # e.g. "Yes, to Grade 6"
    remarks: str = Field(default="", max_length=300)
    # Bonafide field
    purpose: str = Field(default="", max_length=200)

    @field_validator("reason", "conduct", "promotion", "remarks", "purpose", mode="before")
    @classmethod
    def _strip(cls, value):
        return value.strip() if isinstance(value, str) else value


class CancelCertificateRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=200)


class CertificateOut(BaseModel):
    id: str
    student_id: str
    kind: str
    title: str
    serial_no: str
    issued_on: date
    details: dict
    school: dict
    issued_by_name: str | None
    cancelled: bool
    cancel_reason: str


class IdCard(BaseModel):
    student_id: str
    full_name: str
    admission_number: str
    class_label: str
    date_of_birth: date | None
    blood_group: str
    parent_name: str
    parent_phone: str
    address: str
    has_photo: bool
    qr_text: str


class IdCardSheet(BaseModel):
    school: dict
    academic_year: str
    cards: list[IdCard]


async def _school(school_id: str) -> dict:
    row = await fetch_one(
        """
        SELECT s.name, s.code, ss.logo_url, ss.contact_address, ss.contact_phone, ss.contact_email
        FROM schools s LEFT JOIN school_sites ss ON ss.school_id = s.id WHERE s.id = %s
        """,
        (school_id,),
    )
    return {
        "name": row["name"], "code": row["code"], "logo_url": row["logo_url"], "address": row["contact_address"] or "",
        "phone": row["contact_phone"] or "", "email": row["contact_email"] or "",
    }


async def _guardians(student_id: str) -> dict[str, dict]:
    rows = await fetch_all("SELECT relation, full_name, phone FROM student_guardians WHERE student_id = %s", (student_id,))
    return {r["relation"]: r for r in rows}


async def _snapshot(user: CurrentUser, student: dict, payload: IssueCertificateRequest, issued_on: date) -> dict:
    cls = await fetch_one("SELECT name, section, academic_year FROM classes WHERE id = %s", (student["class_id"],))
    guardians = await _guardians(student["id"])
    details = {
        "student_name": student["full_name"],
        "admission_number": student["admission_number"],
        "father_name": guardians.get("father", {}).get("full_name", ""),
        "mother_name": guardians.get("mother", {}).get("full_name", ""),
        "guardian_name": guardians.get("guardian", {}).get("full_name", ""),
        "gender": student["gender"],
        "date_of_birth": student["date_of_birth"].isoformat() if student["date_of_birth"] else None,
        "date_of_birth_words": date_in_words(student["date_of_birth"]) if student["date_of_birth"] else "",
        "admission_date": student["admission_date"].isoformat() if student["admission_date"] else None,
        "class_name": f"{cls['name']} - {cls['section']}",
        "academic_year": cls["academic_year"],
        "address": student["address"],
    }
    if payload.kind == "bonafide":
        details["purpose"] = payload.purpose
        return details

    attendance = await fetch_one(
        "SELECT COUNT(*) AS marked, COALESCE(SUM(status IN ('present', 'late')), 0) AS came FROM attendance WHERE student_id = %s AND class_id = %s",
        (student["id"], student["class_id"]),
    )
    account = await fees.student_account(user.school_id, student["id"])
    details.update(
        leaving_date=(payload.leaving_date or issued_on).isoformat(),
        reason=payload.reason or "Parent's request",
        conduct=payload.conduct or "Good",
        promotion=payload.promotion,
        remarks=payload.remarks,
        working_days=attendance["marked"],
        days_present=int(attendance["came"]),
        fees_due=account.balance,
    )
    return details


async def _next_serial(cur, school_id: str, kind: str, year: int) -> str:
    # Same pattern as fee receipts: LAST_INSERT_ID(expr) is per-connection, so two admins never get the same number.
    await cur.execute(
        """
        INSERT INTO certificate_counters (school_id, kind, year, last_number) VALUES (%s, %s, %s, LAST_INSERT_ID(1))
        ON DUPLICATE KEY UPDATE last_number = LAST_INSERT_ID(last_number + 1)
        """,
        (school_id, kind, year),
    )
    await cur.execute("SELECT LAST_INSERT_ID() AS n")
    return f"{KIND_PREFIX[kind]}/{year}/{(await cur.fetchone())['n']:04d}"


def _out(row: dict, school: dict) -> CertificateOut:
    details = row["details"] if isinstance(row["details"], dict) else json.loads(row["details"])
    return CertificateOut(
        id=row["id"], student_id=row["student_id"], kind=row["kind"], title=KIND_TITLE[row["kind"]], serial_no=row["serial_no"],
        issued_on=row["issued_on"], details=details, school=school, issued_by_name=row.get("issued_by_name"),
        cancelled=row["cancelled_at"] is not None, cancel_reason=row["cancel_reason"],
    )


_SELECT = "SELECT sc.*, u.full_name AS issued_by_name FROM student_certificates sc LEFT JOIN users u ON u.id = sc.issued_by"


async def issue(user: CurrentUser, student_id: str, payload: IssueCertificateRequest) -> CertificateOut:
    student = await students.get_student_row(user, student_id)
    if payload.kind == "tc":
        existing = await fetch_one(
            "SELECT serial_no FROM student_certificates WHERE student_id = %s AND kind = 'tc' AND cancelled_at IS NULL", (student_id,)
        )
        if existing:
            raise AppError(status.HTTP_409_CONFLICT, "tc_exists", f"A TC ({existing['serial_no']}) was already issued. Cancel it to issue a new one.")
    elif student["status"] != "active":
        raise AppError(status.HTTP_409_CONFLICT, "student_left", "A bonafide certificate is only for a current student.")
    if payload.kind == "tc" and payload.leaving_date and payload.leaving_date > today_ist():
        raise AppError(status.HTTP_400_BAD_REQUEST, "invalid_date", "The leaving date can't be in the future.")

    issued_on = today_ist()
    details = await _snapshot(user, student, payload, issued_on)
    certificate_id = str(uuid.uuid4())
    async with db.pool.acquire() as conn:
        await conn.begin()
        try:
            async with conn.cursor() as cur:
                serial = await _next_serial(cur, user.school_id, payload.kind, issued_on.year)
                await cur.execute(
                    """
                    INSERT INTO student_certificates (id, school_id, student_id, kind, serial_no, issued_on, details, issued_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (certificate_id, user.school_id, student_id, payload.kind, serial, issued_on, json.dumps(details), user.id),
                )
        except Exception:
            await conn.rollback()
            raise
        await conn.commit()

    if payload.kind == "tc" and student["status"] == "active":
        await students.update_student(user, student_id, UpdateStudentRequest(status="left"))
    certificate = await get(user, certificate_id)
    await audit.record(
        user, "students.certificate", f"Issued {certificate.title} {certificate.serial_no} to {student['full_name']} ({student['admission_number']})",
        entity_type="certificate", entity_id=certificate_id,
    )
    return certificate


async def get(user: CurrentUser, certificate_id: str) -> CertificateOut:
    row = await fetch_one(f"{_SELECT} WHERE sc.id = %s AND sc.school_id = %s", (certificate_id, user.school_id))
    if row is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "certificate_not_found", "Certificate not found.")
    return _out(row, await _school(user.school_id))


async def list_for_student(user: CurrentUser, student_id: str) -> list[CertificateOut]:
    await students.get_student_row(user, student_id)
    rows = await fetch_all(f"{_SELECT} WHERE sc.student_id = %s ORDER BY sc.created_at DESC, sc.serial_no DESC", (student_id,))
    school = await _school(user.school_id)
    return [_out(r, school) for r in rows]


async def recent(user: CurrentUser, limit: int = 50) -> list[CertificateOut]:
    rows = await fetch_all(f"{_SELECT} WHERE sc.school_id = %s ORDER BY sc.created_at DESC, sc.serial_no DESC LIMIT %s", (user.school_id, limit))
    school = await _school(user.school_id)
    return [_out(r, school) for r in rows]


async def cancel(user: CurrentUser, certificate_id: str, payload: CancelCertificateRequest) -> CertificateOut:
    certificate = await get(user, certificate_id)
    if certificate.cancelled:
        raise AppError(status.HTTP_409_CONFLICT, "already_cancelled", "This certificate is already cancelled.")
    await execute(
        "UPDATE student_certificates SET cancelled_at = %s, cancel_reason = %s WHERE id = %s",
        (datetime.now(timezone.utc), payload.reason.strip(), certificate_id),
    )
    await audit.record(
        user, "students.certificate_cancelled",
        f"Cancelled {certificate.title} {certificate.serial_no} of {certificate.details.get('student_name', '')}: {payload.reason.strip()}",
        entity_type="certificate", entity_id=certificate_id,
    )
    return await get(user, certificate_id)


async def id_cards(user: CurrentUser, class_id: str) -> IdCardSheet:
    cls = await fetch_one("SELECT * FROM classes WHERE id = %s AND school_id = %s", (class_id, user.school_id))
    if cls is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "class_not_found", "Class not found.")
    school = await _school(user.school_id)
    rows = await fetch_all(
        """
        SELECT s.*, g.full_name AS contact_name, g.phone AS contact_phone FROM students s
        LEFT JOIN student_guardians g ON g.student_id = s.id AND g.relation = s.primary_contact
        WHERE s.class_id = %s AND s.status = 'active' ORDER BY s.full_name
        """,
        (class_id,),
    )
    label = f"{cls['name']} - {cls['section']}"
    return IdCardSheet(
        school=school,
        academic_year=cls["academic_year"],
        cards=[
            IdCard(
                student_id=r["id"], full_name=r["full_name"], admission_number=r["admission_number"], class_label=label,
                date_of_birth=r["date_of_birth"], blood_group=r["blood_group"], parent_name=r["contact_name"] or r["parent_name"] or "",
                parent_phone=r["contact_phone"] or "", address=r["address"], has_photo=bool(r["photo_path"]),
                qr_text=f"{school['code']}:{r['admission_number']}",
            )
            for r in rows
        ],
    )
