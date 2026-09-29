"""Audit log: a permanent record of who changed what, for when there's a dispute.

Modules call `record` after a change succeeds. Recording never breaks the
action itself: if writing the log fails, the failure is logged and ignored.
"""

import json
import logging
import uuid
from datetime import date, timedelta

from pydantic import BaseModel

from app.api.deps import CurrentUser
from app.db.helpers import execute, fetch_all

logger = logging.getLogger(__name__)

# action -> area shown in the filter
AREAS = {
    "marks": "Marks & exams",
    "fees": "Fees",
    "attendance": "Attendance",
    "students": "Students & certificates",
    "staff": "Staff & payroll",
    "admissions": "Admissions",
    "settings": "Settings",
}


class AuditEntry(BaseModel):
    id: str
    action: str
    area: str
    user_name: str
    user_role: str
    summary: str
    details: dict | list | None
    entity_type: str
    entity_id: str | None
    created_at: str


async def record(
    user: CurrentUser | None,
    action: str,
    summary: str,
    *,
    school_id: str | None = None,
    entity_type: str = "",
    entity_id: str | None = None,
    details: dict | list | None = None,
) -> None:
    """`action` is "<area>.<verb>", e.g. "fees.payment_cancelled"."""
    try:
        await execute(
            """
            INSERT INTO audit_log (id, school_id, user_id, user_name, user_role, action, entity_type, entity_id, summary, details)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                str(uuid.uuid4()), school_id or (user.school_id if user else None), user.id if user else None,
                (user.full_name if user else "System")[:200], (user.role if user else "system")[:20], action[:40],
                entity_type[:30], entity_id, summary[:500], json.dumps(details, default=str) if details is not None else None,
            ),
        )
    except Exception:  # noqa: BLE001 - the audit log must never break the action it records
        logger.warning("Could not write the audit log", exc_info=True)


async def list_entries(
    school_id: str | None, *, area: str | None, start: date | None, end: date | None, query: str | None, limit: int = 300
) -> list[AuditEntry]:
    where, params = [], []
    if school_id:
        where.append("school_id = %s")
        params.append(school_id)
    if area:
        where.append("action LIKE %s")
        params.append(f"{area}.%")
    if start:
        where.append("created_at >= %s")
        params.append(start)
    if end:
        where.append("created_at < %s")
        params.append(end + timedelta(days=1))
    if query:
        where.append("(summary LIKE %s OR user_name LIKE %s)")
        params += [f"%{query}%", f"%{query}%"]
    rows = await fetch_all(
        f"SELECT * FROM audit_log {'WHERE ' + ' AND '.join(where) if where else ''} ORDER BY created_at DESC LIMIT %s",
        (*params, limit),
    )
    return [
        AuditEntry(
            id=r["id"], action=r["action"], area=AREAS.get(r["action"].split(".", 1)[0], "Other"), user_name=r["user_name"],
            user_role=r["user_role"], summary=r["summary"], details=json.loads(r["details"]) if isinstance(r["details"], str) else r["details"],
            entity_type=r["entity_type"], entity_id=r["entity_id"], created_at=r["created_at"].isoformat(),
        )
        for r in rows
    ]
