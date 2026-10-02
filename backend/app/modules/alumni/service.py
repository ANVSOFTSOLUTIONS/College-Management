"""Alumni: passed-out students and what they do now (NAAC criterion 5.4).

Graduated students are added in one step from their records (name, roll
number, programme, passing year, contact); the office then keeps their
status up to date: employed, higher studies, self-employed and so on.
"""

import uuid
from datetime import datetime
from typing import Literal

from fastapi import status
from pydantic import BaseModel, EmailStr, Field, field_validator

from app.api.deps import CurrentUser
from app.core.errors import AppError
from app.db.helpers import execute, fetch_all, fetch_one

Status = Literal["unknown", "employed", "higher_studies", "self_employed", "competitive_exams", "other"]
STATUS_LABELS = {
    "unknown": "Not known", "employed": "Employed", "higher_studies": "Higher studies", "self_employed": "Self-employed / business",
    "competitive_exams": "Preparing for exams", "other": "Other",
}


def _strip(value):
    return value.strip() if isinstance(value, str) else value


class AlumnusIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    admission_number: str = Field(default="", max_length=50)
    passing_year: str = Field(min_length=4, max_length=9)
    program: str = Field(default="", max_length=100)
    email: EmailStr | Literal[""] = ""
    phone: str = Field(default="", max_length=15)
    status: Status = "unknown"
    organisation: str = Field(default="", max_length=150)
    designation: str = Field(default="", max_length=100)
    location: str = Field(default="", max_length=100)
    notes: str = Field(default="", max_length=300)

    _strip = field_validator("full_name", "admission_number", "passing_year", "program", "phone", "organisation", "designation", "location", "notes",
                             mode="before")(_strip)


class AlumnusOut(AlumnusIn):
    id: str
    student_id: str | None
    status_label: str
    updated_at: datetime


class AlumniSummary(BaseModel):
    passing_year: str
    total: int
    employed: int
    higher_studies: int
    self_employed: int
    unknown: int


class ImportResult(BaseModel):
    added: int


def _out(row: dict) -> AlumnusOut:
    return AlumnusOut(**{k: row[k] for k in AlumnusOut.model_fields if k in row}, status_label=STATUS_LABELS.get(row["status"], row["status"]))


async def _get(user: CurrentUser, alumnus_id: str) -> dict:
    row = await fetch_one("SELECT * FROM alumni WHERE id = %s AND school_id = %s", (alumnus_id, user.school_id))
    if row is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "alumnus_not_found", "Alumni record not found.")
    return row


async def list_alumni(user: CurrentUser, passing_year: str | None, status_filter: str | None, q: str | None) -> list[AlumnusOut]:
    where, params = ["school_id = %s"], [user.school_id]
    if passing_year:
        where.append("passing_year = %s")
        params.append(passing_year)
    if status_filter:
        where.append("status = %s")
        params.append(status_filter)
    if q:
        where.append("(full_name LIKE %s OR organisation LIKE %s OR admission_number LIKE %s)")
        params += [f"%{q.strip()}%"] * 3
    rows = await fetch_all(f"SELECT * FROM alumni WHERE {' AND '.join(where)} ORDER BY passing_year DESC, full_name", tuple(params))
    return [_out(r) for r in rows]


async def summary(user: CurrentUser) -> list[AlumniSummary]:
    rows = await fetch_all(
        """
        SELECT passing_year, COUNT(*) AS total, SUM(status = 'employed') AS employed, SUM(status = 'higher_studies') AS higher_studies,
               SUM(status = 'self_employed') AS self_employed, SUM(status = 'unknown') AS unknown
        FROM alumni WHERE school_id = %s GROUP BY passing_year ORDER BY passing_year DESC
        """,
        (user.school_id,),
    )
    return [AlumniSummary(passing_year=r["passing_year"], **{k: int(r[k] or 0) for k in ("total", "employed", "higher_studies", "self_employed", "unknown")})
            for r in rows]


async def create(user: CurrentUser, payload: AlumnusIn) -> AlumnusOut:
    alumnus_id = str(uuid.uuid4())
    data = payload.model_dump()
    data["email"] = str(data["email"]).lower()
    await execute(
        f"INSERT INTO alumni (id, school_id, {', '.join(data)}) VALUES (%s, %s, {', '.join(['%s'] * len(data))})",
        (alumnus_id, user.school_id, *data.values()),
    )
    return _out(await _get(user, alumnus_id))


async def update(user: CurrentUser, alumnus_id: str, payload: AlumnusIn) -> AlumnusOut:
    await _get(user, alumnus_id)
    data = payload.model_dump()
    data["email"] = str(data["email"]).lower()
    await execute(f"UPDATE alumni SET {', '.join(f'{k} = %s' for k in data)} WHERE id = %s", (*data.values(), alumnus_id))
    return _out(await _get(user, alumnus_id))


async def delete(user: CurrentUser, alumnus_id: str) -> None:
    await _get(user, alumnus_id)
    await execute("DELETE FROM alumni WHERE id = %s", (alumnus_id,))


async def import_graduated(user: CurrentUser) -> ImportResult:
    """Adds every graduated student who isn't in the alumni list yet; passing year = their last batch's year."""
    added = await execute(
        """
        INSERT INTO alumni (id, school_id, student_id, full_name, admission_number, passing_year, program, email, phone)
        SELECT UUID(), s.school_id, s.id, s.full_name, s.admission_number, c.academic_year,
               c.name, COALESCE(s.email, ''), COALESCE(s.phone, '')
        FROM students s JOIN classes c ON c.id = s.class_id
        WHERE s.school_id = %s AND s.status = 'graduated' AND NOT EXISTS (SELECT 1 FROM alumni a WHERE a.student_id = s.id)
        """,
        (user.school_id,),
    )
    return ImportResult(added=added or 0)
