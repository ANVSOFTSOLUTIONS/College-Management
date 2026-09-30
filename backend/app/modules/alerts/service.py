"""Parent alerts: build the message, find the parent's phone, send (or not), log it."""

import asyncio
import uuid
from datetime import date, datetime, timedelta, timezone

import aiomysql
from pydantic import BaseModel

from app.api.deps import CurrentUser
from app.core.config import get_settings
from app.db.helpers import execute, fetch_all, fetch_one
from app.integrations.sms import get_sms_sender

# Schools on this platform are in India; "today" for absence alerts is IST.
IST = timezone(timedelta(hours=5, minutes=30))
_SEND_CONCURRENCY = 5

REMARK_LABELS = {
    "missed_exam": "missed an exam",
    "absent_class": "was absent from class",
    "homework": "homework",
    "behaviour": "behaviour",
    "appreciation": "appreciation",
    "other": "note",
}


def today_ist() -> date:
    return datetime.now(IST).date()


class AlertOut(BaseModel):
    id: str
    student_id: str
    student_name: str
    admission_number: str
    class_name: str
    section: str
    kind: str
    recipient_name: str
    recipient_phone: str
    message: str
    status: str
    status_detail: str
    created_at: str


class AlertSettingsOut(BaseModel):
    sms_enabled: bool
    provider: str


def alert_settings() -> AlertSettingsOut:
    settings = get_settings()
    return AlertSettingsOut(sms_enabled=settings.sms_enabled, provider=settings.sms_provider if settings.sms_enabled else "")


async def _context(student_id: str) -> dict | None:
    return await fetch_one(
        """
        SELECT s.id, s.full_name, s.class_id, s.school_id, c.name AS class_name, c.section, sc.name AS school_name,
               g.full_name AS contact_name, g.phone AS contact_phone
        FROM students s
        JOIN classes c ON c.id = s.class_id
        JOIN schools sc ON sc.id = s.school_id
        LEFT JOIN student_guardians g ON g.student_id = s.id AND g.relation = s.primary_contact
        WHERE s.id = %s
        """,
        (student_id,),
    )


async def create_alert(
    *, student_id: str, kind: str, dedupe_key: str, build_message, created_by: str | None
) -> str | None:
    """Sends and logs one alert; returns its id, or None if this event was already alerted.

    build_message(ctx) returns (message text, template variables) for the student context.
    """
    ctx = await _context(student_id)
    if ctx is None:
        return None
    if await fetch_one(
        "SELECT id FROM parent_alerts WHERE school_id = %s AND dedupe_key = %s", (ctx["school_id"], dedupe_key)
    ):
        return None

    message, variables = build_message(ctx)
    phone = (ctx["contact_phone"] or "").strip()
    if phone:
        result = await get_sms_sender().send(phone, message, kind, variables)
        status, detail, message_id = result.status, result.detail, result.message_id
    else:
        status, detail, message_id = "not_sent", "No parent phone number on file.", ""

    alert_id = str(uuid.uuid4())
    try:
        await execute(
            """
            INSERT INTO parent_alerts (id, school_id, student_id, class_id, kind, dedupe_key, recipient_name, recipient_phone,
                                       message, status, status_detail, provider_message_id, created_by, sent_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                alert_id,
                ctx["school_id"],
                student_id,
                ctx["class_id"],
                kind,
                dedupe_key,
                ctx["contact_name"] or "",
                phone,
                message[:500],
                status,
                detail[:300],
                message_id,
                created_by,
                datetime.now(timezone.utc) if status == "sent" else None,
            ),
        )
    except aiomysql.IntegrityError:
        return None  # a concurrent request logged the same event first
    return alert_id


def _absence_message(on: date):
    def build(ctx: dict):
        day = on.strftime("%d %b %Y")
        variables = {"student": ctx["full_name"], "class": f"{ctx['class_name']} {ctx['section']}", "date": day, "school": ctx["school_name"]}
        text = f"Dear Parent, {ctx['full_name']} ({variables['class']}) was absent today, {day}. - {ctx['school_name']}"
        return text, variables

    return build


async def alert_absences(student_ids: list[str], on: date, marked_by: str) -> None:
    """Absence alerts go out only for today's attendance, not for back-filled past days."""
    if on != today_ist() or not student_ids:
        return
    semaphore = asyncio.Semaphore(_SEND_CONCURRENCY)

    async def one(student_id: str) -> None:
        async with semaphore:
            await create_alert(
                student_id=student_id,
                kind="absence",
                dedupe_key=f"absence:{student_id}:{on.isoformat()}",
                build_message=_absence_message(on),
                created_by=marked_by,
            )

    await asyncio.gather(*(one(student_id) for student_id in student_ids))


async def alert_remark(remark: dict, subject_name: str | None, author_id: str) -> str | None:
    def build(ctx: dict):
        day = remark["remark_date"].strftime("%d %b %Y")
        label = REMARK_LABELS[remark["category"]]
        variables = {
            "student": ctx["full_name"],
            "class": f"{ctx['class_name']} {ctx['section']}",
            "date": day,
            "school": ctx["school_name"],
            "category": label,
            "subject": subject_name or "",
            "note": remark["note"],
        }
        subject = f" ({subject_name})" if subject_name else ""
        if remark["category"] in ("missed_exam", "absent_class"):
            text = f"Dear Parent, {ctx['full_name']} {label}{subject} on {day}."
        else:
            text = f"Dear Parent, a {label} note about {ctx['full_name']}{subject}:"
        if remark["note"]:
            text += f" {remark['note']}"
        return f"{text} - {ctx['school_name']}", variables

    return await create_alert(
        student_id=remark["student_id"],
        kind="remark",
        dedupe_key=f"remark:{remark['id']}",
        build_message=build,
        created_by=author_id,
    )


async def list_alerts(user: CurrentUser, *, class_id: str | None, student_id: str | None, limit: int) -> list[AlertOut]:
    where, params = ["a.school_id = %s"], [user.school_id]
    if user.role != "admin":
        # Teachers see alerts for the classes they are class teacher of.
        where.append("c.teacher_id = (SELECT id FROM teachers WHERE user_id = %s AND school_id = %s)")
        params.extend([user.id, user.school_id])
    if class_id:
        where.append("a.class_id = %s")
        params.append(class_id)
    if student_id:
        where.append("a.student_id = %s")
        params.append(student_id)
    rows = await fetch_all(
        f"""
        SELECT a.*, s.full_name AS student_name, s.admission_number, c.name AS class_name, c.section
        FROM parent_alerts a
        JOIN students s ON s.id = a.student_id
        JOIN classes c ON c.id = a.class_id
        WHERE {' AND '.join(where)}
        ORDER BY a.created_at DESC, a.id
        LIMIT %s
        """,
        (*params, limit),
    )
    return [
        AlertOut(
            **{k: row[k] for k in ("id", "student_id", "student_name", "admission_number", "class_name", "section", "kind",
                                   "recipient_name", "recipient_phone", "message", "status", "status_detail")},
            created_at=row["created_at"].isoformat(),
        )
        for row in rows
    ]
