"""Scholarships: government schemes (fee reimbursement, post-matric ...) tracked per student and year.

The office records each application and moves it through applied, verified,
sanctioned and disbursed (or rejected), with the amounts sanctioned and
received. Students and parents see their own status in the app.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

import aiomysql
from fastapi import status
from pydantic import BaseModel, Field, field_validator

from app.api.deps import CurrentUser
from app.core.errors import AppError
from app.db.helpers import execute, fetch_all, fetch_one

Status = Literal["applied", "verified", "sanctioned", "disbursed", "rejected"]


def _strip(value):
    return value.strip() if isinstance(value, str) else value


class ScholarshipIn(BaseModel):
    student_id: str
    scheme: str = Field(min_length=2, max_length=100)
    academic_year: str = Field(min_length=4, max_length=9)
    application_no: str = Field(default="", max_length=50)
    amount_sanctioned: Decimal = Field(default=Decimal(0), ge=0, max_digits=10, decimal_places=2)
    amount_received: Decimal = Field(default=Decimal(0), ge=0, max_digits=10, decimal_places=2)
    status: Status = "applied"
    remarks: str = Field(default="", max_length=300)

    _strip = field_validator("scheme", "academic_year", "application_no", "remarks", mode="before")(_strip)


class ScholarshipUpdate(BaseModel):
    application_no: str | None = Field(default=None, max_length=50)
    amount_sanctioned: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    amount_received: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    status: Status | None = None
    remarks: str | None = Field(default=None, max_length=300)

    _strip = field_validator("application_no", "remarks", mode="before")(_strip)


class ScholarshipOut(BaseModel):
    id: str
    student_id: str
    full_name: str
    admission_number: str
    batch: str
    scheme: str
    academic_year: str
    application_no: str
    amount_sanctioned: float
    amount_received: float
    status: str
    remarks: str
    updated_at: datetime


class SchemeSummary(BaseModel):
    scheme: str
    students: int
    sanctioned: float
    received: float
    pending: int


_SELECT = """
    SELECT sc.*, s.full_name, s.admission_number, CONCAT(c.name, ' - ', c.section) AS batch
    FROM student_scholarships sc JOIN students s ON s.id = sc.student_id JOIN classes c ON c.id = s.class_id
"""


def _out(row: dict) -> ScholarshipOut:
    return ScholarshipOut(**{**row, "amount_sanctioned": float(row["amount_sanctioned"]), "amount_received": float(row["amount_received"])})


async def _get(user: CurrentUser, scholarship_id: str) -> ScholarshipOut:
    row = await fetch_one(f"{_SELECT} WHERE sc.id = %s AND sc.school_id = %s", (scholarship_id, user.school_id))
    if row is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "scholarship_not_found", "Scholarship record not found.")
    return _out(row)


async def list_all(user: CurrentUser, class_id: str | None, status_filter: str | None, academic_year: str | None, scheme: str | None) -> list[ScholarshipOut]:
    where, params = ["sc.school_id = %s"], [user.school_id]
    for column, value in (("s.class_id", class_id), ("sc.status", status_filter), ("sc.academic_year", academic_year), ("sc.scheme", scheme)):
        if value:
            where.append(f"{column} = %s")
            params.append(value)
    rows = await fetch_all(f"{_SELECT} WHERE {' AND '.join(where)} ORDER BY sc.academic_year DESC, c.name, c.section, s.admission_number", tuple(params))
    return [_out(r) for r in rows]


async def summary(user: CurrentUser, academic_year: str | None) -> list[SchemeSummary]:
    where, params = "school_id = %s", [user.school_id]
    if academic_year:
        where += " AND academic_year = %s"
        params.append(academic_year)
    rows = await fetch_all(
        f"""
        SELECT scheme, COUNT(*) AS students, SUM(amount_sanctioned) AS sanctioned, SUM(amount_received) AS received,
               SUM(status IN ('applied', 'verified', 'sanctioned')) AS pending
        FROM student_scholarships WHERE {where} GROUP BY scheme ORDER BY scheme
        """,
        tuple(params),
    )
    return [SchemeSummary(scheme=r["scheme"], students=r["students"], sanctioned=float(r["sanctioned"] or 0), received=float(r["received"] or 0),
                          pending=int(r["pending"] or 0)) for r in rows]


async def create(user: CurrentUser, payload: ScholarshipIn) -> ScholarshipOut:
    if not await fetch_one("SELECT id FROM students WHERE id = %s AND school_id = %s", (payload.student_id, user.school_id)):
        raise AppError(status.HTTP_404_NOT_FOUND, "student_not_found", "Student not found.")
    scholarship_id = str(uuid.uuid4())
    try:
        await execute(
            """
            INSERT INTO student_scholarships (id, school_id, student_id, scheme, academic_year, application_no, amount_sanctioned, amount_received, status, remarks)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (scholarship_id, user.school_id, payload.student_id, payload.scheme, payload.academic_year, payload.application_no,
             payload.amount_sanctioned, payload.amount_received, payload.status, payload.remarks),
        )
    except aiomysql.IntegrityError as exc:
        raise AppError(status.HTTP_409_CONFLICT, "scholarship_exists", "This student already has this scheme for that year.") from exc
    return await _get(user, scholarship_id)


async def update(user: CurrentUser, scholarship_id: str, payload: ScholarshipUpdate) -> ScholarshipOut:
    await _get(user, scholarship_id)
    changes = payload.model_dump(exclude_none=True)
    if changes:
        await execute(
            f"UPDATE student_scholarships SET {', '.join(f'{k} = %s' for k in changes)} WHERE id = %s", (*changes.values(), scholarship_id)
        )
    return await _get(user, scholarship_id)


async def delete(user: CurrentUser, scholarship_id: str) -> None:
    await _get(user, scholarship_id)
    await execute("DELETE FROM student_scholarships WHERE id = %s", (scholarship_id,))


async def for_student(student_id: str) -> list[ScholarshipOut]:
    return [_out(r) for r in await fetch_all(f"{_SELECT} WHERE sc.student_id = %s ORDER BY sc.academic_year DESC, sc.scheme", (student_id,))]
