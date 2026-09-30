from datetime import date, timedelta

from app.modules.alerts.service import today_ist
from tests.factories import auth_headers, create_school, create_user, login

PASSWORD = "Secret123!"
API = "/api/v1"
AUGUST = "2026-08-01"  # 26 Mon–Sat days, 25 working days once 15 Aug is a holiday


async def _setup(client, code):
    school_id = await create_school(code=code)
    await create_user(school_id=school_id, email=f"{code}-admin@example.com".lower(), password=PASSWORD, role="admin")
    admin = auth_headers((await login(client, f"{code}-admin@example.com".lower(), PASSWORD)).json()["access_token"])

    async def teacher(key, name):
        body = {"email": f"{code}-{key}@example.com".lower(), "full_name": name, "password": PASSWORD}
        tid = (await client.post(f"{API}/teachers", json=body, headers=admin)).json()["id"]
        return tid, auth_headers((await login(client, body["email"], PASSWORD)).json()["access_token"])

    ravi_id, ravi = await teacher("ravi", "Ravi")
    priya_id, priya = await teacher("priya", "Priya")
    await teacher("kiran", "Kiran")  # no salary set
    await client.post(f"{API}/calendar", json={"title": "Independence Day", "start_date": "2026-08-15", "notify": False}, headers=admin)
    return {"admin": admin, "ravi": ravi, "ravi_id": ravi_id, "priya": priya, "priya_id": priya_id}


async def _mark(client, ctx, day, records):
    response = await client.post(f"{API}/staff-attendance", json={"date": day, "records": records}, headers=ctx["admin"])
    assert response.status_code == 200, response.text


async def _salary(client, ctx, teacher, basic, allowances="0", deductions="0"):
    body = {"basic": basic, "allowances": allowances, "deductions": deductions}
    return await client.put(f"{API}/payroll/salaries/{ctx[teacher + '_id']}", json=body, headers=ctx["admin"])


async def test_salaries(db, client):
    ctx = await _setup(client, "PAY1")
    saved = (await _salary(client, ctx, "ravi", "20000", "5000", "1800")).json()
    assert (saved["gross"], saved["deductions"]) == (25000.0, 1800.0)
    listed = {s["full_name"]: s for s in (await client.get(f"{API}/payroll/salaries", headers=ctx["admin"])).json()}
    assert listed["Kiran"]["basic"] is None and listed["Ravi"]["basic"] == 20000.0
    assert (await _salary(client, ctx, "ravi", "1000", "0", "5000")).status_code == 400
    assert (await client.put(f"{API}/payroll/salaries/{ctx['ravi_id']}", json={"basic": "-5"}, headers=ctx["admin"])).status_code == 422
    assert (await client.get(f"{API}/payroll/salaries", headers=ctx["ravi"])).status_code == 403


async def test_generate_uses_attendance_and_holidays(db, client):
    ctx = await _setup(client, "PAY2")
    await _salary(client, ctx, "ravi", "20000", "5000", "1800")
    await _salary(client, ctx, "priya", "30000")
    await _mark(client, ctx, "2026-08-03", [{"teacher_id": ctx["ravi_id"], "status": "present"}, {"teacher_id": ctx["priya_id"], "status": "absent"}])
    await _mark(client, ctx, "2026-08-04", [{"teacher_id": ctx["ravi_id"], "status": "late"}, {"teacher_id": ctx["priya_id"], "status": "absent"}])
    await _mark(client, ctx, "2026-08-05", [{"teacher_id": ctx["ravi_id"], "status": "leave"}])

    month = (await client.post(f"{API}/payroll/months/{AUGUST}/generate", headers=ctx["admin"])).json()
    assert month["month"] == "2026-08" and month["without_salary"] == ["Kiran"]
    slips = {s["full_name"]: s for s in month["slips"]}
    ravi, priya = slips["Ravi"], slips["Priya"]
    assert (ravi["working_days"], ravi["days_present"], ravi["days_leave"], ravi["days_absent"], ravi["days_unmarked"]) == (25, 2, 1, 0, 22)
    assert (ravi["gross"], ravi["lop_amount"], ravi["net"]) == (25000.0, 0.0, 23200.0)
    assert ravi["net_in_words"] == "Rupees Twenty-Three Thousand Two Hundred Only"
    # Two absent days at 30000 / 25 = 1200 a day.
    assert (priya["lop_days"], priya["lop_amount"], priya["net"]) == (2.0, 2400.0, 27600.0)
    assert month["total_net"] == 50800.0 and month["total_paid"] == 0

    # The admin forgives one day, then pays; the teacher is told and can see it.
    adjusted = (await client.patch(f"{API}/payroll/slips/{priya['id']}", json={"lop_days": "1", "note": "One day excused"}, headers=ctx["admin"])).json()
    assert (adjusted["lop_amount"], adjusted["net"]) == (1200.0, 28800.0)
    assert (await client.get(f"{API}/payroll/mine", headers=ctx["priya"])).json() == []
    paid = (await client.post(f"{API}/payroll/slips/{priya['id']}/pay", json={"payment_mode": "upi"}, headers=ctx["admin"])).json()
    assert (paid["status"], paid["payment_mode_label"], paid["paid_on"]) == ("paid", "UPI", today_ist().isoformat())
    mine = (await client.get(f"{API}/payroll/mine", headers=ctx["priya"])).json()
    assert [s["net"] for s in mine] == [28800.0]
    bell = [n["title"] for n in (await client.get(f"{API}/notifications", headers=ctx["priya"])).json()["items"]]
    assert "Salary for August 2026 paid" in bell

    # Paid payslips are locked: regenerating skips them and edits are refused.
    await _mark(client, ctx, "2026-08-06", [{"teacher_id": ctx["priya_id"], "status": "absent"}])
    regenerated = {s["full_name"]: s for s in (await client.post(f"{API}/payroll/months/{AUGUST}/generate", headers=ctx["admin"])).json()["slips"]}
    assert regenerated["Priya"]["net"] == 28800.0
    assert (await client.patch(f"{API}/payroll/slips/{priya['id']}", json={"lop_days": "0"}, headers=ctx["admin"])).status_code == 409
    assert (await client.post(f"{API}/payroll/slips/{priya['id']}/pay", json={}, headers=ctx["admin"])).status_code == 409
    reverted = (await client.post(f"{API}/payroll/slips/{priya['id']}/revert", headers=ctx["admin"])).json()
    assert reverted["status"] == "draft"


async def test_payslip_privacy_and_rules(db, client):
    ctx = await _setup(client, "PAY3")
    await _salary(client, ctx, "ravi", "20000")
    await _salary(client, ctx, "priya", "30000")
    slips = {s["full_name"]: s for s in (await client.post(f"{API}/payroll/months/{AUGUST}/generate", headers=ctx["admin"])).json()["slips"]}
    ravi = slips["Ravi"]
    await client.post(f"{API}/payroll/slips/{ravi['id']}/pay", json={"payment_mode": "bank"}, headers=ctx["admin"])

    printable = (await client.get(f"{API}/payroll/slips/{ravi['id']}", headers=ctx["ravi"])).json()
    assert printable["school"]["name"] and printable["full_name"] == "Ravi"
    assert (await client.get(f"{API}/payroll/slips/{ravi['id']}", headers=ctx["priya"])).status_code == 404  # someone else's
    assert (await client.get(f"{API}/payroll/slips/{slips['Priya']['id']}", headers=ctx["priya"])).status_code == 404  # not paid yet
    assert (await client.post(f"{API}/payroll/months/{AUGUST}/generate", headers=ctx["ravi"])).status_code == 403

    future = (date.today().replace(day=1) + timedelta(days=62)).isoformat()
    assert (await client.post(f"{API}/payroll/months/{future}/generate", headers=ctx["admin"])).status_code == 400
    too_many = await client.patch(f"{API}/payroll/slips/{slips['Priya']['id']}", json={"lop_days": "26"}, headers=ctx["admin"])
    assert too_many.status_code == 400
    tomorrow = (today_ist() + timedelta(days=1)).isoformat()
    assert (await client.post(f"{API}/payroll/slips/{slips['Priya']['id']}/pay", json={"paid_on": tomorrow}, headers=ctx["admin"])).status_code == 400

    other = await _setup(client, "PAY4")
    assert (await client.get(f"{API}/payroll/slips/{ravi['id']}", headers=other["admin"])).status_code == 404
