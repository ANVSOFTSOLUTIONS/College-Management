from datetime import datetime, timedelta, timezone

from app.modules.alerts.service import IST, today_ist
from app.modules.staff_attendance import punch
from tests.factories import auth_headers, create_school, create_user, login

PASSWORD = "Secret123!"
API = "/api/v1"


def _at(hour, minute):
    """A moment today at the given IST time, as punch._now() would return it."""
    return datetime.combine(today_ist(), datetime.min.time(), tzinfo=IST).replace(hour=hour, minute=minute).astimezone(timezone.utc)


async def _setup(client, code):
    school_id = await create_school(code=code)
    await create_user(school_id=school_id, email=f"{code}-admin@example.com".lower(), password=PASSWORD, role="admin")
    admin = auth_headers((await login(client, f"{code}-admin@example.com".lower(), PASSWORD)).json()["access_token"])

    async def teacher(key, name):
        body = {"email": f"{code}-{key}@example.com".lower(), "full_name": name, "password": PASSWORD}
        tid = (await client.post(f"{API}/teachers", json=body, headers=admin)).json()["id"]
        return tid, auth_headers((await login(client, body["email"], PASSWORD)).json()["access_token"])

    ravi_id, ravi = await teacher("ravi", "Ravi")  # class teacher of Grade 5
    priya_id, priya = await teacher("priya", "Priya")  # not a class teacher
    grade = (await client.post(f"{API}/classes", json={"name": "Grade 5", "section": "A", "academic_year": "2026", "class_teacher_id": ravi_id}, headers=admin)).json()
    asha = (await client.post(f"{API}/students", json={"admission_number": "A-1", "full_name": "Asha", "class_id": grade["id"], "mother": {"full_name": "Padma", "phone": "9848022338"}}, headers=admin)).json()
    parent_password = (await client.post(f"{API}/students/{asha['id']}/parent-login", json={}, headers=admin)).json()["password"]
    parent = auth_headers((await client.post(f"{API}/auth/login", json={"phone": "9848022338", "password": parent_password})).json()["access_token"])
    return {"admin": admin, "ravi": ravi, "ravi_id": ravi_id, "priya": priya, "priya_id": priya_id, "grade": grade, "asha": asha, "parent": parent}


async def _notes(client, headers):
    return (await client.get(f"{API}/notifications", headers=headers)).json()


# --- Punch in / out ---------------------------------------------------------------


async def test_punch_in_on_time_then_out_marks_attendance(db, client, monkeypatch):
    ctx = await _setup(client, "PUN1")
    monkeypatch.setattr(punch, "_now", lambda: _at(8, 55))
    first = (await client.post(f"{API}/staff-punch/in", headers=ctx["ravi"])).json()
    assert first["is_late"] is False and first["punch_in_at"]
    assert (await client.post(f"{API}/staff-punch/in", headers=ctx["ravi"])).status_code == 409

    monkeypatch.setattr(punch, "_now", lambda: _at(16, 25))
    out = (await client.post(f"{API}/staff-punch/out", headers=ctx["ravi"])).json()
    assert out["worked_minutes"] == 7 * 60 + 30
    assert (await client.post(f"{API}/staff-punch/out", headers=ctx["ravi"])).status_code == 409

    staff = (await client.get(f"{API}/staff-attendance", params={"date": today_ist().isoformat()}, headers=ctx["admin"])).json()
    assert {e["full_name"]: e["status"] for e in staff["entries"]} == {"Ravi": "present", "Priya": None}
    day = (await client.get(f"{API}/staff-punch", params={"date": today_ist().isoformat()}, headers=ctx["admin"])).json()
    rows = {r["full_name"]: r for r in day}
    assert rows["Ravi"]["punch"]["worked_minutes"] == 450 and rows["Priya"]["punch"] is None


async def test_late_punch_uses_school_start_time_and_grace(db, client, monkeypatch):
    ctx = await _setup(client, "PUN2")
    saved = (await client.put(f"{API}/school-settings", json={"day_starts_at": "08:30", "late_grace_minutes": 10}, headers=ctx["admin"])).json()
    assert saved == {"day_starts_at": "08:30", "late_grace_minutes": 10}
    monkeypatch.setattr(punch, "_now", lambda: _at(8, 41))
    assert (await client.post(f"{API}/staff-punch/in", headers=ctx["ravi"])).json()["is_late"] is True
    monkeypatch.setattr(punch, "_now", lambda: _at(8, 40))
    assert (await client.post(f"{API}/staff-punch/in", headers=ctx["priya"])).json()["is_late"] is False
    staff = (await client.get(f"{API}/staff-attendance", params={"date": today_ist().isoformat()}, headers=ctx["admin"])).json()
    assert {e["full_name"]: e["status"] for e in staff["entries"]} == {"Ravi": "late", "Priya": "present"}


async def test_punch_is_for_teachers_only(db, client):
    ctx = await _setup(client, "PUN3")
    assert (await client.post(f"{API}/staff-punch/in", headers=ctx["admin"])).status_code == 403
    assert (await client.post(f"{API}/staff-punch/in", headers=ctx["parent"])).status_code == 403
    assert (await client.post(f"{API}/staff-punch/out", headers=ctx["ravi"])).status_code == 409  # not punched in
    assert (await client.get(f"{API}/staff-punch", params={"date": "2026-09-25"}, headers=ctx["ravi"])).status_code == 403


# --- Leave -----------------------------------------------------------------------


def _leave(ctx=None, start_offset=1, days=2, kind="sick"):
    """A leave body; with ctx it is the parent's request for Asha."""
    start = today_ist() + timedelta(days=start_offset)
    body = {"leave_type": kind, "from_date": start.isoformat(), "to_date": (start + timedelta(days=days - 1)).isoformat(), "reason": "Fever"}
    return {**body, "student_id": ctx["asha"]["id"]} if ctx else body


async def test_child_leave_goes_to_class_teacher(db, client):
    ctx = await _setup(client, "LEV1")
    applied = await client.post(f"{API}/leave", json=_leave(ctx), headers=ctx["parent"])
    assert applied.status_code == 201
    leave = applied.json()
    assert (leave["status"], leave["days"], leave["applicant_kind"], leave["applicant_name"]) == ("pending", 2, "student", "Asha")

    ravi_notes = await _notes(client, ctx["ravi"])
    assert ravi_notes["unread"] == 1 and ravi_notes["items"][0]["title"] == "Leave request: Asha (from parent)"
    assert (await _notes(client, ctx["priya"]))["unread"] == 0

    assert [l["id"] for l in (await client.get(f"{API}/leave/inbox", headers=ctx["ravi"])).json()] == [leave["id"]]
    assert (await client.get(f"{API}/leave/inbox", headers=ctx["priya"])).json() == []
    assert (await client.post(f"{API}/leave/{leave['id']}/review", json={"status": "approved"}, headers=ctx["priya"])).status_code == 403

    reviewed = (await client.post(f"{API}/leave/{leave['id']}/review", json={"status": "approved", "note": "Get well soon"}, headers=ctx["ravi"])).json()
    assert (reviewed["status"], reviewed["reviewer_name"]) == ("approved", "Ravi")
    parent_notes = await _notes(client, ctx["parent"])
    assert parent_notes["items"][0]["title"] == "Your leave was approved"
    again = await client.post(f"{API}/leave/{leave['id']}/review", json={"status": "rejected", "note": "x"}, headers=ctx["ravi"])
    assert again.status_code == 409


async def test_approved_child_leave_shows_on_attendance_without_parent_alert(db, client):
    ctx = await _setup(client, "LEV2")
    leave = (await client.post(f"{API}/leave", json=_leave(ctx, start_offset=0, days=1), headers=ctx["parent"])).json()
    await client.post(f"{API}/leave/{leave['id']}/review", json={"status": "approved"}, headers=ctx["ravi"])

    today = today_ist().isoformat()
    sheet = (await client.get(f"{API}/classes/{ctx['grade']['id']}/attendance", params={"date": today}, headers=ctx["ravi"])).json()
    assert sheet["entries"][0]["on_leave"] is True
    await client.post(
        f"{API}/classes/{ctx['grade']['id']}/attendance",
        json={"date": today, "records": [{"student_id": ctx["asha"]["id"], "status": "absent"}]},
        headers=ctx["ravi"],
    )
    assert (await client.get(f"{API}/parent-alerts", headers=ctx["admin"])).json() == []


async def test_teacher_leave_goes_to_admin_and_marks_staff_attendance(db, client):
    ctx = await _setup(client, "LEV3")
    ravi_leave = (await client.post(f"{API}/leave", json=_leave(start_offset=3, days=3, kind="casual"), headers=ctx["ravi"])).json()
    assert (await _notes(client, ctx["admin"]))["items"][0]["title"] == "Staff leave request: Ravi"
    assert (await client.post(f"{API}/leave/{ravi_leave['id']}/review", json={"status": "approved"}, headers=ctx["priya"])).status_code == 403

    await client.post(f"{API}/leave/{ravi_leave['id']}/review", json={"status": "approved"}, headers=ctx["admin"])
    start = today_ist() + timedelta(days=3)
    marked = []
    for offset in range(3):
        day = start + timedelta(days=offset)
        staff = (await client.get(f"{API}/staff-attendance", params={"date": day.isoformat()}, headers=ctx["admin"])).json()
        marked.append(next(e["status"] for e in staff["entries"] if e["full_name"] == "Ravi"))
    assert marked == ["leave" if (start + timedelta(days=i)).weekday() < 5 else None for i in range(3)]


async def test_leave_rules(db, client):
    ctx = await _setup(client, "LEV4")
    first = (await client.post(f"{API}/leave", json=_leave(ctx, days=3), headers=ctx["parent"])).json()
    overlap = await client.post(f"{API}/leave", json=_leave(ctx, start_offset=2, days=1), headers=ctx["parent"])
    assert overlap.status_code == 409
    backwards = _leave(ctx)
    backwards["to_date"], backwards["from_date"] = backwards["from_date"], backwards["to_date"]
    assert (await client.post(f"{API}/leave", json=backwards, headers=ctx["parent"])).status_code == 422
    assert (await client.post(f"{API}/leave", json=_leave(ctx, start_offset=-40, days=1), headers=ctx["parent"])).status_code == 400
    assert (await client.post(f"{API}/leave", json=_leave(), headers=ctx["parent"])).status_code == 404  # which child?
    assert (await client.post(f"{API}/leave", json=_leave(), headers=ctx["admin"])).status_code == 403

    no_reason = await client.post(f"{API}/leave/{first['id']}/review", json={"status": "rejected"}, headers=ctx["ravi"])
    assert no_reason.status_code == 400
    cancelled = (await client.post(f"{API}/leave/{first['id']}/cancel", headers=ctx["parent"])).json()
    assert cancelled["status"] == "cancelled"
    assert (await client.post(f"{API}/leave", json=_leave(ctx, start_offset=2, days=1), headers=ctx["parent"])).status_code == 201


async def test_notifications_read(db, client):
    ctx = await _setup(client, "LEV5")
    await client.post(f"{API}/leave", json=_leave(ctx), headers=ctx["parent"])
    notes = await _notes(client, ctx["ravi"])
    assert notes["unread"] == 1
    await client.post(f"{API}/notifications/{notes['items'][0]['id']}/read", headers=ctx["ravi"])
    assert (await _notes(client, ctx["ravi"]))["unread"] == 0
    await client.post(f"{API}/leave", json=_leave(ctx, start_offset=10, days=1), headers=ctx["parent"])
    await client.post(f"{API}/notifications/read-all", headers=ctx["ravi"])
    assert (await _notes(client, ctx["ravi"]))["unread"] == 0
    # Can't mark someone else's notification.
    assert (await _notes(client, ctx["parent"]))["unread"] == 0
