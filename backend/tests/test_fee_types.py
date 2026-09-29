import base64
import hashlib
import hmac
import json

from app.integrations import cashfree
from tests.test_parents import API, _parent_headers, _school, _student

FEE = {"academic_year": "2026", "due_date": "2026-12-01"}


async def test_fee_types_and_fees_for_chosen_students(db, client):
    class_id, admin = await _school(client, "FT1")
    asha = await _student(client, admin, class_id, "A-1", "Asha")
    ravi = await _student(client, admin, class_id, "A-2", "Ravi")

    tuition = await client.post(f"{API}/fees/items", json={**FEE, "name": "Term 1", "amount": "5000", "class_ids": [class_id]}, headers=admin)
    assert tuition.status_code == 201, tuition.text
    assert (tuition.json()[0]["category"], tuition.json()[0]["applies_to"], tuition.json()[0]["student_count"]) == ("tuition", "class", 2)

    # Bus fee only for Asha.
    bus = await client.post(
        f"{API}/fees/items", json={**FEE, "name": "Bus Term 1", "category": "transport", "amount": "1200", "student_ids": [asha["id"]]}, headers=admin
    )
    assert bus.status_code == 201, bus.text
    bus_item = bus.json()[0]
    assert (bus_item["category"], bus_item["applies_to"], bus_item["student_count"]) == ("transport", "selected", 1)
    lines = (await client.get(f"{API}/fees/students/{asha['id']}", headers=admin)).json()["lines"]
    assert sorted((line["name"], line["category"]) for line in lines) == [("Bus Term 1", "transport"), ("Term 1", "tuition")]
    assert [line["name"] for line in (await client.get(f"{API}/fees/students/{ravi['id']}", headers=admin)).json()["lines"]] == ["Term 1"]

    # A class-wide sync doesn't apply; adding Ravi later does.
    assert (await client.post(f"{API}/fees/items/{bus_item['id']}/sync", headers=admin)).status_code == 409
    added = await client.post(f"{API}/fees/items/{bus_item['id']}/students", json={"student_ids": [ravi["id"]]}, headers=admin)
    assert added.json()["student_count"] == 2
    assert (await client.post(f"{API}/fees/items/{tuition.json()[0]['id']}/students", json={"student_ids": [ravi["id"]]}, headers=admin)).status_code == 409

    # Ravi stops using the bus: the unpaid fee comes off.
    ravi_bus = next(line for line in (await client.get(f"{API}/fees/students/{ravi['id']}", headers=admin)).json()["lines"] if line["category"] == "transport")
    after = await client.delete(f"{API}/fees/student-fees/{ravi_bus['id']}", headers=admin)
    assert [line["name"] for line in after.json()["lines"]] == ["Term 1"]

    # Paid fees can't be removed.
    asha_bus = next(line for line in lines if line["category"] == "transport")
    await client.post(f"{API}/fees/payments", json={"student_fee_id": asha_bus["id"], "amount": "100", "method": "cash"}, headers=admin)
    assert (await client.delete(f"{API}/fees/student-fees/{asha_bus['id']}", headers=admin)).status_code == 409

    # Validation: classes or students, not both or neither; only this school's students.
    both = {**FEE, "name": "X", "amount": "1", "class_ids": [class_id], "student_ids": [asha["id"]]}
    assert (await client.post(f"{API}/fees/items", json=both, headers=admin)).status_code == 422
    assert (await client.post(f"{API}/fees/items", json={**FEE, "name": "X", "amount": "1"}, headers=admin)).status_code == 422
    other_class, other_admin = await _school(client, "FT2")
    stranger = await _student(client, other_admin, other_class, "B-1", "Stranger")
    wrong = await client.post(f"{API}/fees/items", json={**FEE, "name": "X", "amount": "1", "student_ids": [stranger["id"]]}, headers=admin)
    assert wrong.status_code == 400


async def test_parent_pays_all_fees_at_once(db, client, monkeypatch):
    class_id, admin = await _school(client, "FT3")
    asha = await _student(client, admin, class_id, "A-1", "Asha", "9848022350")
    password = (await client.post(f"{API}/students/{asha['id']}/parent-login", json={}, headers=admin)).json()["password"]
    parent, _ = await _parent_headers(client, "9848022350", password)
    await client.post(f"{API}/fees/items", json={**FEE, "name": "Term 1", "amount": "5000", "class_ids": [class_id]}, headers=admin)
    await client.post(f"{API}/fees/items", json={**FEE, "name": "Bus", "category": "transport", "amount": "1200", "student_ids": [asha["id"]]}, headers=admin)
    await client.post(f"{API}/fees/items", json={**FEE, "name": "Exam", "category": "exam", "amount": "300", "class_ids": [class_id]}, headers=admin)
    exam = next(line for line in (await client.get(f"{API}/fees/students/{asha['id']}", headers=admin)).json()["lines"] if line["name"] == "Exam")
    await client.post(f"{API}/fees/payments", json={"student_fee_id": exam["id"], "amount": "300", "method": "cash"}, headers=admin)
    term = next(line for line in (await client.get(f"{API}/fees/students/{asha['id']}", headers=admin)).json()["lines"] if line["name"] == "Term 1")
    await client.put(f"{API}/fees/student-fees/{term['id']}/discount", json={"discount": "500"}, headers=admin)

    pay_all = f"{API}/me/parent/children/{asha['id']}/fees/pay-all"
    assert (await client.post(pay_all, headers=parent)).json()["error"]["code"] == "online_payment_unavailable"
    await client.put(f"{API}/fees/payment-settings", json={"key_id": "CF_X", "key_secret": "cfsk_x", "enabled": True}, headers=admin)

    orders = {}

    async def fake_create(environment, app_id, secret, *, order_id, amount, **_):
        orders[order_id] = {"order_id": order_id, "order_amount": float(amount), "order_status": "ACTIVE"}
        return {"payment_session_id": f"s_{order_id}"}

    async def fake_fetch(environment, app_id, secret, order_id):
        return orders[order_id]

    async def fake_payment_id(*_):
        return "cf_all_1"

    monkeypatch.setattr(cashfree, "create_order", fake_create)
    monkeypatch.setattr(cashfree, "fetch_order", fake_fetch)
    monkeypatch.setattr(cashfree, "successful_payment_id", fake_payment_id)

    # Only what is still due: 4500 tuition (after the concession) + 1200 bus; the paid exam fee is left out.
    order = (await client.post(pay_all, headers=parent)).json()
    assert order["amount"] == 5700.0 and order["payment_id"].startswith("all_") and len(order["payment_id"]) <= 45
    confirm = f"{API}/me/parent/children/{asha['id']}/pay-all/{order['payment_id']}/confirm"
    assert (await client.post(confirm, headers=parent)).json()["error"]["code"] == "payment_pending"
    assert (await client.get(f"{API}/fees/students/{asha['id']}", headers=admin)).json()["balance"] == 5700.0

    orders[order["payment_id"]]["order_status"] = "PAID"
    paid = await client.post(confirm, headers=parent)
    assert paid.status_code == 200, paid.text
    receipts = paid.json()["receipts"]
    assert sorted((r["fee_name"], r["amount"]) for r in receipts) == [("Bus", 1200.0), ("Term 1", 4500.0)]
    assert len({r["receipt_number"] for r in receipts}) == 2
    assert (await client.post(confirm, headers=parent)).json()["receipts"] == receipts  # idempotent
    assert (await client.get(f"{API}/fees/students/{asha['id']}", headers=admin)).json()["balance"] == 0.0
    assert (await client.post(pay_all, headers=parent)).json()["error"]["code"] == "already_paid"

    # Another parent can't confirm this child's payment.
    ravi = await _student(client, admin, class_id, "A-2", "Ravi", "9848022351")
    other_pw = (await client.post(f"{API}/students/{ravi['id']}/parent-login", json={}, headers=admin)).json()["password"]
    other, _ = await _parent_headers(client, "9848022351", other_pw)
    assert (await client.post(confirm, headers=other)).status_code in (403, 404)


async def test_pay_all_wrong_amount_and_webhook(db, client, monkeypatch):
    class_id, admin = await _school(client, "FT4")
    asha = await _student(client, admin, class_id, "A-1", "Asha", "9848022352")
    password = (await client.post(f"{API}/students/{asha['id']}/parent-login", json={}, headers=admin)).json()["password"]
    parent, _ = await _parent_headers(client, "9848022352", password)
    for name in ("Term 1", "Term 2"):
        await client.post(f"{API}/fees/items", json={**FEE, "name": name, "amount": "1000", "class_ids": [class_id]}, headers=admin)
    await client.put(f"{API}/fees/payment-settings", json={"key_id": "CF_Y", "key_secret": "cfsk_y", "enabled": True}, headers=admin)
    orders = {}

    async def fake_create(environment, app_id, secret, *, order_id, amount, **_):
        orders[order_id] = {"order_id": order_id, "order_amount": float(amount), "order_status": "ACTIVE"}
        return {"payment_session_id": "s"}

    async def fake_fetch(environment, app_id, secret, order_id):
        return orders[order_id]

    async def fake_payment_id(*_):
        return "cf_2"

    monkeypatch.setattr(cashfree, "create_order", fake_create)
    monkeypatch.setattr(cashfree, "fetch_order", fake_fetch)
    monkeypatch.setattr(cashfree, "successful_payment_id", fake_payment_id)
    pay_all = f"{API}/me/parent/children/{asha['id']}/fees/pay-all"

    wrong = (await client.post(pay_all, headers=parent)).json()["payment_id"]
    orders[wrong].update(order_status="PAID", order_amount=1.0)
    response = await client.post(f"{API}/me/parent/children/{asha['id']}/pay-all/{wrong}/confirm", headers=parent)
    assert response.json()["error"]["code"] == "payment_not_verified"
    assert (await client.get(f"{API}/fees/students/{asha['id']}", headers=admin)).json()["balance"] == 2000.0

    # The tab closed: the signed webhook records the whole order.
    batch = (await client.post(pay_all, headers=parent)).json()["payment_id"]
    orders[batch]["order_status"] = "PAID"
    raw = json.dumps({"data": {"order": {"order_id": batch}}}).encode()
    timestamp = "1700000001"
    signature = base64.b64encode(hmac.new(b"cfsk_y", timestamp.encode() + raw, hashlib.sha256).digest()).decode()
    webhook = f"{API}/public/payments/cashfree/webhook"
    assert (await client.post(webhook, content=raw, headers={"x-webhook-timestamp": timestamp, "x-webhook-signature": "bad"})).status_code == 401
    assert (await client.post(webhook, content=raw, headers={"x-webhook-timestamp": timestamp, "x-webhook-signature": signature})).status_code == 204
    assert (await client.get(f"{API}/fees/students/{asha['id']}", headers=admin)).json()["balance"] == 0.0
