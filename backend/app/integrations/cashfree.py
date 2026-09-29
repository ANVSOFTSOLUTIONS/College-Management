"""Cashfree online payments, using each school's own Cashfree account.

Flow: the backend creates an order with the school's App ID and secret key
and gets a payment_session_id; the browser opens Cashfree Checkout with it.
Afterwards the backend asks Cashfree for the order (server to server) and
counts the payment only if Cashfree says it is PAID for the right amount, so
nothing the browser sends is trusted. A webhook does the same check for
payments whose browser tab closed early.

Kept off until a school connects its account (school_payment_settings.enabled).
API version 2023-08-01: https://docs.cashfree.com/reference/pg-new-apis-endpoint
"""

import asyncio
import base64
import hashlib
import hmac
import json
import urllib.error
import urllib.request
from decimal import Decimal

API_VERSION = "2023-08-01"
BASE_URLS = {"production": "https://api.cashfree.com/pg", "sandbox": "https://sandbox.cashfree.com/pg"}


class CashfreeError(Exception):
    pass


def _request(environment: str, app_id: str, secret_key: str, method: str, path: str, body: dict | None = None) -> dict | list:
    request = urllib.request.Request(
        BASE_URLS[environment] + path,
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={
            "x-client-id": app_id,
            "x-client-secret": secret_key,
            "x-api-version": API_VERSION,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        try:
            message = json.loads(exc.read()).get("message", "")
        except (ValueError, AttributeError):
            message = ""
        raise CashfreeError(f"Cashfree refused the request ({exc.code}){': ' + message if message else ''}.") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise CashfreeError("Could not reach Cashfree.") from exc


async def create_order(
    environment: str, app_id: str, secret_key: str, *, order_id: str, amount: Decimal, customer_id: str,
    customer_phone: str, customer_name: str, note: str,
) -> dict:
    body = {
        "order_id": order_id,
        "order_amount": float(amount),
        "order_currency": "INR",
        "customer_details": {"customer_id": customer_id, "customer_phone": customer_phone, "customer_name": customer_name[:100]},
        "order_note": note[:200],
    }
    order = await asyncio.to_thread(_request, environment, app_id, secret_key, "POST", "/orders", body)
    if not isinstance(order, dict) or not order.get("payment_session_id"):
        raise CashfreeError("Cashfree did not return a payment session.")
    return order


async def fetch_order(environment: str, app_id: str, secret_key: str, order_id: str) -> dict:
    return await asyncio.to_thread(_request, environment, app_id, secret_key, "GET", f"/orders/{order_id}")


async def successful_payment_id(environment: str, app_id: str, secret_key: str, order_id: str) -> str:
    """Cashfree's id for the order's successful payment ("" if none is listed)."""
    payments = await asyncio.to_thread(_request, environment, app_id, secret_key, "GET", f"/orders/{order_id}/payments")
    for payment in payments if isinstance(payments, list) else []:
        if payment.get("payment_status") == "SUCCESS":
            return str(payment.get("cf_payment_id", ""))
    return ""


def verify_webhook_signature(raw_body: bytes, timestamp: str, signature: str, secret_key: str) -> bool:
    """Cashfree signs base64(HMAC-SHA256(timestamp + raw body)) with the merchant's secret key."""
    expected = base64.b64encode(hmac.new(secret_key.encode(), timestamp.encode() + raw_body, hashlib.sha256).digest()).decode()
    return hmac.compare_digest(expected, signature or "")
