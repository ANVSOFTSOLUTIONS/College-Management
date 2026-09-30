import base64
import hashlib
import hmac
import json
from datetime import timedelta

from app.db.helpers import fetch_all
from app.integrations import cashfree
from app.modules.alerts import service as alerts
from tests.factories import auth_headers, create_class, create_school, create_teacher, create_user, login

PASSWORD = "Secret123!"
API = "/api/v1"


async def _school(client, code):
    school_id = await create_school(code=code)
    await create_user(school_id=school_id, email=f"{code}-admin@example.com".lower(), password=PASSWORD, role="admin")
    teacher_user = await create_user(school_id=school_id, email=f"{code}-t@example.com".lower(), password=PASSWORD, role="teacher")
    teacher_id = await create_teacher(school_id=school_id, user_id=teacher_user)
    class_id = await create_class(school_id=school_id, teacher_id=teacher_id)
    admin = auth_headers((await login(client, f"{code}-admin@example.com".lower(), PASSWORD)).json()["access_token"])
    return class_id, admin


async def _student(client, admin, class_id, number, name, phone=None):
    body = {"admission_number": number, "full_name": name, "class_id": class_id}
    if phone:
        body["mother"] = {"full_name": "Padma", "phone": phone}
    return (await client.post(f"{API}/students", json=body, headers=admin)).json()


async def _parent_headers(client, phone, password):
    response = await client.post(f"{API}/auth/login", json={"phone": phone, "password": password})
    assert response.status_code == 200, response.text
    return auth_headers(response.json()["access_token"]), response.json()["user"]


async def test_parent_login_links_siblings_across_schools(db, client):
    class_a, admin_a = await _school(client, "PAR1")
    class_b, admin_b = await _school(client, "PAR2")
    asha = await _student(client, admin_a, class_a, "A-1", "Asha", "98480 22338")
    ravi = await _student(client, admin_b, class_b, "B-1", "Ravi", "+91 9848022338")

    first = (await client.post(f"{API}/students/{asha['id']}/parent-login", json={}, headers=admin_a)).json()
    assert (first["phone"], first["already_had_account"]) == ("9848022338", False)
    assert first["password"]
    second = (await client.post(f"{API}/students/{ravi['id']}/parent-login", json={}, headers=admin_b)).json()
    assert (second["already_had_account"], second["password"]) == (True, None)

    headers, user = await _parent_headers(client, "09848022338", first["password"])
    assert user["role"] == "parent" and user["must_change_password"] is True
    children = (await client.get(f"{API}/me/parent/children", headers=headers)).json()
    assert sorted(c["full_name"] for c in children) == ["Asha", "Ravi"]

    detail = (await client.get(f"{API}/students/{asha['id']}", headers=admin_a)).json()
    assert detail["parent_login_phone"] == "9848022338"


async def test_parent_login_needs_a_valid_mobile(db, client):
    class_id, admin = await _school(client, "PAR3")
    no_phone = await _student(client, admin, class_id, "A-1", "Asha")
    response = await client.post(f"{API}/students/{no_phone['id']}/parent-login", json={}, headers=admin)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "no_parent_mobile"


async def test_bulk_parent_logins_skip_students_without_mobile(db, client):
    class_id, admin = await _school(client, "PAR4")
    await _student(client, admin, class_id, "A-1", "Asha", "9848022338")
    await _student(client, admin, class_id, "A-2", "Bala", "9848022338")  # sibling, same mother
    await _student(client, admin, class_id, "A-3", "Chitra")
    result = (await client.post(f"{API}/students/bulk-parent-logins", json={"class_id": class_id}, headers=admin)).json()
    assert [(l["student_name"], l["already_had_account"]) for l in result["logins"]] == [("Asha", False), ("Bala", True)]
    assert result["skipped_without_mobile"] == ["Chitra"]
    again = (await client.post(f"{API}/students/bulk-parent-logins", json={"class_id": class_id}, headers=admin)).json()
    assert again["logins"] == []


async def test_parent_sees_only_own_children_with_attendance_remarks_alerts_fees(db, client):
    class_id, admin = await _school(client, "PAR5")
    asha = await _student(client, admin, class_id, "A-1", "Asha", "9848022338")
    other = await _student(client, admin, class_id, "A-2", "Other", "9000000009")
    password = (await client.post(f"{API}/students/{asha['id']}/parent-login", json={}, headers=admin)).json()["password"]
    headers, _ = await _parent_headers(client, "9848022338", password)

    today = alerts.today_ist()
    await client.post(
        f"{API}/classes/{class_id}/attendance",
        json={"date": today.isoformat(), "records": [{"student_id": asha["id"], "status": "absent"}]},
        headers=admin,
    )
    await client.post(
        f"{API}/remarks", json={"student_id": asha["id"], "category": "missed_exam", "note": "Maths test", "notify_parent": True}, headers=admin
    )
    await client.post(f"{API}/remarks", json={"student_id": asha["id"], "category": "behaviour", "note": "Staff-only note"}, headers=admin)
    await client.post(
        f"{API}/fees/items",
        json={"name": "Term 1", "academic_year": "2026", "amount": "3000", "due_date": (today + timedelta(days=5)).isoformat(), "class_ids": [class_id]},
        headers=admin,
    )

    overview = (await client.get(f"{API}/me/parent/children/{asha['id']}", headers=headers)).json()
    assert (overview["absent"], overview["attendance_days"]) == (1, 1)
    assert [r["note"] for r in overview["remarks"]] == ["Maths test"]  # only remarks meant for parents
    assert {a["kind"] for a in overview["alerts"]} == {"absence", "remark"}
    assert overview["fees"]["balance"] == 3000.0
    assert overview["online_payment_enabled"] is False

    assert (await client.get(f"{API}/me/parent/children/{other['id']}", headers=headers)).status_code == 404
    assert (await client.get(f"{API}/students", headers=headers)).status_code == 403

    # Receipts for their child only.
    line = overview["fees"]["lines"][0]
    payment = (await client.post(f"{API}/fees/payments", json={"student_fee_id": line["id"], "amount": "1000", "method": "cash"}, headers=admin)).json()
    receipt = (await client.get(f"{API}/me/parent/children/{asha['id']}/receipts/{payment['id']}", headers=headers)).json()
    assert receipt["amount"] == 1000.0
    assert (await client.get(f"{API}/me/parent/children/{other['id']}/receipts/{payment['id']}", headers=headers)).status_code == 404


async def test_online_payment_is_off_until_the_school_connects_cashfree(db, client, monkeypatch):
    class_id, admin = await _school(client, "PAR6")
    asha = await _student(client, admin, class_id, "A-1", "Asha", "9848022338")
    password = (await client.post(f"{API}/students/{asha['id']}/parent-login", json={}, headers=admin)).json()["password"]
    headers, _ = await _parent_headers(client, "9848022338", password)
    await client.post(
        f"{API}/fees/items",
        json={"name": "Term 1", "academic_year": "2026", "amount": "2500", "due_date": "2026-12-01", "class_ids": [class_id]},
        headers=admin,
    )
    line = (await client.get(f"{API}/me/parent/children/{asha['id']}", headers=headers)).json()["fees"]["lines"][0]
    pay_url = f"{API}/me/parent/children/{asha['id']}/fees/{line['id']}/pay"

    off = await client.post(pay_url, headers=headers)
    assert off.status_code == 409 and off.json()["error"]["code"] == "online_payment_unavailable"

    # Connect the school's Cashfree (keys stay with the school; the secret is never returned).
    missing = await client.put(f"{API}/fees/payment-settings", json={"key_id": "CF_APP_1", "enabled": True}, headers=admin)
    assert missing.status_code == 400
    body = {"key_id": "CF_APP_1", "key_secret": "cfsk_test", "environment": "sandbox", "enabled": True}
    saved = (await client.put(f"{API}/fees/payment-settings", json=body, headers=admin)).json()
    assert saved == {
        "provider": "cashfree", "key_id": "CF_APP_1", "has_secret": True, "environment": "sandbox", "enabled": True,
        "client_version": "", "allowed_providers": ["cashfree", "razorpay", "phonepe"],
    }

    # A fake Cashfree: orders are ACTIVE until the test marks them PAID.
    orders = {}

    async def fake_create(environment, app_id, secret, *, order_id, amount, customer_id, customer_phone, customer_name, note):
        assert (environment, app_id, secret, customer_phone) == ("sandbox", "CF_APP_1", "cfsk_test", "9848022338")
        orders[order_id] = {"order_id": order_id, "order_amount": float(amount), "order_status": "ACTIVE"}
        return {"payment_session_id": f"session_{order_id}"}

    async def fake_fetch(environment, app_id, secret, order_id):
        return orders[order_id]

    async def fake_payment_id(environment, app_id, secret, order_id):
        return "cf_pay_77"

    monkeypatch.setattr(cashfree, "create_order", fake_create)
    monkeypatch.setattr(cashfree, "fetch_order", fake_fetch)
    monkeypatch.setattr(cashfree, "successful_payment_id", fake_payment_id)

    order = (await client.post(pay_url, headers=headers)).json()
    assert (order["payment_session_id"], order["environment"], order["amount"]) == (f"session_{order['payment_id']}", "sandbox", 2500.0)
    confirm_url = f"{API}/me/parent/children/{asha['id']}/payments/{order['payment_id']}/confirm"

    # Nothing is recorded until Cashfree itself says the order is paid.
    pending = await client.post(confirm_url, headers=headers)
    assert pending.status_code == 409 and pending.json()["error"]["code"] == "payment_pending"
    assert (await client.get(f"{API}/fees/students/{asha['id']}", headers=admin)).json()["balance"] == 2500.0

    orders[order["payment_id"]]["order_status"] = "PAID"
    good = await client.post(confirm_url, headers=headers)
    assert good.status_code == 200, good.text
    assert good.json()["method"] == "online" and good.json()["receipt_number"].startswith("RCPT-")
    assert (await client.post(confirm_url, headers=headers)).json()["receipt_number"] == good.json()["receipt_number"]  # idempotent
    assert (await client.get(f"{API}/fees/students/{asha['id']}", headers=admin)).json()["balance"] == 0.0


async def test_cashfree_amount_mismatch_expiry_and_webhook(db, client, monkeypatch):
    class_id, admin = await _school(client, "PAR8")
    asha = await _student(client, admin, class_id, "A-1", "Asha", "9848022340")
    password = (await client.post(f"{API}/students/{asha['id']}/parent-login", json={}, headers=admin)).json()["password"]
    headers, _ = await _parent_headers(client, "9848022340", password)
    for name in ("Term 1", "Term 2", "Term 3"):
        await client.post(
            f"{API}/fees/items",
            json={"name": name, "academic_year": "2026", "amount": "1000", "due_date": "2026-12-01", "class_ids": [class_id]},
            headers=admin,
        )
    lines = (await client.get(f"{API}/me/parent/children/{asha['id']}", headers=headers)).json()["fees"]["lines"]
    await client.put(f"{API}/fees/payment-settings", json={"key_id": "CF_APP_2", "key_secret": "cfsk_2", "enabled": True}, headers=admin)
    orders = {}

    async def fake_create(environment, app_id, secret, *, order_id, amount, **_):
        orders[order_id] = {"order_id": order_id, "order_amount": float(amount), "order_status": "ACTIVE"}
        return {"payment_session_id": "s"}

    async def fake_fetch(environment, app_id, secret, order_id):
        return orders[order_id]

    async def fake_payment_id(*_):
        return "cf_pay_1"

    monkeypatch.setattr(cashfree, "create_order", fake_create)
    monkeypatch.setattr(cashfree, "fetch_order", fake_fetch)
    monkeypatch.setattr(cashfree, "successful_payment_id", fake_payment_id)

    async def start(line):
        return (await client.post(f"{API}/me/parent/children/{asha['id']}/fees/{line['id']}/pay", headers=headers)).json()["payment_id"]

    # Paid, but for a different amount: refused.
    wrong = await start(lines[0])
    orders[wrong].update(order_status="PAID", order_amount=1.0)
    response = await client.post(f"{API}/me/parent/children/{asha['id']}/payments/{wrong}/confirm", headers=headers)
    assert response.status_code == 400 and response.json()["error"]["code"] == "payment_not_verified"

    # Expired orders are marked failed.
    expired = await start(lines[1])
    orders[expired]["order_status"] = "EXPIRED"
    assert (await client.post(f"{API}/me/parent/children/{asha['id']}/payments/{expired}/confirm", headers=headers)).status_code == 400

    # The webhook records a payment whose browser tab closed, but only with a valid signature.
    paid = await start(lines[2])
    orders[paid]["order_status"] = "PAID"
    raw = json.dumps({"type": "PAYMENT_SUCCESS_WEBHOOK", "data": {"order": {"order_id": paid}}}).encode()
    timestamp = "1727500000"
    forged = await client.post(f"{API}/public/payments/cashfree/webhook", content=raw, headers={"x-webhook-timestamp": timestamp, "x-webhook-signature": "bad"})
    assert forged.status_code == 401
    signature = base64.b64encode(hmac.new(b"cfsk_2", timestamp.encode() + raw, hashlib.sha256).digest()).decode()
    ok = await client.post(f"{API}/public/payments/cashfree/webhook", content=raw, headers={"x-webhook-timestamp": timestamp, "x-webhook-signature": signature})
    assert ok.status_code == 204
    account = (await client.get(f"{API}/fees/students/{asha['id']}", headers=admin)).json()
    assert account["balance"] == 2000.0
    recorded = await fetch_all("SELECT status, gateway_payment_id FROM fee_payments WHERE id = %s", (paid,))
    assert recorded == [{"status": "success", "gateway_payment_id": "cf_pay_1"}]


def test_cashfree_webhook_signature_check():
    raw, timestamp = b'{"a":1}', "123"
    signature = base64.b64encode(hmac.new(b"secret", b"123" + raw, hashlib.sha256).digest()).decode()
    assert cashfree.verify_webhook_signature(raw, timestamp, signature, "secret")
    assert not cashfree.verify_webhook_signature(raw, "124", signature, "secret")
    assert not cashfree.verify_webhook_signature(raw, timestamp, "", "secret")
