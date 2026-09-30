from datetime import timedelta

from app.modules.alerts.service import today_ist
from tests.factories import auth_headers, create_school, create_user, login

PASSWORD = "Secret123!"
API = "/api/v1"


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

    async def grade(name, teacher_id):
        return (await client.post(f"{API}/classes", json={"name": name, "section": "A", "academic_year": "2026", "class_teacher_id": teacher_id}, headers=admin)).json()

    grade5, grade6 = await grade("Grade 5", ravi_id), await grade("Grade 6", priya_id)

    async def student(cls, adm, name):
        return (await client.post(f"{API}/students", json={"admission_number": adm, "full_name": name, "class_id": cls["id"]}, headers=admin)).json()

    students = [await student(grade5, "A-1", "Asha"), await student(grade5, "A-2", "Bala"), await student(grade6, "B-1", "Chitra")]
    return {"admin": admin, "ravi": ravi, "priya": priya, "grade5": grade5, "grade6": grade6, "students": students}


async def _mark(client, headers, class_id, day, records):
    response = await client.post(f"{API}/classes/{class_id}/attendance", json={"date": day.isoformat(), "records": records}, headers=headers)
    assert response.status_code == 200, response.text


async def test_admin_dashboard_shows_today_at_a_glance(db, client):
    ctx = await _setup(client, "DSH1")
    today = today_ist()
    asha, bala, _ = ctx["students"]
    await _mark(client, ctx["ravi"], ctx["grade5"]["id"], today, [{"student_id": asha["id"], "status": "present"}, {"student_id": bala["id"], "status": "absent"}])
    await client.post(f"{API}/staff-punch/in", headers=ctx["ravi"])

    item = (await client.post(
        f"{API}/fees/items",
        json={"name": "Tuition", "term_label": "Term 1", "academic_year": "2026", "amount": "1000",
              "due_date": (today - timedelta(days=1)).isoformat(), "class_ids": [ctx["grade5"]["id"]]},
        headers=ctx["admin"],
    )).json()[0]
    lines = (await client.get(f"{API}/fees/students/{asha['id']}", headers=ctx["admin"])).json()["lines"]
    line = next(l for l in lines if l["fee_item_id"] == item["id"])
    paid = await client.post(f"{API}/fees/payments", json={"student_fee_id": line["id"], "amount": "400", "method": "cash"}, headers=ctx["admin"])
    assert paid.status_code == 201, paid.text

    data = (await client.get(f"{API}/dashboard/admin", headers=ctx["admin"])).json()
    assert (data["students"], data["teachers"]) == (3, 2)
    assert (data["classes_marked"], data["classes_total"], data["present"], data["absent"]) == (1, 2, 1, 1)
    assert [c["name"] for c in data["unmarked_classes"]] == ["Grade 6"]
    assert data["unmarked_classes"][0]["class_teacher_name"] == "Priya"
    assert data["trend"][-1] == {"date": today.isoformat(), "percent": 50.0, "marked": 1}
    assert len(data["trend"]) == 7 and all(d["percent"] is None for d in data["trend"][:-1])
    assert data["staff_punched_in"] == 1
    assert (data["fees_collected_today"], data["fees_collected_month"]) == (400.0, 400.0)
    assert (data["fees_outstanding"], data["fees_overdue"]) == (1600.0, 1600.0)


async def test_teacher_dashboard_is_their_own_class(db, client):
    ctx = await _setup(client, "DSH2")
    data = (await client.get(f"{API}/dashboard/teacher", headers=ctx["ravi"])).json()
    assert [c["name"] for c in data["my_classes"]] == ["Grade 5"]
    assert data["my_classes"][0]["marked"] is False and data["my_classes"][0]["students"] == 2
    assert data["punch"]["punch_in_at"] is None
    assert data["marks_to_enter"] == []


async def test_dashboards_are_role_checked(db, client):
    ctx = await _setup(client, "DSH3")
    assert (await client.get(f"{API}/dashboard/admin", headers=ctx["ravi"])).status_code == 403
    assert (await client.get(f"{API}/dashboard/teacher", headers=ctx["admin"])).status_code == 403
    assert (await client.get(f"{API}/dashboard/admin")).status_code == 401
