from datetime import timedelta

from app.modules.alerts.service import today_ist
from app.modules.audit import service as audit
from tests.factories import auth_headers, create_user, login
from tests.test_exams import _entry, _save, _setup

API = "/api/v1"


async def _log(client, headers, **params):
    response = await client.get(f"{API}/audit-log", params=params, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def test_changed_marks_are_logged_but_first_entries_are_not(db, client):
    ctx = await _setup(client, "AUD1")
    maths = ctx["papers"]["Maths"]
    await _save(client, ctx["ravi"], maths, [_entry(ctx, "Asha", 40), _entry(ctx, "Bala", 30)])
    assert await _log(client, ctx["admin"]) == []

    await _save(client, ctx["ravi"], maths, [_entry(ctx, "Asha", 45), _entry(ctx, "Bala", 30), _entry(ctx, "Chitra", absent=True)])
    entries = await _log(client, ctx["admin"])
    assert len(entries) == 1
    entry = entries[0]
    assert (entry["action"], entry["area"], entry["user_name"]) == ("marks.changed", "Marks & exams", "Ravi")
    assert "Asha 40→45" in entry["summary"] and "Unit Test 1" in entry["summary"]
    assert entry["details"] == [{"student_id": ctx["students"]["Asha"]["id"], "from": "40", "to": "45", "student": "Asha"}]

    await client.post(f"{API}/exams/{ctx['exam']['id']}/publish", headers=ctx["admin"])
    assert [e["action"] for e in await _log(client, ctx["admin"], area="marks")][0] == "marks.published"


async def test_attendance_edits_and_fee_actions_are_logged(db, client):
    ctx = await _setup(client, "AUD2")
    asha, bala = ctx["students"]["Asha"], ctx["students"]["Bala"]
    day = (today_ist() - timedelta(days=1)).isoformat()
    url = f"{API}/classes/{ctx['grade']['id']}/attendance"
    await client.post(url, json={"date": day, "records": [{"student_id": asha["id"], "status": "absent"}, {"student_id": bala["id"], "status": "present"}]}, headers=ctx["ravi"])
    await client.post(url, json={"date": day, "records": [{"student_id": asha["id"], "status": "present"}, {"student_id": bala["id"], "status": "present"}]}, headers=ctx["ravi"])
    attendance = await _log(client, ctx["admin"], area="attendance")
    assert len(attendance) == 1 and "Asha absent→present" in attendance[0]["summary"]

    item = (await client.post(
        f"{API}/fees/items",
        json={"name": "Tuition", "academic_year": "2026", "amount": "1000", "due_date": (today_ist() + timedelta(days=5)).isoformat(), "class_ids": [ctx["grade"]["id"]]},
        headers=ctx["admin"],
    )).json()[0]
    line = next(l for l in (await client.get(f"{API}/fees/students/{asha['id']}", headers=ctx["admin"])).json()["lines"] if l["fee_item_id"] == item["id"])
    await client.put(f"{API}/fees/student-fees/{line['id']}/discount", json={"discount": "100", "note": "Sibling"}, headers=ctx["admin"])
    payment = (await client.post(f"{API}/fees/payments", json={"student_fee_id": line["id"], "amount": "500", "method": "cash"}, headers=ctx["admin"])).json()
    await client.post(f"{API}/fees/payments/{payment['id']}/cancel", json={"reason": "Entered twice"}, headers=ctx["admin"])
    fees = await _log(client, ctx["admin"], area="fees")
    assert [e["action"] for e in fees] == ["fees.payment_cancelled", "fees.payment", "fees.concession"]
    assert "Asha (A-1)" in fees[0]["summary"] and "Entered twice" in fees[0]["summary"]
    assert (await _log(client, ctx["admin"], q="Sibling"))[0]["action"] == "fees.concession"


async def test_who_sees_the_log(db, client):
    ctx = await _setup(client, "AUD3")
    other = await _setup(client, "AUD4")
    await client.delete(f"{API}/students/{ctx['students']['Asha']['id']}", headers=ctx["admin"])  # marked as left
    assert [e["action"] for e in await _log(client, ctx["admin"])] == ["students.changed"]
    assert await _log(client, other["admin"]) == []
    assert (await client.get(f"{API}/audit-log", headers=ctx["ravi"])).status_code == 403

    await create_user(school_id=None, email="root-aud@example.com", password="Secret123!", role="super_admin")
    root = auth_headers((await login(client, "root-aud@example.com", "Secret123!")).json()["access_token"])
    assert len(await _log(client, root)) == 1
    assert (await client.get(f"{API}/audit-log", params={"area": "nope"}, headers=root)).status_code == 422


async def test_a_failing_audit_write_never_breaks_the_action(db, client, monkeypatch):
    ctx = await _setup(client, "AUD5")

    async def broken(*_args, **_kwargs):
        raise RuntimeError("audit table missing")

    monkeypatch.setattr(audit, "execute", broken)
    response = await client.delete(f"{API}/students/{ctx['students']['Bala']['id']}", headers=ctx["admin"])
    assert response.status_code == 200 and response.json()["status"] == "left"
