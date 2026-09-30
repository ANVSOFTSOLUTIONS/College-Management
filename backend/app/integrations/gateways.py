"""One way to take an online payment, whichever gateway the school uses.

A school connects one gateway (Cashfree, Razorpay or PhonePe) with its own
keys, from the ones the super admin allows it. "demo" is a pretend gateway for
showing the product: no keys, its payment page is in the app, no money moves. The fee and admission code
calls create_order and check_order here; each gateway's own module talks to
its API. Nothing the browser reports is trusted: a payment counts only when
check_order hears from the gateway itself that it is paid.
"""

from dataclasses import dataclass
from decimal import Decimal

from app.db.helpers import execute, fetch_one
from app.integrations import cashfree, phonepe, razorpay

PROVIDERS = {"cashfree": "Cashfree", "razorpay": "Razorpay", "phonepe": "PhonePe", "demo": "Demo gateway (test)"}
NEEDS_KEYS = {"cashfree", "razorpay", "phonepe"}


class GatewayError(Exception):
    pass


@dataclass
class Checkout:
    """What the browser needs to open the gateway's checkout."""

    provider: str
    environment: str
    gateway_ref: str  # the gateway's id for the order (Razorpay makes its own)
    payment_session_id: str = ""  # Cashfree
    key_id: str = ""  # Razorpay (its public Key ID)
    checkout_url: str = ""  # PhonePe


@dataclass
class OrderState:
    status: str  # "paid", "failed" or "pending"
    amount: Decimal | None  # rupees the gateway says the order is for
    payment_ref: str = ""  # the gateway's id for the successful payment


def label(provider: str) -> str:
    return PROVIDERS.get(provider, provider)


async def create_order(
    settings: dict, secret: str, *, order_id: str, amount: Decimal, customer_id: str, customer_phone: str,
    customer_name: str, note: str, redirect_url: str,
) -> Checkout:
    provider, environment, key_id = settings["provider"], settings["environment"], settings["key_id"]
    try:
        if provider == "cashfree":
            order = await cashfree.create_order(
                environment, key_id, secret, order_id=order_id, amount=amount, customer_id=customer_id,
                customer_phone=customer_phone, customer_name=customer_name, note=note,
            )
            return Checkout(provider, environment, order_id, payment_session_id=order["payment_session_id"])
        if provider == "razorpay":
            order = await razorpay.create_order(key_id, secret, receipt=order_id, amount=amount, note=note)
            return Checkout(provider, environment, order["id"], key_id=key_id)
        if provider == "phonepe":
            order = await phonepe.create_order(
                environment, key_id, settings.get("client_version") or "1", secret, order_id=order_id, amount=amount, note=note,
                redirect_url=redirect_url,
            )
            return Checkout(provider, environment, order_id, checkout_url=order["redirectUrl"])
        if provider == "demo":
            await execute("INSERT INTO demo_payment_orders (ref, amount) VALUES (%s, %s)", (order_id, amount))
            return Checkout(provider, "sandbox", order_id)
    except (cashfree.CashfreeError, razorpay.RazorpayError, phonepe.PhonePeError) as exc:
        raise GatewayError(str(exc)) from exc
    raise GatewayError(f"Unknown payment gateway {provider}.")


async def check_order(settings: dict, secret: str, gateway_ref: str) -> OrderState:
    provider, environment, key_id = settings["provider"], settings["environment"], settings["key_id"]
    try:
        if provider == "cashfree":
            order = await cashfree.fetch_order(environment, key_id, secret, gateway_ref)
            order_status = order.get("order_status")
            if order_status in ("EXPIRED", "TERMINATED", "TERMINATION_REQUESTED"):
                return OrderState("failed", None)
            if order_status != "PAID":
                return OrderState("pending", None)
            payment_ref = await cashfree.successful_payment_id(environment, key_id, secret, gateway_ref)
            return OrderState("paid", Decimal(str(order.get("order_amount"))), payment_ref)
        if provider == "razorpay":
            order = await razorpay.fetch_order(key_id, secret, gateway_ref)
            if order.get("status") != "paid":
                return OrderState("pending", None)
            payment_ref = await razorpay.captured_payment_id(key_id, secret, gateway_ref)
            return OrderState("paid", Decimal(order.get("amount_paid") or 0) / 100, payment_ref)
        if provider == "phonepe":
            order = await phonepe.order_status(environment, key_id, settings.get("client_version") or "1", secret, gateway_ref)
            state = order.get("state")
            if state == "FAILED":
                return OrderState("failed", None)
            if state != "COMPLETED":
                return OrderState("pending", None)
            done = [p for p in order.get("paymentDetails") or [] if p.get("state") == "COMPLETED"]
            return OrderState("paid", Decimal(order.get("amount") or 0) / 100, str(done[-1].get("transactionId", "")) if done else "")
        if provider == "demo":
            order = await fetch_one("SELECT amount, status FROM demo_payment_orders WHERE ref = %s", (gateway_ref,))
            if order is None or order["status"] == "pending":
                return OrderState("pending", None)
            if order["status"] == "failed":
                return OrderState("failed", None)
            return OrderState("paid", Decimal(order["amount"]), f"DEMO-{gateway_ref[-8:].upper()}")
    except (cashfree.CashfreeError, razorpay.RazorpayError, phonepe.PhonePeError) as exc:
        raise GatewayError(str(exc)) from exc
    raise GatewayError(f"Unknown payment gateway {provider}.")


async def finish_demo_order(ref: str, paid: bool) -> bool:
    """The demo payment page's Pay / Fail buttons. Only a pending demo order changes."""
    count = await execute(
        "UPDATE demo_payment_orders SET status = %s WHERE ref = %s AND status = 'pending'", ("paid" if paid else "failed", ref)
    )
    return bool(count)
