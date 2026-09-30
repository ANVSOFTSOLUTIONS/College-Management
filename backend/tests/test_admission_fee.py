import base64
import hashlib
import hmac
import json

from app.integrations import cashfree
from tests.test_admissions import API, _apply, _setup


def _fake_cashfree(monkeypatch, orders):
    async def fake_create(environment, app_id, secret, *, order_id, amount, customer_phone, **_):
        assert customer_phone == "9848022338"
        orders[order_id] = {"order_id": order_id, "order_amount": float(amount), "order_status": "ACTIVE"}
        return {"payment_session_id": f"session_{order_id}"}

    async def fake_fetch(environment, app_id, secret, order_id):
        return orders[order_id]

    async def fake_payment_id(*_):
        return "cf_pay_9"

    monkeypatch.setattr(cashfree, "create_order", fake_create)
    monkeypatch.setattr(cashfree, "fetch_order", fake_fetch)
    monkeypatch.setattr(cashfree, "successful_payment_id", fake_payment_id)


async def test_settings_keep_the_fee_when_only_opening_or_closing(db, client):
    ctx = await _setup(client, "FEE1")
    url = f"{API}/admissions/settings"
    assert (await client.get(url, headers=ctx["admin"])).json() == {"open": True, "admission_fee": 0.0}
    assert (await client.put(url, json={"open": True, "admission_fee": "500"}, headers=ctx["admin"])).json()["admission_fee"] == 500.0
    assert (await client.put(url, json={"open": False}, headers=ctx["admin"])).json() == {"open": False, "admission_fee": 500.0}
    assert (await client.put(url, json={"open": True, "admission_fee": "-1"}, headers=ctx["admin"])).status_code == 422

    # No fee: applications carry none.
    await client.put(url, json={"open": True, "admission_fee": "0"}, headers=ctx["admin"])
    submitted = (await _apply(client, ctx)).json()
    assert submitted["fee_amount"] == 0
    listed = (await client.get(f"{API}/admissions", headers=ctx["admin"])).json()
    assert (listed[0]["fee_status"], listed[0]["fee_amount"]) == ("none", 0)


async def test_fee_paid_online_after_applying(db, client, monkeypatch):
    ctx = await _setup(client, "FEE2")
    await client.put(f"{API}/admissions/settings", json={"open": True, "admission_fee": "750"}, headers=ctx["admin"])
    form = (await client.get(f"{API}/public/schools/{ctx['code']}/admissions")).json()
    assert (form["admission_fee"], form["online_payment"]) == (750.0, False)

    submitted = (await _apply(client, ctx)).json()
    assert submitted["fee_amount"] == 750.0
    base = f"{API}/public/schools/{ctx['code']}/admissions/{submitted['id']}/fee"
    token = {"token": submitted["upload_token"]}

    # Cashfree not connected yet: pay at the office.
    off = await client.post(f"{base}/pay", json=token)
    assert off.status_code == 409 and off.json()["error"]["code"] == "online_payment_unavailable"

    await client.put(f"{API}/fees/payment-settings", json={"key_id": "CF_A", "key_secret": "cfsk_a", "environment": "sandbox", "enabled": True}, headers=ctx["admin"])
    assert (await client.get(f"{API}/public/schools/{ctx['code']}/admissions")).json()["online_payment"] is True
    orders = {}
    _fake_cashfree(monkeypatch, orders)

    assert (await client.post(f"{base}/pay", json={"token": "x" * 64})).status_code == 403
    order = (await client.post(f"{base}/pay", json=token)).json()
    assert (order["amount"], order["environment"], order["payment_session_id"]) == (750.0, "sandbox", f"session_{order['order_id']}")
    assert len(order["order_id"]) <= 45

    pending = await client.post(f"{base}/confirm", json=token)
    assert pending.status_code == 409 and pending.json()["error"]["code"] == "payment_pending"

    # Paid for a different amount: not counted.
    orders[order["order_id"]].update(order_status="PAID", order_amount=1.0)
    assert (await client.post(f"{base}/confirm", json=token)).status_code == 409

    orders[order["order_id"]]["order_amount"] = 750.0
    paid = await client.post(f"{base}/confirm", json=token)
    assert paid.json() == {"fee_status": "paid", "fee_amount": 750.0}
    assert (await client.post(f"{base}/confirm", json=token)).json()["fee_status"] == "paid"  # idempotent
    assert (await client.post(f"{base}/pay", json=token)).json()["error"]["code"] == "fee_not_due"

    app = (await client.get(f"{API}/admissions/{submitted['id']}", headers=ctx["admin"])).json()
    assert (app["fee_status"], app["fee_method"], app["fee_payment_ref"]) == ("paid", "online", "cf_pay_9")


async def test_fee_webhook_records_a_payment_whose_tab_closed(db, client, monkeypatch):
    ctx = await _setup(client, "FEE3")
    await client.put(f"{API}/admissions/settings", json={"open": True, "admission_fee": "300"}, headers=ctx["admin"])
    await client.put(f"{API}/fees/payment-settings", json={"key_id": "CF_B", "key_secret": "cfsk_b", "enabled": True}, headers=ctx["admin"])
    orders = {}
    _fake_cashfree(monkeypatch, orders)
    submitted = (await _apply(client, ctx)).json()
    base = f"{API}/public/schools/{ctx['code']}/admissions/{submitted['id']}/fee"
    order_id = (await client.post(f"{base}/pay", json={"token": submitted["upload_token"]})).json()["order_id"]
    orders[order_id]["order_status"] = "PAID"

    raw = json.dumps({"data": {"order": {"order_id": order_id}}}).encode()
    timestamp = "1700000000"

    def signed(secret):
        return base64.b64encode(hmac.new(secret.encode(), timestamp.encode() + raw, hashlib.sha256).digest()).decode()

    webhook = f"{API}/public/payments/cashfree/webhook"
    bad = await client.post(webhook, content=raw, headers={"x-webhook-timestamp": timestamp, "x-webhook-signature": signed("wrong")})
    assert bad.status_code == 401
    good = await client.post(webhook, content=raw, headers={"x-webhook-timestamp": timestamp, "x-webhook-signature": signed("cfsk_b")})
    assert good.status_code == 204
    assert (await client.get(f"{API}/admissions/{submitted['id']}", headers=ctx["admin"])).json()["fee_status"] == "paid"


async def test_office_marks_fee_paid_or_waived_and_it_is_logged(db, client):
    ctx = await _setup(client, "FEE4")
    await client.put(f"{API}/admissions/settings", json={"open": True, "admission_fee": "500"}, headers=ctx["admin"])
    first = (await _apply(client, ctx)).json()
    second = (await _apply(client, ctx, student_name="Ravi Rao")).json()

    paid = await client.post(f"{API}/admissions/{first['id']}/fee", json={"action": "paid", "reference": "R-12"}, headers=ctx["admin"])
    assert (paid.json()["fee_status"], paid.json()["fee_method"], paid.json()["fee_payment_ref"]) == ("paid", "office", "R-12")
    assert (await client.post(f"{API}/admissions/{first['id']}/fee", json={"action": "waived"}, headers=ctx["admin"])).status_code == 409
    waived = await client.post(f"{API}/admissions/{second['id']}/fee", json={"action": "waived"}, headers=ctx["admin"])
    assert waived.json()["fee_status"] == "waived"
    # Teachers can't.
    assert (await client.post(f"{API}/admissions/{second['id']}/fee", json={"action": "paid"}, headers=ctx["ravi"])).status_code == 403

    log = [e["summary"] for e in (await client.get(f"{API}/audit-log", params={"area": "admissions"}, headers=ctx["admin"])).json()]
    assert "Application fee ₹500.00 for Asha Rao" in log[1] and "received at the office, ref R-12" in log[1]
    assert log[0].endswith("waived")


async def test_approving_gives_the_parent_a_login(db, client):
    ctx = await _setup(client, "FEE5")
    first = (await _apply(client, ctx)).json()
    approved = (await client.post(f"{API}/admissions/{first['id']}/approve", json={"class_id": ctx["grades"]["Grade 2"]["id"]}, headers=ctx["admin"])).json()
    login = approved["parent_login"]
    assert (login["parent_name"], login["phone"], login["already_had_account"]) == ("Srinivas Rao", "9848022338", False)
    assert login["password"]
    signed_in = await client.post(f"{API}/auth/login", json={"phone": "9848022338", "password": login["password"]})
    assert signed_in.status_code == 200, signed_in.text

    # A sibling admitted later joins the same login; no new password.
    second = (await _apply(client, ctx, student_name="Ravi Rao", class_applied="LKG")).json()
    sibling = (await client.post(f"{API}/admissions/{second['id']}/approve", json={"class_id": ctx["grades"]["LKG"]["id"]}, headers=ctx["admin"])).json()
    assert (sibling["parent_login"]["already_had_account"], sibling["parent_login"]["password"]) == (True, None)
    parent = {"Authorization": f"Bearer {signed_in.json()['access_token']}"}
    children = (await client.get(f"{API}/me/parent/children", headers=parent)).json()
    assert sorted(c["full_name"] for c in children) == ["Asha Rao", "Ravi Rao"]

    # Other lists don't carry a login.
    assert (await client.get(f"{API}/admissions/{first['id']}", headers=ctx["admin"])).json()["parent_login"] is None
