"""Phone/browser push notifications for the in-app notifications.

Every bell notification is also pushed to the user's subscribed devices, so it
shows on the phone even when the app is closed. Sending happens in the
background and never slows down or breaks the request that caused it.
"""

import asyncio
import hashlib
import logging
import uuid

from fastapi import status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser
from app.core.errors import AppError
from app.db.helpers import execute, fetch_all, fetch_one

logger = logging.getLogger(__name__)
SUBJECT = "mailto:support@anvsoftsolutions.com"
_background: set[asyncio.Task] = set()
_keys: tuple[str, str] | None = None


class SubscriptionKeys(BaseModel):
    p256dh: str = Field(min_length=20, max_length=200)
    auth: str = Field(min_length=8, max_length=100)


class SubscribeIn(BaseModel):
    endpoint: str = Field(min_length=10, max_length=700, pattern=r"^https://")
    keys: SubscriptionKeys


class UnsubscribeIn(BaseModel):
    endpoint: str = Field(min_length=10, max_length=700)


def _webpush():
    # Imported on use, so the API still starts if the crypto package is missing on a server.
    from app.core import webpush

    return webpush


async def vapid_keys() -> tuple[str, str]:
    """The platform's VAPID key pair, created once and kept in platform_settings."""
    global _keys
    if _keys:
        return _keys
    row = await fetch_one("SELECT vapid_public_key, vapid_private_key FROM platform_settings WHERE id = 1")
    if not row or not row["vapid_public_key"]:
        public, private = _webpush().generate_vapid_keys()
        await execute(
            """
            INSERT INTO platform_settings (id, vapid_public_key, vapid_private_key) VALUES (1, %s, %s)
            ON DUPLICATE KEY UPDATE vapid_public_key = IF(vapid_public_key = '', VALUES(vapid_public_key), vapid_public_key),
                                    vapid_private_key = IF(vapid_private_key = '', VALUES(vapid_private_key), vapid_private_key)
            """,
            (public, private),
        )
        row = await fetch_one("SELECT vapid_public_key, vapid_private_key FROM platform_settings WHERE id = 1")
    _keys = (row["vapid_public_key"], row["vapid_private_key"])
    return _keys


def _hash(endpoint: str) -> str:
    return hashlib.sha256(endpoint.encode()).hexdigest()


async def subscribe(user: CurrentUser, payload: SubscribeIn, user_agent: str) -> None:
    try:
        _webpush().b64url_decode(payload.keys.p256dh)
        _webpush().b64url_decode(payload.keys.auth)
    except ValueError as exc:
        raise AppError(status.HTTP_400_BAD_REQUEST, "invalid_subscription", "That push subscription isn't valid.") from exc
    # One device, one row: re-subscribing (or another user on the same phone) takes it over.
    await execute(
        """
        INSERT INTO push_subscriptions (id, user_id, endpoint, endpoint_hash, p256dh, auth, user_agent) VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE user_id = VALUES(user_id), p256dh = VALUES(p256dh), auth = VALUES(auth), user_agent = VALUES(user_agent)
        """,
        (str(uuid.uuid4()), user.id, payload.endpoint, _hash(payload.endpoint), payload.keys.p256dh, payload.keys.auth, user_agent[:200]),
    )


async def unsubscribe(user: CurrentUser, endpoint: str) -> None:
    await execute("DELETE FROM push_subscriptions WHERE endpoint_hash = %s AND user_id = %s", (_hash(endpoint), user.id))


async def device_count(user: CurrentUser) -> int:
    row = await fetch_one("SELECT COUNT(*) AS n FROM push_subscriptions WHERE user_id = %s", (user.id,))
    return row["n"]


async def _deliver(user_ids: list[str], message: dict) -> None:
    try:
        placeholders = ", ".join(["%s"] * len(user_ids))
        subscriptions = await fetch_all(f"SELECT * FROM push_subscriptions WHERE user_id IN ({placeholders})", tuple(user_ids))
        if not subscriptions:
            return
        webpush = _webpush()
        public, private = await vapid_keys()

        async def one(sub: dict) -> None:
            try:
                await asyncio.to_thread(
                    webpush.send, sub["endpoint"], sub["p256dh"], sub["auth"], message,
                    public_key=public, private_key=private, subject=SUBJECT,
                )
            except webpush.SubscriptionGone:
                await execute("DELETE FROM push_subscriptions WHERE id = %s", (sub["id"],))
            except Exception:  # noqa: BLE001 - a bad endpoint must never break the others
                logger.warning("Push to a subscription failed", exc_info=True)

        await asyncio.gather(*(one(s) for s in subscriptions))
    except Exception:  # noqa: BLE001 - background work: log, never raise
        logger.warning("Push delivery failed", exc_info=True)


def push_in_background(user_ids: list[str], *, title: str, body: str, link: str) -> None:
    """Fire-and-forget: the caller's request finishes without waiting for push services."""
    if not user_ids:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    message = {"title": title, "body": body, "link": link}
    task = loop.create_task(_deliver(user_ids, message))
    _background.add(task)
    task.add_done_callback(_background.discard)
