import zlib
from datetime import timedelta

from app.modules.alerts.service import today_ist
from tests.factories import auth_headers, create_school, create_user, login

PASSWORD = "Secret123!"
API = "/api/v1"
PERIODS = [
    {"label": "P1", "start_time": "09:00", "end_time": "09:45"},
    {"label": "P2", "start_time": "09:45", "end_time": "10:30"},
    {"label": "Break", "start_time": "10:30", "end_time": "10:45", "is_break": True},
    {"label": "P3", "start_time": "10:45", "end_time": "11:30"},
]


async def _setup(client, code):
    """Ravi teaches Maths in Grade 5 and Grade 6; Priya teaches English in Grade 5 (and is its class teacher)."""
    phone = f"9{zlib.crc32(code.encode()) % 10**9:09d}"
    school_id = await create_school(code=code)
    await create_user(school_id=school_id, email=f"{code}-admin@example.com".lower(), password=PASSWORD, role="admin")
    admin = auth_headers((await login(client, f"{code}-admin@example.com".lower(), PASSWORD)).json()["access_token"])

    async def teacher(key, name):
        body = {"email": f"{code}-{key}@example.com".lower(), "full_name": name, "password": PASSWORD}
        tid = (await client.post(f"{API}/teachers", json=body, headers=admin)).json()["id"]
        return tid, auth_headers((await login(client, body["email"], PASSWORD)).json()["access_token"])

    ravi_id, ravi = await teacher("ravi", "Ravi")
    priya_id, priya = await teacher("priya", "Priya")

    async def grade(name, tid):
        body = {"name": name, "section": "A", "academic_year": "2026", "class_teacher_id": tid}
        return (await client.post(f"{API}/classes", json=body, headers=admin)).json()

    g5, g6 = await grade("Grade 5", priya_id), await grade("Grade 6", ravi_id)
    maths = (await client.post(f"{API}/subjects", json={"name": "Maths"}, headers=admin)).json()
    english = (await client.post(f"{API}/subjects", json={"name": "English"}, headers=admin)).json()
    await client.put(f"{API}/classes/{g5['id']}/subjects/{maths['id']}", json={"teacher_id": ravi_id}, headers=admin)
    await client.put(f"{API}/classes/{g5['id']}/subjects/{english['id']}", json={"teacher_id": priya_id}, headers=admin)
    await client.put(f"{API}/classes/{g6['id']}/subjects/{maths['id']}", json={"teacher_id": ravi_id}, headers=admin)

    asha_body = {"admission_number": "A-1", "full_name": "Asha", "class_id": g5["id"], "mother": {"full_name": "Padma", "phone": phone}}
    asha = (await client.post(f"{API}/students", json=asha_body, headers=admin)).json()
    parent_password = (await client.post(f"{API}/students/{asha['id']}/parent-login", json={}, headers=admin)).json()["password"]
    parent = auth_headers((await client.post(f"{API}/auth/login", json={"phone": phone, "password": parent_password})).json()["access_token"])

    periods = (await client.put(f"{API}/timetable/periods", json={"periods": PERIODS}, headers=admin)).json()
    return {"admin": admin, "ravi": ravi, "priya": priya, "g5": g5, "g6": g6, "maths": maths, "english": english,
            "asha": asha, "parent": parent, "p": {p["label"]: p for p in periods}}


def _cell(ctx, weekday, period, subject):
    return {"weekday": weekday, "period_id": ctx["p"][period]["id"], "subject_id": ctx[subject]["id"]}


async def _save(client, ctx, cls, cells, who="admin"):
    return await client.put(f"{API}/timetable/classes/{ctx[cls]['id']}", json={"cells": cells}, headers=ctx[who])


async def test_periods_are_ordered_and_validated(db, client):
    ctx = await _setup(client, "TT1")
    assert list(ctx["p"]) == ["P1", "P2", "Break", "P3"]
    assert ctx["p"]["P1"]["start_time"] == "09:00" and ctx["p"]["Break"]["is_break"] is True

    overlap = [{"label": "A", "start_time": "09:00", "end_time": "10:00"}, {"label": "B", "start_time": "09:30", "end_time": "10:30"}]
    response = await client.put(f"{API}/timetable/periods", json={"periods": overlap}, headers=ctx["admin"])
    assert response.status_code == 400 and response.json()["error"]["code"] == "periods_overlap"
    backwards = [{"label": "A", "start_time": "10:00", "end_time": "09:00"}]
    assert (await client.put(f"{API}/timetable/periods", json={"periods": backwards}, headers=ctx["admin"])).status_code == 422
    assert (await client.put(f"{API}/timetable/periods", json={"periods": PERIODS}, headers=ctx["ravi"])).status_code == 403


async def test_class_grid_and_everyones_view(db, client):
    ctx = await _setup(client, "TT2")
    saved = await _save(client, ctx, "g5", [_cell(ctx, 0, "P1", "maths"), _cell(ctx, 0, "P2", "english"), _cell(ctx, 1, "P1", "english")])
    assert saved.status_code == 200, saved.text
    cells = {(c["weekday"], c["period_id"]): (c["subject_name"], c["teacher_name"]) for c in saved.json()["cells"]}
    assert cells[(0, ctx["p"]["P1"]["id"])] == ("Maths", "Ravi")

    parent_view = (await client.get(f"{API}/timetable/mine", params={"student_id": ctx["asha"]["id"]}, headers=ctx["parent"])).json()
    assert parent_view["title"] == "Grade 5 - A" and len(parent_view["cells"]) == 3
    ravi_week = (await client.get(f"{API}/timetable/mine", headers=ctx["ravi"])).json()
    assert [(c["class_label"], c["subject_name"]) for c in ravi_week["cells"]] == [("Grade 5 - A", "Maths")]

    # A subject not taught in the class, a break, and non-admins are refused.
    assert (await _save(client, ctx, "g6", [_cell(ctx, 0, "P1", "english")])).status_code == 400
    assert (await _save(client, ctx, "g5", [_cell(ctx, 0, "Break", "maths")])).json()["error"]["code"] == "break_period"
    assert (await _save(client, ctx, "g5", [], who="priya")).status_code == 403
    assert (await client.get(f"{API}/timetable/classes/{ctx['g5']['id']}", headers=ctx["parent"])).status_code == 403


async def test_teacher_clash_is_refused(db, client):
    ctx = await _setup(client, "TT3")
    assert (await _save(client, ctx, "g5", [_cell(ctx, 0, "P1", "maths")])).status_code == 200
    clash = await _save(client, ctx, "g6", [_cell(ctx, 0, "P1", "maths")])
    assert clash.status_code == 409
    assert clash.json()["error"]["message"] == "Ravi already teaches Grade 5 - A on Monday, P1."
    assert (await _save(client, ctx, "g6", [_cell(ctx, 0, "P2", "maths")])).status_code == 200
    # Re-saving a class's own grid is not a clash with itself.
    assert (await _save(client, ctx, "g5", [_cell(ctx, 0, "P1", "maths")])).status_code == 200


async def test_removing_or_breaking_a_period_clears_its_cells(db, client):
    ctx = await _setup(client, "TT4")
    await _save(client, ctx, "g5", [_cell(ctx, 0, "P1", "maths"), _cell(ctx, 0, "P3", "english")])
    kept = [{**ctx["p"]["P1"], "is_break": True}, ctx["p"]["P2"]]
    periods = (await client.put(f"{API}/timetable/periods", json={"periods": kept}, headers=ctx["admin"])).json()
    assert [p["label"] for p in periods] == ["P1", "P2"]
    assert (await client.get(f"{API}/timetable/classes/{ctx['g5']['id']}", headers=ctx["admin"])).json()["cells"] == []


async def test_calendar_entries_and_notifications(db, client):
    ctx = await _setup(client, "CAL1")
    today = today_ist()
    body = {"title": "Dussehra", "start_date": (today + timedelta(days=3)).isoformat(), "end_date": (today + timedelta(days=5)).isoformat()}
    created = await client.post(f"{API}/calendar", json=body, headers=ctx["admin"])
    assert created.status_code == 201 and created.json()["days"] == 3
    await client.post(f"{API}/calendar", json={"title": "Sports day", "kind": "event", "start_date": today.isoformat(), "notify": False}, headers=ctx["admin"])

    window = {"start": today.isoformat(), "end": (today + timedelta(days=30)).isoformat()}
    for who in ("parent", "ravi"):
        assert [h["title"] for h in (await client.get(f"{API}/calendar", params=window, headers=ctx[who])).json()] == ["Sports day", "Dussehra"]
    bell = [n["title"] for n in (await client.get(f"{API}/notifications", headers=ctx["parent"])).json()["items"]]
    assert "Holiday: Dussehra" in bell and "Event: Sports day" not in bell

    assert (await client.post(f"{API}/calendar", json=body, headers=ctx["ravi"])).status_code == 403
    backwards = {**body, "end_date": today.isoformat()}
    assert (await client.post(f"{API}/calendar", json=backwards, headers=ctx["admin"])).status_code == 422
    too_wide = {"start": today.isoformat(), "end": (today + timedelta(days=500)).isoformat()}
    assert (await client.get(f"{API}/calendar", params=too_wide, headers=ctx["admin"])).status_code == 400
    assert (await client.delete(f"{API}/calendar/{created.json()['id']}", headers=ctx["admin"])).status_code == 204


async def test_dashboards_know_about_holidays_and_lessons(db, client):
    ctx = await _setup(client, "CAL2")
    today = today_ist()
    if today.weekday() <= 5:
        await _save(client, ctx, "g5", [_cell(ctx, today.weekday(), "P2", "maths"), _cell(ctx, today.weekday(), "P1", "english")])
        lessons = (await client.get(f"{API}/dashboard/teacher", headers=ctx["ravi"])).json()["lessons_today"]
        assert lessons == [{"period": "P2", "start_time": "09:45", "end_time": "10:30", "subject_name": "Maths", "class_label": "Grade 5 - A"}]

    assert len((await client.get(f"{API}/dashboard/admin", headers=ctx["admin"])).json()["unmarked_classes"]) == 2
    await client.post(f"{API}/calendar", json={"title": "Gandhi Jayanti", "start_date": today.isoformat(), "notify": False}, headers=ctx["admin"])
    admin_view = (await client.get(f"{API}/dashboard/admin", headers=ctx["admin"])).json()
    assert admin_view["holiday"] == "Gandhi Jayanti" and admin_view["unmarked_classes"] == []
    teacher_view = (await client.get(f"{API}/dashboard/teacher", headers=ctx["ravi"])).json()
    assert teacher_view["holiday"] == "Gandhi Jayanti" and teacher_view["lessons_today"] == []
