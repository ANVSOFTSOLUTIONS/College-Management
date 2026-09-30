"""Outgoing email over SMTP (e.g. the cPanel mailbox of anvsoftsolutions.com).

Off until SMTP_HOST is set; while off, nothing is sent and a line is logged.
Sending runs in a worker thread so a slow mail server never blocks a request.
"""

import asyncio
import logging
import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _send(to: list[str], subject: str, body: str, reply_to: str | None) -> None:
    settings = get_settings()
    message = EmailMessage()
    message["From"] = settings.smtp_from or settings.smtp_user
    message["To"] = ", ".join(to)
    message["Subject"] = subject
    if reply_to:
        message["Reply-To"] = reply_to
    message.set_content(body)

    context = ssl.create_default_context()
    if settings.smtp_use_ssl:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=context, timeout=20) as server:
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(message)
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
            server.starttls(context=context)
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(message)


async def send_email(to: list[str], subject: str, body: str, reply_to: str | None = None) -> bool:
    """Sends one email; returns False (and logs) when email is off or sending fails."""
    settings = get_settings()
    recipients = [address for address in to if address]
    if not settings.smtp_host or not recipients:
        logger.info("Email not sent (SMTP not configured): %s", subject)
        return False
    try:
        await asyncio.to_thread(_send, recipients, subject, body, reply_to)
        return True
    except (smtplib.SMTPException, OSError):
        logger.exception("Couldn't send email: %s", subject)
        return False
