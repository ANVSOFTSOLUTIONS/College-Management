"""Placements: companies, recruitment drives, and students' applications.

A drive can be limited to some departments and to a minimum CGPA (from
published semester-end results). Students see open drives, whether they are
eligible and why not, and apply while the drive is open and before its last
date. The placement cell moves applications through shortlisted → selected /
rejected; selected students count as placed.
"""

import json
import uuid
from datetime import date, datetime
from typing import Literal

import aiomysql
from fastapi import status
from pydantic import BaseModel, Field, field_validator

from app.api.deps import CurrentUser
from app.core.errors import AppError
from app.db.helpers import execute, fetch_all, fetch_one
from app.modules.alerts.service import today_ist
from app.modules.exams.service import cgpa

DriveStatus = Literal["open", "closed", "completed"]
ApplicationStatus = Literal["applied", "shortlisted", "selected", "rejected"]


def _strip(value):
    return value.strip() if isinstance(value, str) else value


class CompanyIn(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    industry: str = Field(default="", max_length=100)
    website: str = Field(default="", max_length=200)

    _strip_text = field_validator("name", "industry", "website", mode="before")(_strip)


class CompanyOut(CompanyIn):
    id: str
    drives: int
    selected: int


class DriveIn(BaseModel):
    company_id: str
    role_title: str = Field(min_length=1, max_length=150)
    package_lpa: float | None = Field(default=None, ge=0, le=1000)
    location: str = Field(default="", max_length=150)
    drive_date: date | None = None
    last_date: date | None = None
    min_cgpa: float | None = Field(default=None, ge=0, le=10)
    eligible_department_ids: list[str] = Field(default_factory=list, max_length=100)
    description: str = Field(default="", max_length=5000)
    status: DriveStatus = "open"

    _strip_text = field_validator("role_title", "location", "description", mode="before")(_strip)


class DriveOut(BaseModel):
    id: str
    company_id: str
    company_name: str
    role_title: str
    package_lpa: float | None
    location: str
    drive_date: date | None
    last_date: date | None
    min_cgpa: float | None
    eligible_department_ids: list[str]
    eligible_departments: list[str]
    description: str
    status: DriveStatus
    applicants: int
    shortlisted: int
    selected: int


class StudentDriveOut(DriveOut):
    eligible: bool
    reason: str  # why not eligible, or '' when eligible
    my_status: ApplicationStatus | None


class ApplicationOut(BaseModel):
    id: str
    student_id: str
    full_name: str
    admission_number: str
    class_name: str
    department: str | None
    cgpa: float | None
    status: ApplicationStatus
    applied_at: datetime


class StatusIn(BaseModel):
    status: ApplicationStatus


class PlacementStats(BaseModel):
    companies: int
    drives: int
    open_drives: int
    applications: int
    students_placed: int
    highest_package: float | None
    average_package: float | None


def _not_found(what: str) -> AppError:
    return AppError(status.HTTP_404_NOT_FOUND, f"{what}_not_found", f"{what.capitalize()} not found.")


# --- Companies ------------------------------------------------------------------


async def list_companies(school_id: str) -> list[CompanyOut]:
    rows = await fetch_all(
        """
        SELECT c.*, (SELECT COUNT(*) FROM placement_drives d WHERE d.company_id = c.id) AS drives,
               (SELECT COUNT(*) FROM placement_applications a JOIN placement_drives d ON d.id = a.drive_id
                 WHERE d.company_id = c.id AND a.status = 'selected') AS selected
        FROM placement_companies c WHERE c.school_id = %s ORDER BY c.name
        """,
        (school_id,),
    )
    return [CompanyOut(id=r["id"], name=r["name"], industry=r["industry"], website=r["website"], drives=r["drives"], selected=r["selected"]) for r in rows]


_COMPANY_TAKEN = AppError(status.HTTP_409_CONFLICT, "company_exists", "A company with this name already exists.")


async def create_company(school_id: str, payload: CompanyIn) -> str:
    company_id = str(uuid.uuid4())
    try:
        await execute(
            "INSERT INTO placement_companies (id, school_id, name, industry, website) VALUES (%s, %s, %s, %s, %s)",
            (company_id, school_id, payload.name, payload.industry, payload.website),
        )
    except aiomysql.IntegrityError as exc:
        raise _COMPANY_TAKEN from exc
    return company_id


async def update_company(school_id: str, company_id: str, payload: CompanyIn) -> None:
    await _company(school_id, company_id)
    try:
        await execute(
            "UPDATE placement_companies SET name = %s, industry = %s, website = %s WHERE id = %s",
            (payload.name, payload.industry, payload.website, company_id),
        )
    except aiomysql.IntegrityError as exc:
        raise _COMPANY_TAKEN from exc


async def delete_company(school_id: str, company_id: str) -> None:
    await _company(school_id, company_id)
    if await fetch_one("SELECT id FROM placement_drives WHERE company_id = %s LIMIT 1", (company_id,)):
        raise AppError(status.HTTP_409_CONFLICT, "company_has_drives", "This company has drives. Delete them first.")
    await execute("DELETE FROM placement_companies WHERE id = %s", (company_id,))


async def _company(school_id: str, company_id: str) -> dict:
    row = await fetch_one("SELECT * FROM placement_companies WHERE school_id = %s AND id = %s", (school_id, company_id))
    if row is None:
        raise _not_found("company")
    return row


# --- Drives ---------------------------------------------------------------------

_DRIVE_SELECT = """
    SELECT d.*, c.name AS company_name,
           (SELECT COUNT(*) FROM placement_applications a WHERE a.drive_id = d.id) AS applicants,
           (SELECT COUNT(*) FROM placement_applications a WHERE a.drive_id = d.id AND a.status = 'shortlisted') AS shortlisted,
           (SELECT COUNT(*) FROM placement_applications a WHERE a.drive_id = d.id AND a.status = 'selected') AS selected
    FROM placement_drives d JOIN placement_companies c ON c.id = d.company_id
"""


def _department_ids(row: dict) -> list[str]:
    try:
        return json.loads(row["eligible_departments"] or "[]")
    except (TypeError, ValueError):
        return []


async def _drives_out(school_id: str, rows: list[dict]) -> list[DriveOut]:
    names = {d["id"]: d["code"] for d in await fetch_all("SELECT id, code FROM departments WHERE school_id = %s", (school_id,))}
    result = []
    for r in rows:
        ids = _department_ids(r)
        result.append(
            DriveOut(
                id=r["id"], company_id=r["company_id"], company_name=r["company_name"], role_title=r["role_title"],
                package_lpa=float(r["package_lpa"]) if r["package_lpa"] is not None else None, location=r["location"],
                drive_date=r["drive_date"], last_date=r["last_date"], min_cgpa=float(r["min_cgpa"]) if r["min_cgpa"] is not None else None,
                eligible_department_ids=ids, eligible_departments=[names[i] for i in ids if i in names], description=r["description"] or "",
                status=r["status"], applicants=r["applicants"], shortlisted=r["shortlisted"], selected=r["selected"],
            )
        )
    return result


async def list_drives(school_id: str) -> list[DriveOut]:
    rows = await fetch_all(f"{_DRIVE_SELECT} WHERE d.school_id = %s ORDER BY d.status = 'open' DESC, d.drive_date DESC, d.created_at DESC", (school_id,))
    return await _drives_out(school_id, rows)


async def _drive_row(school_id: str, drive_id: str) -> dict:
    row = await fetch_one(f"{_DRIVE_SELECT} WHERE d.school_id = %s AND d.id = %s", (school_id, drive_id))
    if row is None:
        raise _not_found("drive")
    return row


async def _check_drive(school_id: str, payload: DriveIn) -> str:
    await _company(school_id, payload.company_id)
    ids = list(dict.fromkeys(payload.eligible_department_ids))
    if ids:
        found = await fetch_all(
            f"SELECT id FROM departments WHERE school_id = %s AND id IN ({', '.join(['%s'] * len(ids))})", (school_id, *ids)
        )
        if len(found) != len(ids):
            raise AppError(status.HTTP_400_BAD_REQUEST, "invalid_department", "Choose departments of this college.")
    if payload.drive_date and payload.last_date and payload.last_date > payload.drive_date:
        raise AppError(status.HTTP_400_BAD_REQUEST, "invalid_dates", "The last date to apply must be on or before the drive date.")
    return json.dumps(ids)


async def create_drive(school_id: str, payload: DriveIn) -> DriveOut:
    departments = await _check_drive(school_id, payload)
    drive_id = str(uuid.uuid4())
    await execute(
        """
        INSERT INTO placement_drives (id, school_id, company_id, role_title, package_lpa, location, drive_date, last_date, min_cgpa,
                                      eligible_departments, description, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (drive_id, school_id, payload.company_id, payload.role_title, payload.package_lpa, payload.location, payload.drive_date,
         payload.last_date, payload.min_cgpa, departments, payload.description, payload.status),
    )
    return (await _drives_out(school_id, [await _drive_row(school_id, drive_id)]))[0]


async def update_drive(school_id: str, drive_id: str, payload: DriveIn) -> DriveOut:
    await _drive_row(school_id, drive_id)
    departments = await _check_drive(school_id, payload)
    await execute(
        """
        UPDATE placement_drives SET company_id = %s, role_title = %s, package_lpa = %s, location = %s, drive_date = %s, last_date = %s,
               min_cgpa = %s, eligible_departments = %s, description = %s, status = %s
        WHERE id = %s
        """,
        (payload.company_id, payload.role_title, payload.package_lpa, payload.location, payload.drive_date, payload.last_date,
         payload.min_cgpa, departments, payload.description, payload.status, drive_id),
    )
    return (await _drives_out(school_id, [await _drive_row(school_id, drive_id)]))[0]


async def delete_drive(school_id: str, drive_id: str) -> None:
    await _drive_row(school_id, drive_id)
    await execute("DELETE FROM placement_drives WHERE id = %s", (drive_id,))


# --- Applications -----------------------------------------------------------------


async def applications(school_id: str, drive_id: str) -> list[ApplicationOut]:
    await _drive_row(school_id, drive_id)
    rows = await fetch_all(
        """
        SELECT a.*, s.full_name, s.admission_number, CONCAT(c.name, ' - ', c.section) AS class_name, d.code AS department
        FROM placement_applications a JOIN students s ON s.id = a.student_id JOIN classes c ON c.id = s.class_id
        LEFT JOIN departments d ON d.id = c.department_id
        WHERE a.drive_id = %s ORDER BY FIELD(a.status, 'selected', 'shortlisted', 'applied', 'rejected'), s.full_name
        """,
        (drive_id,),
    )
    return [
        ApplicationOut(
            id=r["id"], student_id=r["student_id"], full_name=r["full_name"], admission_number=r["admission_number"], class_name=r["class_name"],
            department=r["department"], cgpa=await cgpa(r["student_id"]), status=r["status"], applied_at=r["applied_at"],
        )
        for r in rows
    ]


async def set_status(school_id: str, application_id: str, new_status: str) -> None:
    row = await fetch_one("SELECT id FROM placement_applications WHERE id = %s AND school_id = %s", (application_id, school_id))
    if row is None:
        raise _not_found("application")
    await execute("UPDATE placement_applications SET status = %s WHERE id = %s", (new_status, application_id))


# --- Student side -----------------------------------------------------------------


async def _me(user: CurrentUser) -> dict:
    row = await fetch_one(
        """
        SELECT s.*, c.department_id FROM students s JOIN classes c ON c.id = s.class_id
        WHERE s.user_id = %s AND s.school_id = %s AND s.status = 'active'
        """,
        (user.id, user.school_id),
    )
    if row is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "student_not_found", "Student not found.")
    return row


def _ineligible_reason(drive: DriveOut, student: dict, my_cgpa: float | None, today: date) -> str:
    if drive.status != "open":
        return "Applications are closed."
    if drive.last_date and drive.last_date < today:
        return "The last date to apply has passed."
    if drive.eligible_department_ids and student["department_id"] not in drive.eligible_department_ids:
        return f"Only for {', '.join(drive.eligible_departments)}."
    if drive.min_cgpa is not None and (my_cgpa is None or my_cgpa < drive.min_cgpa):
        return f"Needs CGPA {drive.min_cgpa} or more" + (f" (yours is {my_cgpa})." if my_cgpa is not None else " (no CGPA yet).")
    return ""


async def student_drives(user: CurrentUser) -> list[StudentDriveOut]:
    student = await _me(user)
    my_cgpa, today = await cgpa(student["id"]), today_ist()
    mine = {
        r["drive_id"]: r["status"]
        for r in await fetch_all("SELECT drive_id, status FROM placement_applications WHERE student_id = %s", (student["id"],))
    }
    rows = await fetch_all(
        f"{_DRIVE_SELECT} WHERE d.school_id = %s AND (d.status = 'open' OR d.id IN (SELECT drive_id FROM placement_applications WHERE student_id = %s)) "
        "ORDER BY d.drive_date IS NULL, d.drive_date",
        (user.school_id, student["id"]),
    )
    result = []
    for drive in await _drives_out(user.school_id, rows):
        reason = _ineligible_reason(drive, student, my_cgpa, today)
        result.append(StudentDriveOut(**drive.model_dump(), eligible=not reason, reason=reason, my_status=mine.get(drive.id)))
    return result


async def apply(user: CurrentUser, drive_id: str) -> None:
    student = await _me(user)
    drive = (await _drives_out(user.school_id, [await _drive_row(user.school_id, drive_id)]))[0]
    reason = _ineligible_reason(drive, student, await cgpa(student["id"]), today_ist())
    if reason:
        raise AppError(status.HTTP_409_CONFLICT, "not_eligible", reason)
    try:
        await execute(
            "INSERT INTO placement_applications (id, school_id, drive_id, student_id) VALUES (%s, %s, %s, %s)",
            (str(uuid.uuid4()), user.school_id, drive_id, student["id"]),
        )
    except aiomysql.IntegrityError as exc:
        raise AppError(status.HTTP_409_CONFLICT, "already_applied", "You have already applied to this drive.") from exc


async def withdraw(user: CurrentUser, drive_id: str) -> None:
    student = await _me(user)
    row = await fetch_one("SELECT status FROM placement_applications WHERE drive_id = %s AND student_id = %s", (drive_id, student["id"]))
    if row is None:
        raise _not_found("application")
    if row["status"] != "applied":
        raise AppError(status.HTTP_409_CONFLICT, "application_in_progress", "The placement cell has already acted on this application.")
    await execute("DELETE FROM placement_applications WHERE drive_id = %s AND student_id = %s", (drive_id, student["id"]))


async def stats(school_id: str) -> PlacementStats:
    counts = await fetch_one(
        """
        SELECT (SELECT COUNT(*) FROM placement_companies WHERE school_id = %s) AS companies,
               (SELECT COUNT(*) FROM placement_drives WHERE school_id = %s) AS drives,
               (SELECT COUNT(*) FROM placement_drives WHERE school_id = %s AND status = 'open') AS open_drives,
               (SELECT COUNT(*) FROM placement_applications WHERE school_id = %s) AS applications,
               (SELECT COUNT(DISTINCT student_id) FROM placement_applications WHERE school_id = %s AND status = 'selected') AS placed
        """,
        (school_id,) * 5,
    )
    packages = await fetch_one(
        """
        SELECT MAX(d.package_lpa) AS highest, AVG(d.package_lpa) AS average FROM placement_applications a
        JOIN placement_drives d ON d.id = a.drive_id WHERE a.school_id = %s AND a.status = 'selected' AND d.package_lpa IS NOT NULL
        """,
        (school_id,),
    )
    return PlacementStats(
        companies=counts["companies"], drives=counts["drives"], open_drives=counts["open_drives"], applications=counts["applications"],
        students_placed=counts["placed"],
        highest_package=float(packages["highest"]) if packages["highest"] is not None else None,
        average_package=round(float(packages["average"]), 2) if packages["average"] is not None else None,
    )
