"""Notice board.

- Admins post to the whole school or chosen classes, for staff, students
  and/or parents; they can pin a notice and set when it stops showing.
- Teachers post to classes they teach, for that class's students and parents.
- Everyone the notice is for gets a bell notification when it is posted.
"""

import uuid
from datetime import date

from fastapi import UploadFile, status
from pydantic import BaseModel, Field, field_validator, model_validator

from app.api.deps import CurrentUser
from app.core.errors import AppError
from app.db.database import db
from app.db.helpers import execute, fetch_all
from app.modules.alerts.service import today_ist
from app.modules.board import audience
from app.modules.notifications import service as notifications
from app.modules.students.files import delete_private_file


class NoticeIn(BaseModel):
    title: str = Field(min_length=3, max_length=150)
    body: str = Field(min_length=1, max_length=5000)
    class_ids: list[str] = Field(default_factory=list, max_length=100)  # empty: whole school
    for_staff: bool = False
    for_students: bool = False
    for_parents: bool = True
    is_pinned: bool = False
    expires_on: date | None = None

    @field_validator("title", "body", mode="before")
    @classmethod
    def _strip(cls, value):
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def _someone(self):
        if not (self.for_staff or self.for_students or self.for_parents):
            raise ValueError("Choose who the notice is for: faculty, students or parents.")
        return self


class NoticeOut(BaseModel):
    id: str
    title: str
    body: str
    classes: list[str]  # "Grade 5 - A"; empty for the whole school
    class_ids: list[str]
    for_staff: bool
    for_students: bool
    for_parents: bool
    is_pinned: bool
    expires_on: date | None
    is_expired: bool
    attachment_name: str | None
    posted_by_name: str | None
    created_at: str
    can_edit: bool


async def _rows(where: str, params: tuple) -> list[dict]:
    return await fetch_all(
        f"""
        SELECT n.*, u.full_name AS posted_by_name FROM notices n LEFT JOIN users u ON u.id = n.posted_by
        WHERE {where} ORDER BY n.is_pinned DESC, n.created_at DESC, n.id LIMIT 200
        """,
        params,
    )


async def _classes_of(notice_ids: list[str]) -> dict[str, list[dict]]:
    if not notice_ids:
        return {}
    placeholders = ", ".join(["%s"] * len(notice_ids))
    result: dict[str, list[dict]] = {}
    for r in await fetch_all(
        f"""
        SELECT nc.notice_id, c.id, c.name, c.section FROM notice_classes nc JOIN classes c ON c.id = nc.class_id
        WHERE nc.notice_id IN ({placeholders}) ORDER BY c.name, c.section
        """,
        tuple(notice_ids),
    ):
        result.setdefault(r["notice_id"], []).append(r)
    return result


def _out(row: dict, classes: list[dict], user: CurrentUser) -> NoticeOut:
    return NoticeOut(
        id=row["id"],
        title=row["title"],
        body=row["body"],
        classes=[f"{c['name']} - {c['section']}" for c in classes],
        class_ids=[c["id"] for c in classes],
        for_staff=bool(row["for_staff"]),
        for_students=bool(row["for_students"]),
        for_parents=bool(row["for_parents"]),
        is_pinned=bool(row["is_pinned"]),
        expires_on=row["expires_on"],
        is_expired=row["expires_on"] is not None and row["expires_on"] < today_ist(),
        attachment_name=row["attachment_name"],
        posted_by_name=row["posted_by_name"],
        created_at=row["created_at"].isoformat(),
        can_edit=user.role == "admin" or row["posted_by"] == user.id,
    )


def _visible(user: CurrentUser, row: dict, class_ids: set[str], my_classes: set[str]) -> bool:
    """Whether a notice (with its target classes) is for this user."""
    if user.role in ("parent", "student"):
        # Parents have no college of their own; a whole-college notice needs a child in that college.
        # Students see notices for students, parents those for parents.
        audience_flag = row["for_students"] if user.role == "student" else row["for_parents"]
        return bool(audience_flag) and (bool(class_ids & my_classes) if class_ids else row["school_id"] in _schools_of(my_classes))
    if row["school_id"] != user.school_id:
        return False
    if user.role == "admin" or row["posted_by"] == user.id:
        return True
    in_scope = not class_ids or bool(class_ids & my_classes)
    if user.role == "teacher":
        # Staff notices, plus anything posted to a class they teach.
        return (row["for_staff"] and in_scope) or bool(class_ids & my_classes)
    return False


class _ParentClasses(set):
    """A parent's children's class ids, remembering which schools they are in."""

    def __init__(self, children: list[dict]):
        super().__init__(c["class_id"] for c in children)
        self.school_ids = {c["school_id"] for c in children}


def _schools_of(my_classes: set[str]) -> set[str]:
    return getattr(my_classes, "school_ids", set())


async def _my_classes(user: CurrentUser) -> set[str]:
    if user.role == "teacher":
        return await audience.teaching_class_ids(user)
    if user.role in ("parent", "student"):
        return _ParentClasses(await audience.children(user))
    return set()


async def list_notices(user: CurrentUser, *, include_expired: bool) -> list[NoticeOut]:
    my_classes = await _my_classes(user)
    school_ids = sorted(_schools_of(my_classes)) if user.role in ("parent", "student") else [user.school_id]
    if not school_ids:
        return []
    where, params = "n.school_id IN ({})".format(", ".join(["%s"] * len(school_ids))), list(school_ids)
    if not (include_expired and user.role in ("admin", "teacher")):
        where += " AND (n.expires_on IS NULL OR n.expires_on >= %s)"
        params.append(today_ist())
    rows = await _rows(where, tuple(params))
    classes = await _classes_of([r["id"] for r in rows])
    return [
        _out(r, classes.get(r["id"], []), user)
        for r in rows
        if _visible(user, r, {c["id"] for c in classes.get(r["id"], [])}, my_classes)
    ]


async def _get_row(user: CurrentUser, notice_id: str) -> tuple[dict, list[dict]]:
    rows = await _rows("n.id = %s", (notice_id,))
    if not rows:
        raise AppError(status.HTTP_404_NOT_FOUND, "notice_not_found", "Notice not found.")
    classes = (await _classes_of([notice_id])).get(notice_id, [])
    if not _visible(user, rows[0], {c["id"] for c in classes}, await _my_classes(user)):
        raise AppError(status.HTTP_404_NOT_FOUND, "notice_not_found", "Notice not found.")
    return rows[0], classes


async def _get(user: CurrentUser, notice_id: str) -> NoticeOut:
    row, classes = await _get_row(user, notice_id)
    return _out(row, classes, user)


async def _check_payload(user: CurrentUser, payload: NoticeIn) -> list[str]:
    class_ids = await audience.school_class_ids(user.school_id, payload.class_ids)
    if user.role == "teacher":
        if not class_ids:
            raise AppError(status.HTTP_403_FORBIDDEN, "forbidden", "Teachers post notices to the classes they teach.")
        if not set(class_ids) <= await audience.teaching_class_ids(user):
            raise AppError(status.HTTP_403_FORBIDDEN, "forbidden", "You can only post to classes you teach.")
        if payload.for_staff or payload.is_pinned:
            raise AppError(status.HTTP_403_FORBIDDEN, "forbidden", "Only the admin can post staff notices or pin a notice.")
    if payload.expires_on and payload.expires_on < today_ist():
        raise AppError(status.HTTP_400_BAD_REQUEST, "invalid_expiry", "The show-until date is already past.")
    return class_ids


async def _save_classes(cur, notice_id: str, class_ids: list[str]) -> None:
    await cur.execute("DELETE FROM notice_classes WHERE notice_id = %s", (notice_id,))
    if class_ids:
        await cur.executemany("INSERT INTO notice_classes (notice_id, class_id) VALUES (%s, %s)", [(notice_id, c) for c in class_ids])


async def create_notice(user: CurrentUser, payload: NoticeIn) -> NoticeOut:
    class_ids = await _check_payload(user, payload)
    notice_id = str(uuid.uuid4())
    async with db.pool.acquire() as conn:
        await conn.begin()
        try:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO notices (id, school_id, title, body, for_staff, for_students, for_parents, is_pinned, expires_on, posted_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (notice_id, user.school_id, payload.title, payload.body, payload.for_staff, payload.for_students,
                     payload.for_parents, payload.is_pinned, payload.expires_on, user.id),
                )
                await _save_classes(cur, notice_id, class_ids)
        except Exception:
            await conn.rollback()
            raise
        await conn.commit()

    recipients = await audience.recipients(
        user.school_id, class_ids, staff=payload.for_staff, parents=payload.for_parents, students=payload.for_students
    )
    await notifications.notify(
        [r for r in recipients if r != user.id],
        school_id=user.school_id,
        title=f"Notice: {payload.title}",
        body=payload.body[:300],
        link="notices",
    )
    return await _get(user, notice_id)


async def _editable(user: CurrentUser, notice_id: str) -> dict:
    row, _ = await _get_row(user, notice_id)
    if not (user.role == "admin" or row["posted_by"] == user.id):
        raise AppError(status.HTTP_403_FORBIDDEN, "forbidden", "Only the person who posted this notice or the admin can change it.")
    return row


async def update_notice(user: CurrentUser, notice_id: str, payload: NoticeIn) -> NoticeOut:
    await _editable(user, notice_id)
    class_ids = await _check_payload(user, payload)
    async with db.pool.acquire() as conn:
        await conn.begin()
        try:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    UPDATE notices SET title = %s, body = %s, for_staff = %s, for_students = %s, for_parents = %s,
                           is_pinned = %s, expires_on = %s WHERE id = %s
                    """,
                    (payload.title, payload.body, payload.for_staff, payload.for_students, payload.for_parents,
                     payload.is_pinned, payload.expires_on, notice_id),
                )
                await _save_classes(cur, notice_id, class_ids)
        except Exception:
            await conn.rollback()
            raise
        await conn.commit()
    return await _get(user, notice_id)


async def delete_notice(user: CurrentUser, notice_id: str) -> None:
    row = await _editable(user, notice_id)
    await execute("DELETE FROM notices WHERE id = %s", (notice_id,))
    delete_private_file(row["attachment_path"])


async def set_attachment(user: CurrentUser, notice_id: str, file: UploadFile | None) -> NoticeOut:
    row = await _editable(user, notice_id)
    path = name = content_type = None
    if file is not None:
        path, name, content_type = await audience.save_attachment(user.school_id, "notices", file)
    await execute(
        "UPDATE notices SET attachment_path = %s, attachment_name = %s, attachment_type = %s WHERE id = %s",
        (path, name, content_type, notice_id),
    )
    delete_private_file(row["attachment_path"])
    return await _get(user, notice_id)


async def attachment_row(user: CurrentUser, notice_id: str) -> dict:
    row, _ = await _get_row(user, notice_id)
    return row

