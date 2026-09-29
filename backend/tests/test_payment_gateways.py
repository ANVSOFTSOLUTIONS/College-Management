import json

from app.db.helpers import fetch_all
from app.integrations import phonepe, razorpay
from tests.factories import auth_headers, create_user, login
from tests.test_parents import API, PASSWORD, _parent_headers, _school, _student


async def _family(client, code, phone):
    class_id, admin = await _school(client, code)
    asha = await _student(client, admin, class_id, "A-1", "Asha", phone)
    password = (await client.post(f"{API}/students/{asha['id']}/parent-login", json={}, headers=admin)).json()["password"]
    headers, _ = await _parent_headers(client, phone, password)
    for name in ("Term 1", "Term 2"):
        await client.post(
            f"{API}/fees/items",
            json={"name": name, "academic_year": "2026", "amount": "1500", "due_date": "2026-12-01", "class_ids": [class_id]},
            headers=admin,
        )
    lines = (await client.get(f"{API}/me/parent/children/{asha['id']}", headers=headers)).json()["fees"]["lines"]
    return admin, headers, asha, lines


async def test_super_admin_chooses_which_gateways_a_school_may_use(db, client):
    admin, _, _, _ = await _family(client, "GW1", "9848022401")
    await create_user(school_id=None, email="root-gw@example.com", password=PASSWORD, role="super_admin")
    root = auth_headers((await login(client, "root-gw@example.com", PASSWORD)).json()["access_token"])
    school = next(s for s in (await client.get(f"{API}/super-admin/schools", headers=root)).json() if s["code"] == "GW1")
    assert school["payment_gateways"] == ["cashfree", "razorpay", "phonepe"]  # all allowed by default

    changed = await client.patch(f"{API}/super-admin/schools/{school['id']}", json={"payment_gateways": ["phonepe", "razorpay"]}, headers=root)
    assert changed.json()["payment_gateways"] == ["razorpay", "phonepe"]
    bad = await client.patch(f"{API}/super-admin/schools/{school['id']}", json={"payment_gateways": ["paypal"]}, headers=root)
    assert bad.status_code == 422
    assert (await client.patch(f"{API}/super-admin/schools/{school['id']}", json={"payment_gateways": []}, headers=admin)).status_code == 403

    settings = (await client.get(f"{API}/fees/payment-settings", headers=admin)).json()
    assert settings["allowed_providers"] == ["razorpay", "phonepe"] and settings["provider"] == "razorpay"
    refused = await client.put(
        f"{API}/fees/payment-settings", json={"provider": "cashfree", "key_id": "CF", "key_secret": "s", "enabled": True}, headers=admin
    )
    assert refused.status_code == 403 and refused.json()["error"]["code"] == "gateway_not_allowed"

    # PhonePe needs its client version too.
    no_version = await client.put(
        f"{API}/fees/payment-settings", json={"provider": "phonepe", "key_id": "PP", "key_secret": "s", "enabled": True}, headers=admin
    )
    assert no_version.status_code == 400

    # A gateway the super admin later switches off stops taking payments.
    ok = await client.put(
        f"{API}/fees/payment-settings", json={"provider": "razorpay", "key_id": "rzp_test_1", "key_secret": "s", "enabled": True}, headers=admin
    )
    assert ok.status_code == 200
    await client.patch(f"{API}/super-admin/schools/{school['id']}", json={"payment_gateways": ["phonepe"]}, headers=root)
    assert (await client.get(f"{API}/fees/payment-settings", headers=admin)).json()["allowed_providers"] == ["phonepe"]


async def test_switching_gateway_needs_the_new_secret(db, client):
    admin, _, _, _ = await _family(client, "GW2", "9848022402")
    await client.put(f"{API}/fees/payment-settings", json={"key_id": "CF", "key_secret": "cf_secret", "enabled": True}, headers=admin)
    switched = await client.put(f"{API}/fees/payment-settings", json={"provider": "razorpay", "key_id": "rzp_test_2", "enabled": True}, headers=admin)
    assert switched.status_code == 400 and switched.json()["error"]["code"] == "keys_required"


async def test_parent_pays_with_razorpay(db, client, monkeypatch):
    admin, headers, asha, lines = await _family(client, "GW3", "9848022403")
    body = {"provider": "razorpay", "key_id": "rzp_test_3", "key_secret": "rzp_secret", "enabled": True}
    assert (await client.put(f"{API}/fees/payment-settings", json=body, headers=admin)).status_code == 200

    orders = {}

    async def fake_create(key_id, key_secret, *, receipt, amount, note):
        assert (key_id, key_secret) == ("rzp_test_3", "rzp_secret") and len(receipt) <= 40
        rzp_id = f"order_{len(orders) + 1}"
        orders[rzp_id] = {"id": rzp_id, "amount": razorpay.to_paise(amount), "amount_paid": 0, "status": "created"}
        return orders[rzp_id]

    async def fake_fetch(key_id, key_secret, order_id):
        return orders[order_id]

    async def fake_captured(key_id, key_secret, order_id):
        return "pay_RZP1"

    monkeypatch.setattr(razorpay, "create_order", fake_create)
    monkeypatch.setattr(razorpay, "fetch_order", fake_fetch)
    monkeypatch.setattr(razorpay, "captured_payment_id", fake_captured)

    order = (await client.post(f"{API}/me/parent/children/{asha['id']}/fees/{lines[0]['id']}/pay", headers=headers)).json()
    assert (order["provider"], order["key_id"], order["gateway_order_id"], order["amount"]) == ("razorpay", "rzp_test_3", "order_1", 1500.0)
    confirm_url = f"{API}/me/parent/children/{asha['id']}/payments/{order['payment_id']}/confirm"
    pending = await client.post(confirm_url, headers=headers)
    assert pending.status_code == 409 and "Razorpay" in pending.json()["error"]["message"]

    orders["order_1"].update(status="paid", amount_paid=150000)
    good = await client.post(confirm_url, headers=headers)
    assert good.status_code == 200, good.text

    # Pay all: one Razorpay order; the webhook (order.paid) records it once Razorpay confirms.
    batch = (await client.post(f"{API}/me/parent/children/{asha['id']}/fees/pay-all", headers=headers)).json()
    assert (batch["gateway_order_id"], batch["amount"]) == ("order_2", 1500.0)
    orders["order_2"].update(status="paid", amount_paid=150000)
    raw = json.dumps({"event": "order.paid", "payload": {"order": {"entity": {"id": "order_2"}}}}).encode()
    assert (await client.post(f"{API}/public/payments/razorpay/webhook", content=raw)).status_code == 204
    assert (await client.get(f"{API}/fees/students/{asha['id']}", headers=admin)).json()["balance"] == 0.0
    rows = await fetch_all("SELECT gateway, gateway_payment_id FROM fee_payments WHERE status = 'success' AND gateway_ref = 'order_2'")
    assert rows == [{"gateway": "razorpay", "gateway_payment_id": "pay_RZP1"}]


async def test_razorpay_wrong_amount_is_refused(db, client, monkeypatch):
    admin, headers, asha, lines = await _family(client, "GW4", "9848022404")
    await client.put(f"{API}/fees/payment-settings", json={"provider": "razorpay", "key_id": "rzp_test_4", "key_secret": "x", "enabled": True}, headers=admin)
    order_state = {"id": "order_X", "amount": 150000, "amount_paid": 100, "status": "paid"}

    async def fake_create(*_, **__):
        return order_state

    async def fake_fetch(*_):
        return order_state

    async def fake_captured(*_):
        return "pay_X"

    monkeypatch.setattr(razorpay, "create_order", fake_create)
    monkeypatch.setattr(razorpay, "fetch_order", fake_fetch)
    monkeypatch.setattr(razorpay, "captured_payment_id", fake_captured)
    order = (await client.post(f"{API}/me/parent/children/{asha['id']}/fees/{lines[0]['id']}/pay", headers=headers)).json()
    response = await client.post(f"{API}/me/parent/children/{asha['id']}/payments/{order['payment_id']}/confirm", headers=headers)
    assert response.status_code == 400 and response.json()["error"]["code"] == "payment_not_verified"


async def test_parent_pays_with_phonepe(db, client, monkeypatch):
    admin, headers, asha, lines = await _family(client, "GW5", "9848022405")
    body = {"provider": "phonepe", "key_id": "PP_CLIENT", "key_secret": "pp_secret", "client_version": "1", "environment": "sandbox", "enabled": True}
    assert (await client.put(f"{API}/fees/payment-settings", json=body, headers=admin)).status_code == 200
    orders = {}

    async def fake_create(environment, client_id, client_version, secret, *, order_id, amount, note, redirect_url):
        assert (environment, client_id, client_version, secret) == ("sandbox", "PP_CLIENT", "1", "pp_secret")
        orders[order_id] = {"state": "PENDING", "amount": int(amount * 100), "paymentDetails": []}
        return {"orderId": "OMO1", "redirectUrl": f"https://pay.example/{order_id}"}

    async def fake_status(environment, client_id, client_version, secret, order_id):
        return orders[order_id]

    monkeypatch.setattr(phonepe, "create_order", fake_create)
    monkeypatch.setattr(phonepe, "order_status", fake_status)

    order = (await client.post(f"{API}/me/parent/children/{asha['id']}/fees/{lines[0]['id']}/pay", headers=headers)).json()
    assert order["provider"] == "phonepe" and order["checkout_url"] == f"https://pay.example/{order['payment_id']}"
    confirm_url = f"{API}/me/parent/children/{asha['id']}/payments/{order['payment_id']}/confirm"
    assert (await client.post(confirm_url, headers=headers)).status_code == 409

    # The webhook only makes us ask PhonePe; it records the payment once PhonePe says COMPLETED.
    orders[order["payment_id"]].update(state="COMPLETED", paymentDetails=[{"state": "COMPLETED", "transactionId": "TXN9"}])
    raw = json.dumps({"event": "checkout.order.completed", "payload": {"merchantOrderId": order["payment_id"]}}).encode()
    assert (await client.post(f"{API}/public/payments/phonepe/webhook", content=raw)).status_code == 204
    receipt = (await client.post(confirm_url, headers=headers)).json()
    assert receipt["method"] == "online"
    assert (await client.get(f"{API}/fees/students/{asha['id']}", headers=admin)).json()["balance"] == 1500.0

    # A failed PhonePe order is marked failed.
    second = (await client.post(f"{API}/me/parent/children/{asha['id']}/fees/{lines[1]['id']}/pay", headers=headers)).json()
    orders[second["payment_id"]]["state"] = "FAILED"
    failed = await client.post(f"{API}/me/parent/children/{asha['id']}/payments/{second['payment_id']}/confirm", headers=headers)
    assert failed.status_code == 400


async def test_demo_gateway_needs_the_super_admin_and_no_keys(db, client):
    admin, headers, asha, lines = await _family(client, "GW6", "9848022406")
    refused = await client.put(f"{API}/fees/payment-settings", json={"provider": "demo", "enabled": True}, headers=admin)
    assert refused.status_code == 403  # not on for schools by default

    await create_user(school_id=None, email="root-gw6@example.com", password=PASSWORD, role="super_admin")
    root = auth_headers((await login(client, "root-gw6@example.com", PASSWORD)).json()["access_token"])
    school = next(s for s in (await client.get(f"{API}/super-admin/schools", headers=root)).json() if s["code"] == "GW6")
    await client.patch(f"{API}/super-admin/schools/{school['id']}", json={"payment_gateways": ["razorpay", "demo"]}, headers=root)
    saved = await client.put(f"{API}/fees/payment-settings", json={"provider": "demo", "enabled": True}, headers=admin)
    assert saved.status_code == 200, saved.text

    order = (await client.post(f"{API}/me/parent/children/{asha['id']}/fees/{lines[0]['id']}/pay", headers=headers)).json()
    assert order["provider"] == "demo" and order["gateway_order_id"] == order["payment_id"]
    confirm_url = f"{API}/me/parent/children/{asha['id']}/payments/{order['payment_id']}/confirm"
    assert (await client.post(confirm_url, headers=headers)).status_code == 409  # page not finished yet

    assert (await client.post(f"{API}/public/payments/demo/{order['payment_id']}/pay")).status_code == 204
    assert (await client.post(f"{API}/public/payments/demo/{order['payment_id']}/fail")).status_code == 404  # already finished
    receipt = await client.post(confirm_url, headers=headers)
    assert receipt.status_code == 200 and receipt.json()["amount"] == 1500.0

    second = (await client.post(f"{API}/me/parent/children/{asha['id']}/fees/{lines[1]['id']}/pay", headers=headers)).json()
    await client.post(f"{API}/public/payments/demo/{second['payment_id']}/fail")
    assert (await client.post(f"{API}/me/parent/children/{asha['id']}/payments/{second['payment_id']}/confirm", headers=headers)).status_code == 400
