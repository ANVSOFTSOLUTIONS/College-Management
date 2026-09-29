"""PhonePe online payments (Standard Checkout v2), using each school's own PhonePe account.

Flow: the backend gets an OAuth token with the school's Client ID, Client
Version and Client Secret, creates a payment and gets a checkout URL; the
browser opens PhonePe's checkout with it. Afterwards the backend asks
PhonePe for the order status (server to server) and counts the payment only
if PhonePe says it is COMPLETED for the right amount.
https://developer.phonepe.com/v1/reference/standard-checkout-overview
"""

import asyncio
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal

BASE_URLS = {
    "production": {"auth": "https://api.phonepe.com/apis/identity-manager", "pg": "https://api.phonepe.com/apis/pg"},
    "sandbox": {"auth": "https://api-preprod.phonepe.com/apis/pg-sandbox", "pg": "https://api-preprod.phonepe.com/apis/pg-sandbox"},
}

_tokens: dict[tuple[str, str], tuple[str, float]] = {}  # (environment, client_id) -> (token, expires_at)


class PhonePeError(Exception):
    pass


def _send(request: urllib.request.Request) -> dict:
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        try:
            message = json.loads(exc.read()).get("message", "")
        except (ValueError, AttributeError):
            message = ""
        raise PhonePeError(f"PhonePe refused the request ({exc.code}){': ' + message if message else ''}.") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise PhonePeError("Could not reach PhonePe.") from exc


def _token(environment: str, client_id: str, client_version: str, client_secret: str) -> str:
    cached = _tokens.get((environment, client_id))
    if cached and cached[1] > time.time() + 60:
        return cached[0]
    body = urllib.parse.urlencode({
        "client_id": client_id, "client_version": client_version, "client_secret": client_secret, "grant_type": "client_credentials",
    }).encode()
    request = urllib.request.Request(
        BASE_URLS[environment]["auth"] + "/v1/oauth/token", data=body, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
    )
    reply = _send(request)
    token = reply.get("access_token")
    if not token:
        raise PhonePeError("PhonePe did not accept the Client ID / secret.")
    _tokens[(environment, client_id)] = (token, float(reply.get("expires_at") or time.time() + 600))
    return token


def _request(environment: str, client_id: str, client_version: str, client_secret: str, method: str, path: str, body: dict | None = None) -> dict:
    token = _token(environment, client_id, client_version, client_secret)
    request = urllib.request.Request(
        BASE_URLS[environment]["pg"] + path,
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={"Authorization": f"O-Bearer {token}", "Content-Type": "application/json", "Accept": "application/json"},
    )
    return _send(request)


async def create_order(
    environment: str, client_id: str, client_version: str, client_secret: str, *, order_id: str, amount: Decimal, note: str, redirect_url: str,
) -> dict:
    body = {
        "merchantOrderId": order_id,
        "amount": int((Decimal(amount) * 100).to_integral_value()),
        "expireAfter": 1800,
        "paymentFlow": {"type": "PG_CHECKOUT", "message": note[:100], "merchantUrls": {"redirectUrl": redirect_url}},
    }
    order = await asyncio.to_thread(_request, environment, client_id, client_version, client_secret, "POST", "/checkout/v2/pay", body)
    if not order.get("redirectUrl"):
        raise PhonePeError("PhonePe did not return a checkout page.")
    return order


async def order_status(environment: str, client_id: str, client_version: str, client_secret: str, order_id: str) -> dict:
    return await asyncio.to_thread(
        _request, environment, client_id, client_version, client_secret, "GET", f"/checkout/v2/order/{urllib.parse.quote(order_id)}/status",
    )
