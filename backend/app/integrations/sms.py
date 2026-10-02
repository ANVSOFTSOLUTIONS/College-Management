"""Sending SMS to parents.

Everything goes through `get_sms_sender()`. With SMS_ENABLED=false (the
default) it returns a sender that sends nothing and reports "not_sent", so
the rest of the app records alerts the same way whether SMS is on or off.

MSG91 is the one real provider. Indian SMS must use DLT-approved templates,
so each alert kind has its own MSG91 flow template, and the message text the
app builds is kept only for our own log. Template variables sent:
  absence: student, class, date, school
  remark:  student, class, date, school, category, subject, note
  fee:     student, class, date, school, amount, due_date
  result:  student, class, date, school, exam, result
WhatsApp (also MSG91) uses approved WhatsApp templates whose body variables
{{1}}, {{2}} ... are filled in the order listed in WHATSAPP_VARIABLES.
Name the ##variables## in the MSG91 templates to match. This provider has not
been run against a live MSG91 account yet — test it with one number first.
"""

import asyncio
import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass

from app.core.config import get_settings
from app.core.phone import normalize_indian_mobile  # noqa: F401 (re-exported for callers)

logger = logging.getLogger(__name__)

MSG91_FLOW_URL = "https://control.msg91.com/api/v5/flow/"
MSG91_WHATSAPP_URL = "https://api.msg91.com/api/v5/whatsapp/whatsapp-outbound-message/bulk/"
WHATSAPP_VARIABLES = {
    "absence": ["student", "class", "date", "school"],
    "remark": ["student", "category", "note", "school"],
    "fee": ["student", "amount", "due_date", "school"],
    "result": ["student", "exam", "result", "school"],
}


@dataclass(frozen=True)
class SmsResult:
    status: str  # "sent", "failed", or "not_sent"
    detail: str = ""
    message_id: str = ""


class DisabledSmsSender:
    async def send(self, phone: str, message: str, kind: str, variables: dict[str, str]) -> SmsResult:
        return SmsResult("not_sent", "SMS sending is turned off.")


class Msg91SmsSender:
    def __init__(self, auth_key: str, templates: dict[str, str]):
        self.auth_key = auth_key
        self.templates = templates

    def _post(self, body: dict) -> dict:
        request = urllib.request.Request(
            MSG91_FLOW_URL,
            data=json.dumps(body).encode(),
            method="POST",
            headers={"authkey": self.auth_key, "Content-Type": "application/json", "Accept": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read() or b"{}")

    async def send(self, phone: str, message: str, kind: str, variables: dict[str, str]) -> SmsResult:
        template_id = self.templates.get(kind)
        if not self.auth_key or not template_id:
            return SmsResult("not_sent", f"No MSG91 template configured for {kind} alerts.")
        mobile = normalize_indian_mobile(phone)
        if mobile is None:
            return SmsResult("failed", "Not a valid Indian mobile number.")
        body = {"template_id": template_id, "short_url": "0", "recipients": [{"mobiles": mobile, **variables}]}
        try:
            reply = await asyncio.to_thread(self._post, body)
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            logger.warning("MSG91 send failed: %s", exc)
            return SmsResult("failed", f"Could not reach MSG91: {exc}"[:300])
        if reply.get("type") == "success":
            return SmsResult("sent", "", str(reply.get("message", ""))[:100])
        return SmsResult("failed", f"MSG91: {reply.get('message', reply)}"[:300])


def get_sms_sender():
    settings = get_settings()
    if not settings.sms_enabled:
        return DisabledSmsSender()
    if settings.sms_provider == "msg91":
        return Msg91SmsSender(
            settings.sms_msg91_auth_key,
            {
                "absence": settings.sms_msg91_template_absence,
                "remark": settings.sms_msg91_template_remark,
                "fee": settings.sms_msg91_template_fee,
                "result": settings.sms_msg91_template_result,
            },
        )
    logger.error("Unknown SMS_PROVIDER %r; SMS disabled.", settings.sms_provider)
    return DisabledSmsSender()


class Msg91WhatsAppSender:
    def __init__(self, auth_key: str, number: str, language: str, templates: dict[str, str]):
        self.auth_key = auth_key
        self.number = number
        self.language = language
        self.templates = templates

    def _post(self, body: dict) -> dict:
        request = urllib.request.Request(
            MSG91_WHATSAPP_URL,
            data=json.dumps(body).encode(),
            method="POST",
            headers={"authkey": self.auth_key, "Content-Type": "application/json", "Accept": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read() or b"{}")

    def body(self, mobile: str, kind: str, variables: dict[str, str]) -> dict:
        components = {f"body_{i}": {"type": "text", "value": str(variables.get(name, ""))[:200]}
                      for i, name in enumerate(WHATSAPP_VARIABLES.get(kind, []), start=1)}
        return {
            "integrated_number": self.number,
            "content_type": "template",
            "payload": {
                "messaging_product": "whatsapp",
                "type": "template",
                "template": {
                    "name": self.templates[kind],
                    "language": {"code": self.language, "policy": "deterministic"},
                    "to_and_components": [{"to": [mobile], "components": components}],
                },
            },
        }

    async def send(self, phone: str, message: str, kind: str, variables: dict[str, str]) -> SmsResult:
        if not self.auth_key or not self.number or not self.templates.get(kind):
            return SmsResult("not_sent", f"No WhatsApp template configured for {kind} alerts.")
        mobile = normalize_indian_mobile(phone)
        if mobile is None:
            return SmsResult("failed", "Not a valid Indian mobile number.")
        try:
            reply = await asyncio.to_thread(self._post, self.body(mobile, kind, variables))
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            logger.warning("MSG91 WhatsApp send failed: %s", exc)
            return SmsResult("failed", f"Could not reach MSG91 WhatsApp: {exc}"[:300])
        if reply.get("status") == "success" or reply.get("type") == "success":
            return SmsResult("sent", "", str(reply.get("request_id") or reply.get("message", ""))[:100])
        return SmsResult("failed", f"MSG91 WhatsApp: {reply.get('message', reply)}"[:300])


def get_whatsapp_sender():
    settings = get_settings()
    if not settings.whatsapp_enabled:
        return None
    return Msg91WhatsAppSender(
        settings.sms_msg91_auth_key,
        settings.whatsapp_msg91_number,
        settings.whatsapp_language,
        {
            "absence": settings.whatsapp_template_absence,
            "remark": settings.whatsapp_template_remark,
            "fee": settings.whatsapp_template_fee,
            "result": settings.whatsapp_template_result,
        },
    )
