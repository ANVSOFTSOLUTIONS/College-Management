from datetime import timedelta

from app.modules.alerts import service as alerts
from tests.factories import auth_headers, create_class, create_school, create_teacher, create_user, login

PASSWORD = "Secret123!"
API = "/api/v1"


async def _setup(client, code):
    school_id = await create_school(code=code)
    await create_user(school_id=school_id, email=f"{code}-admin@example.com".lower(), password=PASSWORD, role="admin")
    teacher_user = await create_user(school_id=school_id, email=f"{code}-t@example.com".lower(), password=PASSWORD, role="teacher")
    teacher_id = await create_teacher(school_id=school_id, user_id=teacher_user)
    grade5 = await create_class(school_id=school_id, teacher_id=teacher_id, name="Grade 5")
    grade6 = await create_class(school_id=school_id, teacher_id=teacher_id, name="Grade 6")
    admin = auth_headers((await login(client, f"{code}-admin@example.com".lower(), PASSWORD)).json()["access_token"])
    teacher = auth_headers((await login(client, f"{code}-t@example.com".lower(), PASSWORD)).json()["access_token"])

    async def student(class_id, number, name, phone=None):
        body = {"admission_number": number, "full_name": name, "class_id": class_id}
        if phone:
            body["father"] = {"full_name": f"{name}'s father", "phone": phone}
        return (await client.post(f"{API}/students", json=body, headers=admin)).json()

    asha = await student(grade5, "A-1", "Asha", "9848022338")
    bala = await student(grade5, "A-2", "Bala")
    chitra = await student(grade6, "B-1", "Chitra")
    return {"admin": admin, "teacher": teacher, "grade5": grade5, "grade6": grade6, "asha": asha, "bala": bala, "chitra": chitra}


async def _fee(client, ctx, *, classes, amount="5000", due=None, name="Term 1 tuition"):
    due = due or (alerts.today_ist() + timedelta(days=10))
    response = await client.post(
        f"{API}/fees/items",
        json={"name": name, "term_label": "Term 1", "academic_year": "2026", "amount": amount,
              "due_date": due.isoformat(), "class_ids": classes},
        headers=ctx["admin"],
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _account(client, ctx, student):
    return (await client.get(f"{API}/fees/students/{student['id']}", headers=ctx["admin"])).json()


async def _pay(client, ctx, student_fee_id, amount, method="cash", **extra):
    return await client.post(
        f"{API}/fees/payments",
        json={"student_fee_id": student_fee_id, "amount": amount, "method": method, **extra},
        headers=ctx["admin"],
    )


async def test_fee_item_bills_every_student_in_the_chosen_classes(db, client):
    ctx = await _setup(client, "FEE1")
    items = await _fee(client, ctx, classes=[ctx["grade5"], ctx["grade6"]])
    assert [(i["class_name"], i["student_count"], i["pending"]) for i in items] == [("Grade 5", 2, 10000.0), ("Grade 6", 1, 5000.0)]

    account = await _account(client, ctx, ctx["asha"])
    assert (account["total"], account["balance"]) == (5000.0, 5000.0)
    assert account["lines"][0]["status"] == "due"


async def test_payments_receipts_and_balances(db, client):
    ctx = await _setup(client, "FEE2")
    await _fee(client, ctx, classes=[ctx["grade5"]])
    line = (await _account(client, ctx, ctx["asha"]))["lines"][0]

    first = (await _pay(client, ctx, line["id"], "2000", method="upi", reference="UPI-123")).json()
    assert first["receipt_number"].startswith("RCPT-")
    assert first["receipt_number"].endswith("-00001")
    second = (await _pay(client, ctx, line["id"], "3000")).json()
    assert second["receipt_number"].endswith("-00002")

    account = await _account(client, ctx, ctx["asha"])
    assert (account["paid"], account["balance"], account["lines"][0]["status"]) == (5000.0, 0.0, "paid")

    too_much = await _pay(client, ctx, line["id"], "1")
    assert too_much.status_code == 400
    assert too_much.json()["error"]["code"] == "amount_exceeds_balance"

    receipt = (await client.get(f"{API}/fees/payments/{first['id']}/receipt", headers=ctx["admin"])).json()
    assert receipt["student_name"] == "Asha"
    assert receipt["amount"] == 2000.0
    assert receipt["reference"] == "UPI-123"
    assert receipt["balance_after"] == 0.0


async def test_cancelled_payment_restores_the_balance(db, client):
    ctx = await _setup(client, "FEE3")
    await _fee(client, ctx, classes=[ctx["grade5"]])
    line = (await _account(client, ctx, ctx["asha"]))["lines"][0]
    payment = (await _pay(client, ctx, line["id"], "5000")).json()

    assert (await client.post(f"{API}/fees/payments/{payment['id']}/cancel", json={"reason": "ab"}, headers=ctx["admin"])).status_code == 422
    cancelled = (
        await client.post(f"{API}/fees/payments/{payment['id']}/cancel", json={"reason": "Entered twice"}, headers=ctx["admin"])
    ).json()
    assert cancelled["status"] == "cancelled"
    assert (await _account(client, ctx, ctx["asha"]))["balance"] == 5000.0
    again = await client.post(f"{API}/fees/payments/{payment['id']}/cancel", json={"reason": "Again"}, headers=ctx["admin"])
    assert again.status_code == 409


async def test_discount_rules(db, client):
    ctx = await _setup(client, "FEE4")
    await _fee(client, ctx, classes=[ctx["grade5"]])
    line = (await _account(client, ctx, ctx["asha"]))["lines"][0]
    await _pay(client, ctx, line["id"], "4000")

    too_big = await client.put(f"{API}/fees/student-fees/{line['id']}/discount", json={"discount": "1500"}, headers=ctx["admin"])
    assert too_big.status_code == 400
    account = (
        await client.put(
            f"{API}/fees/student-fees/{line['id']}/discount", json={"discount": "1000", "note": "Sibling concession"}, headers=ctx["admin"]
        )
    ).json()
    assert (account["balance"], account["lines"][0]["status"], account["lines"][0]["discount_note"]) == (0.0, "paid", "Sibling concession")


async def test_fee_item_amount_locks_after_payments(db, client):
    ctx = await _setup(client, "FEE5")
    (item,) = await _fee(client, ctx, classes=[ctx["grade5"]])
    changed = (await client.patch(f"{API}/fees/items/{item['id']}", json={"amount": "6000"}, headers=ctx["admin"])).json()
    assert changed["pending"] == 12000.0

    line = (await _account(client, ctx, ctx["asha"]))["lines"][0]
    await _pay(client, ctx, line["id"], "100")
    blocked = await client.patch(f"{API}/fees/items/{item['id']}", json={"amount": "7000"}, headers=ctx["admin"])
    assert blocked.status_code == 409
    assert (await client.delete(f"{API}/fees/items/{item['id']}", headers=ctx["admin"])).status_code == 409
    renamed = await client.patch(f"{API}/fees/items/{item['id']}", json={"name": "Term 1 fees"}, headers=ctx["admin"])
    assert renamed.json()["name"] == "Term 1 fees"


async def test_sync_bills_students_who_joined_later(db, client):
    ctx = await _setup(client, "FEE6")
    (item,) = await _fee(client, ctx, classes=[ctx["grade5"]])
    await client.post(
        f"{API}/students", json={"admission_number": "A-3", "full_name": "Deepa", "class_id": ctx["grade5"]}, headers=ctx["admin"]
    )
    synced = (await client.post(f"{API}/fees/items/{item['id']}/sync", headers=ctx["admin"])).json()
    assert synced["student_count"] == 3


async def test_report_and_overdue_reminders(db, client):
    ctx = await _setup(client, "FEE7")
    today = alerts.today_ist()
    await _fee(client, ctx, classes=[ctx["grade5"], ctx["grade6"]], amount="1000", due=today - timedelta(days=5), name="Admission fee")
    await _fee(client, ctx, classes=[ctx["grade5"]], amount="2000", due=today + timedelta(days=20))
    bala_line = next(line for line in (await _account(client, ctx, ctx["bala"]))["lines"] if line["name"] == "Admission fee")
    await _pay(client, ctx, bala_line["id"], "1000")

    report = (await client.get(f"{API}/fees/report", params={"class_id": ctx["grade5"]}, headers=ctx["admin"])).json()
    rows = {s["full_name"]: s for s in report["students"]}
    assert (report["total"], report["collected"], report["balance"], report["overdue"]) == (6000.0, 1000.0, 5000.0, 1000.0)
    assert (rows["Asha"]["overdue"], rows["Bala"]["overdue"], rows["Asha"]["primary_contact_phone"]) == (1000.0, 0.0, "9848022338")

    result = (await client.post(f"{API}/fees/reminders", json={"only_overdue": True}, headers=ctx["admin"])).json()
    assert result == {"students_with_dues": 2, "alerts_created": 2}  # Asha and Chitra are overdue; Bala paid
    again = (await client.post(f"{API}/fees/reminders", json={"only_overdue": True}, headers=ctx["admin"])).json()
    assert again["alerts_created"] == 0  # once a day

    alert_list = (await client.get(f"{API}/parent-alerts", headers=ctx["admin"])).json()
    asha_alert = next(a for a in alert_list if a["student_name"] == "Asha")
    assert asha_alert["kind"] == "fee"
    assert "Rs.1,000.00" in asha_alert["message"] and "overdue" in asha_alert["message"]


async def test_fees_are_admin_only_and_school_scoped(db, client):
    ctx = await _setup(client, "FEE8")
    other = await _setup(client, "FEE9")
    await _fee(client, ctx, classes=[ctx["grade5"]])
    assert (await client.get(f"{API}/fees/items", headers=ctx["teacher"])).status_code == 403
    assert (await client.get(f"{API}/fees/students/{ctx['asha']['id']}", headers=other["admin"])).status_code == 404
    line = (await _account(client, ctx, ctx["asha"]))["lines"][0]
    assert (await _pay(client, other, line["id"], "10")).status_code == 404
    cross = await client.post(
        f"{API}/fees/items",
        json={"name": "X", "academic_year": "2026", "amount": "10", "due_date": "2026-12-01", "class_ids": [ctx["grade5"]]},
        headers=other["admin"],
    )
    assert cross.status_code == 400


async def test_money_validation(db, client):
    ctx = await _setup(client, "FEEA")
    bad = await client.post(
        f"{API}/fees/items",
        json={"name": "X", "academic_year": "2026", "amount": "10.555", "due_date": "2026-12-01", "class_ids": [ctx["grade5"]]},
        headers=ctx["admin"],
    )
    assert bad.status_code == 422
    await _fee(client, ctx, classes=[ctx["grade5"]])
    line = (await _account(client, ctx, ctx["asha"]))["lines"][0]
    assert (await _pay(client, ctx, line["id"], "0")).status_code == 422
    assert (await _pay(client, ctx, line["id"], "10", method="online")).status_code == 422  # online only via the gateway
