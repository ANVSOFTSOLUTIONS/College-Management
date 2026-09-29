"""In-app notifications (the bell). Other modules call `notify`."""

import uuid

from pydantic import BaseModel

from app.api.deps import CurrentUser
from app.db.database import db
from app.db.helpers import execute, fetch_all, fetch_one
from app.modules.push import service as push


class NotificationOut(BaseModel):
    id: str
    title: str
    body: str
    link: str
    read: bool
    created_at: str


class NotificationList(BaseModel):
    unread: int
    items: list[NotificationOut]


async def notify(user_ids: list[str], *, school_id: str | None, title: str, body: str = "", link: str = "") -> int:
    user_ids = list(dict.fromkeys(uid for uid in user_ids if uid))
    if not user_ids:
        return 0
    async with db.pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.executemany(
                "INSERT INTO notifications (id, school_id, user_id, title, body, link) VALUES (%s, %s, %s, %s, %s, %s)",
                [(str(uuid.uuid4()), school_id, uid, title[:200], body[:500], link[:50]) for uid in user_ids],
            )
    # The same message goes to the users' phones/browsers that allowed push notifications.
    push.push_in_background(user_ids, title=title[:200], body=body[:300], link=link[:50])
    return len(user_ids)


async def admin_user_ids(school_id: str) -> list[str]:
    rows = await fetch_all("SELECT id FROM users WHERE school_id = %s AND role = 'admin' AND status = 'active'", (school_id,))
    return [r["id"] for r in rows]


async def list_notifications(user: CurrentUser, limit: int = 50) -> NotificationList:
    rows = await fetch_all(
        "SELECT * FROM notifications WHERE user_id = %s ORDER BY created_at DESC, id LIMIT %s", (user.id, limit)
    )
    unread = await fetch_one("SELECT COUNT(*) AS n FROM notifications WHERE user_id = %s AND read_at IS NULL", (user.id,))
    return NotificationList(
        unread=unread["n"],
        items=[
            NotificationOut(
                id=r["id"], title=r["title"], body=r["body"], link=r["link"], read=r["read_at"] is not None,
                created_at=r["created_at"].isoformat(),
            )
            for r in rows
        ],
    )


async def mark_read(user: CurrentUser, notification_id: str | None) -> None:
    if notification_id:
        await execute(
            "UPDATE notifications SET read_at = CURRENT_TIMESTAMP WHERE id = %s AND user_id = %s AND read_at IS NULL",
            (notification_id, user.id),
        )
    else:
        await execute("UPDATE notifications SET read_at = CURRENT_TIMESTAMP WHERE user_id = %s AND read_at IS NULL", (user.id,))
