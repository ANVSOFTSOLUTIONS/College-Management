"""Certificate requests: a student or parent asks for a bonafide certificate or TC in the app.

The office approves (which issues the certificate with the next serial number,
ready to print) or rejects with a note. The requester is notified either way.
"""

import uuid
from datetime import datetime
from typing import Literal

from fastapi import status
from pydantic import BaseModel, Field, field_validator

from app.api.deps import CurrentUser
from app.core.errors import AppError
from app.db.helpers import execute, fetch_all, fetch_one
from app.modules.certificates import service as certificates
from app.modules.notifications import service as notifications

KIND_TITLE = {"bonafide": "Bonafide Certificate", "tc": "Transfer Certificate"}


class RequestIn(BaseModel):
    kind: Literal["bonafide", "tc"]
    purpose: str = Field(min_length=3, max_length=200)

    _strip = field_validator("purpose", mode="before")(lambda v: v.strip() if isinstance(v, str) else v)


class DecisionIn(BaseModel):
    note: str = Field(default="", max_length=300)


class RequestOut(BaseModel):
    id: str
    student_id: str
    full_name: str
    admission_number: str
    batch: str
    kind: str
    title: str
    purpose: str
    status: str
    note: str
    certificate_id: str | None
    serial_no: str | None
    created_at: datetime
    decided_at: datetime | None


_SELECT = """
    SELECT r.*, s.full_name, s.admission_number, CONCAT(c.name, ' - ', c.section) AS batch, sc.serial_no
    FROM certificate_requests r JOIN students s ON s.id = r.student_id JOIN classes c ON c.id = s.class_id
    LEFT JOIN student_certificates sc ON sc.id = r.certificate_id
"""


def _out(row: dict) -> RequestOut:
    return RequestOut(**{k: row[k] for k in RequestOut.model_fields if k in row}, title=KIND_TITLE[row["kind"]])


async def _get(user: CurrentUser, request_id: str) -> dict:
    row = await fetch_one(f"{_SELECT} WHERE r.id = %s AND r.school_id = %s", (request_id, user.school_id))
    if row is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "request_not_found", "Request not found.")
    return row


async def create(user: CurrentUser, student: dict, payload: RequestIn) -> list[RequestOut]:
    pending = await fetch_one(
        "SELECT id FROM certificate_requests WHERE student_id = %s AND kind = %s AND status = 'pending'", (student["id"], payload.kind)
    )
    if pending:
        raise AppError(status.HTTP_409_CONFLICT, "request_pending", f"A {KIND_TITLE[payload.kind]} request is already pending.")
    await execute(
        "INSERT INTO certificate_requests (id, school_id, student_id, requested_by, kind, purpose) VALUES (%s, %s, %s, %s, %s, %s)",
        (str(uuid.uuid4()), student["school_id"], student["id"], user.id, payload.kind, payload.purpose),
    )
    await notifications.notify(
        await notifications.admin_user_ids(student["school_id"]), school_id=student["school_id"],
        title=f"{KIND_TITLE[payload.kind]} requested", body=f"{student['full_name']} ({student['admission_number']}): {payload.purpose}", link="certificate-requests",
    )
    return await for_student(student["id"])


async def for_student(student_id: str) -> list[RequestOut]:
    return [_out(r) for r in await fetch_all(f"{_SELECT} WHERE r.student_id = %s ORDER BY r.created_at DESC, r.id", (student_id,))]


async def list_all(user: CurrentUser, status_filter: str | None) -> list[RequestOut]:
    where, params = "r.school_id = %s", [user.school_id]
    if status_filter:
        where += " AND r.status = %s"
        params.append(status_filter)
    rows = await fetch_all(f"{_SELECT} WHERE {where} ORDER BY r.status <> 'pending', r.created_at DESC", tuple(params))
    return [_out(r) for r in rows]


async def approve(user: CurrentUser, request_id: str, payload: DecisionIn) -> RequestOut:
    row = await _get(user, request_id)
    if row["status"] != "pending":
        raise AppError(status.HTTP_409_CONFLICT, "already_decided", "This request was already handled.")
    issue = certificates.IssueCertificateRequest(kind=row["kind"], purpose=row["purpose"] if row["kind"] == "bonafide" else "",
                                                 reason=row["purpose"] if row["kind"] == "tc" else "")
    certificate = await certificates.issue(user, row["student_id"], issue)
    await execute(
        "UPDATE certificate_requests SET status = 'issued', note = %s, certificate_id = %s, decided_at = CURRENT_TIMESTAMP WHERE id = %s",
        (payload.note.strip(), certificate.id, request_id),
    )
    await notifications.notify([row["requested_by"]], school_id=user.school_id, title=f"{certificate.title} ready",
                               body=f"{certificate.serial_no}: collect it from the college office.", link="certificates")
    return _out(await _get(user, request_id))


async def reject(user: CurrentUser, request_id: str, payload: DecisionIn) -> RequestOut:
    row = await _get(user, request_id)
    if row["status"] != "pending":
        raise AppError(status.HTTP_409_CONFLICT, "already_decided", "This request was already handled.")
    if len(payload.note.strip()) < 3:
        raise AppError(status.HTTP_400_BAD_REQUEST, "note_required", "Tell the student why the request is rejected.")
    await execute(
        "UPDATE certificate_requests SET status = 'rejected', note = %s, decided_at = CURRENT_TIMESTAMP WHERE id = %s", (payload.note.strip(), request_id)
    )
    await notifications.notify([row["requested_by"]], school_id=user.school_id, title=f"{KIND_TITLE[row['kind']]} request rejected",
                               body=payload.note.strip(), link="certificates")
    return _out(await _get(user, request_id))
