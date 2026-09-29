"""Razorpay online payments, using each school's own Razorpay account.

Flow: the backend creates an order with the school's Key ID and secret and
the browser opens Razorpay Checkout with it. Afterwards the backend asks
Razorpay for the order (server to server) and counts the payment only if
Razorpay says it is paid for the right amount. Razorpay has no separate
test server: test keys (rzp_test_…) are test mode.
Orders API: https://razorpay.com/docs/api/orders/
"""

import asyncio
import base64
import json
import urllib.error
import urllib.request
from decimal import Decimal

BASE_URL = "https://api.razorpay.com/v1"


class RazorpayError(Exception):
    pass


def _request(key_id: str, key_secret: str, method: str, path: str, body: dict | None = None) -> dict:
    auth = base64.b64encode(f"{key_id}:{key_secret}".encode()).decode()
    request = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        try:
            message = json.loads(exc.read()).get("error", {}).get("description", "")
        except (ValueError, AttributeError):
            message = ""
        raise RazorpayError(f"Razorpay refused the request ({exc.code}){': ' + message if message else ''}.") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RazorpayError("Could not reach Razorpay.") from exc


def to_paise(amount: Decimal) -> int:
    return int((Decimal(amount) * 100).to_integral_value())


async def create_order(key_id: str, key_secret: str, *, receipt: str, amount: Decimal, note: str) -> dict:
    body = {"amount": to_paise(amount), "currency": "INR", "receipt": receipt[:40], "notes": {"order_id": receipt, "for": note[:250]}}
    order = await asyncio.to_thread(_request, key_id, key_secret, "POST", "/orders", body)
    if not order.get("id"):
        raise RazorpayError("Razorpay did not return an order.")
    return order


async def fetch_order(key_id: str, key_secret: str, order_id: str) -> dict:
    return await asyncio.to_thread(_request, key_id, key_secret, "GET", f"/orders/{order_id}")


async def captured_payment_id(key_id: str, key_secret: str, order_id: str) -> str:
    """Razorpay's id for the order's captured payment ("" if none is listed)."""
    payments = await asyncio.to_thread(_request, key_id, key_secret, "GET", f"/orders/{order_id}/payments")
    for payment in payments.get("items", []):
        if payment.get("status") == "captured":
            return str(payment.get("id", ""))
    return ""
