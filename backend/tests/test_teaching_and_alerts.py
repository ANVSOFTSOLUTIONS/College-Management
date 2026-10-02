from datetime import timedelta

import pytest

from app.integrations import sms
from app.integrations.sms import Msg91SmsSender, SmsResult, normalize_indian_mobile
from app.modules.alerts import service as alerts
from tests.factories import auth_headers, create_school, create_user, login

PASSWORD = "Secret123!"
API = "/api/v1"


async def _setup(client, code):
    """Admin; Ravi is class teacher of Grade 5-A and teaches Maths there; Priya teaches English there;
    Kiran is class teacher of another class. Two students, one with a parent phone."""
    school_id = await create_school(code=code)
    await create_user(school_id=school_id, email=f"{code}-admin@example.com".lower(), password=PASSWORD, role="admin")
    admin = auth_headers((await login(client, f"{code}-admin@example.com".lower(), PASSWORD)).json()["access_token"])

    async def teacher(key, name):
        body = {"email": f"{code}-{key}@example.com".lower(), "full_name": name, "password": PASSWORD}
        created = (await client.post(f"{API}/teachers", json=body, headers=admin)).json()
        token = (await login(client, body["email"], PASSWORD)).json()["access_token"]
        return created["id"], auth_headers(token)

    ravi_id, ravi = await teacher("ravi", "Ravi")
    priya_id, priya = await teacher("priya", "Priya")
    kiran_id, kiran = await teacher("kiran", "Kiran")
    grade = (
        await client.post(
            f"{API}/classes",
            json={"name": "Grade 5", "section": "A", "academic_year": "2026", "class_teacher_id": ravi_id},
            headers=admin,
        )
    ).json()
    await client.post(
        f"{API}/classes",
        json={"name": "Grade 6", "section": "A", "academic_year": "2026", "class_teacher_id": kiran_id},
        headers=admin,
    )
    maths = (await client.post(f"{API}/subjects", json={"name": "Maths"}, headers=admin)).json()
    english = (await client.post(f"{API}/subjects", json={"name": "English"}, headers=admin)).json()
    await client.put(f"{API}/classes/{grade['id']}/subjects/{maths['id']}", json={"teacher_id": ravi_id}, headers=admin)
    await client.put(f"{API}/classes/{grade['id']}/subjects/{english['id']}", json={"teacher_id": priya_id}, headers=admin)

    asha = (
        await client.post(
            f"{API}/students",
            json={
                "admission_number": "A-1",
                "full_name": "Asha",
                "class_id": grade["id"],
                "father": {"full_name": "Srinivas", "phone": "98480 22338"},
            },
            headers=admin,
        )
    ).json()
    bala = (
        await client.post(
            f"{API}/students", json={"admission_number": "A-2", "full_name": "Bala", "class_id": grade["id"]}, headers=admin
        )
    ).json()
    return {
        "admin": admin, "ravi": ravi, "priya": priya, "kiran": kiran, "grade": grade,
        "maths": maths, "english": english, "asha": asha, "bala": bala,
    }


# --- My classes -----------------------------------------------------------------


async def test_subject_teacher_sees_class_and_roster_but_not_student_records(db, client):
    ctx = await _setup(client, "TCH1")
    classes = (await client.get(f"{API}/teaching/classes", headers=ctx["priya"])).json()
    assert [(c["name"], c["is_class_teacher"], [s["name"] for s in c["subjects"]]) for c in classes] == [
        ("Grade 5", False, ["English"])
    ]
    assert classes[0]["student_count"] == 2

    roster = (await client.get(f"{API}/teaching/classes/{ctx['grade']['id']}/students", headers=ctx["priya"])).json()
    assert [s["full_name"] for s in roster] == ["Asha", "Bala"]

    # Parent details and attendance stay with the class teacher.
    assert (await client.get(f"{API}/students/{ctx['asha']['id']}", headers=ctx["priya"])).status_code == 404
    assert (await client.get(f"{API}/classes/{ctx['grade']['id']}/students", headers=ctx["priya"])).status_code == 403
    # Kiran doesn't teach Grade 5 at all.
    assert (await client.get(f"{API}/teaching/classes/{ctx['grade']['id']}/students", headers=ctx["kiran"])).status_code == 404

    ravi_classes = (await client.get(f"{API}/teaching/classes", headers=ctx["ravi"])).json()
    assert ravi_classes[0]["is_class_teacher"] is True


# --- Remarks and remark alerts -----------------------------------------------------


async def test_remark_with_parent_alert_is_recorded_while_sms_is_off(db, client):
    ctx = await _setup(client, "TCH2")
    response = await client.post(
        f"{API}/remarks",
        json={
            "student_id": ctx["asha"]["id"],
            "category": "missed_exam",
            "subject_id": ctx["english"]["id"],
            "note": "Unit test 2",
            "notify_parent": True,
        },
        headers=ctx["priya"],
    )
    assert response.status_code == 201, response.text
    remark = response.json()
    assert remark["subject_name"] == "English"
    assert remark["alert_status"] == "not_sent"

    alert_list = (await client.get(f"{API}/parent-alerts", headers=ctx["admin"])).json()
    assert len(alert_list) == 1
    assert alert_list[0]["recipient_phone"] == "98480 22338"
    assert "Asha missed an exam (English)" in alert_list[0]["message"]
    assert alert_list[0]["status_detail"] == "SMS sending is turned off."
    settings = (await client.get(f"{API}/parent-alerts/settings", headers=ctx["admin"])).json()
    assert settings == {"sms_enabled": False, "provider": "", "whatsapp_enabled": False}


async def test_remark_subject_must_be_one_the_teacher_teaches(db, client):
    ctx = await _setup(client, "TCH3")
    response = await client.post(
        f"{API}/remarks",
        json={"student_id": ctx["asha"]["id"], "category": "homework", "subject_id": ctx["maths"]["id"]},
        headers=ctx["priya"],
    )
    assert response.status_code == 400
    outsider = await client.post(
        f"{API}/remarks", json={"student_id": ctx["asha"]["id"], "category": "homework"}, headers=ctx["kiran"]
    )
    assert outsider.status_code == 404


async def test_remark_visibility_and_deletion(db, client):
    ctx = await _setup(client, "TCH4")
    remark = (
        await client.post(
            f"{API}/remarks",
            json={"student_id": ctx["bala"]["id"], "category": "appreciation", "note": "Great essay"},
            headers=ctx["priya"],
        )
    ).json()
    assert remark["alert_status"] is None  # no parent alert asked for

    assert len((await client.get(f"{API}/remarks", headers=ctx["priya"])).json()) == 1  # author
    assert len((await client.get(f"{API}/remarks", headers=ctx["ravi"])).json()) == 1  # class teacher
    assert (await client.get(f"{API}/remarks", headers=ctx["kiran"])).json() == []  # neither
    by_student = (await client.get(f"{API}/remarks", params={"student_id": ctx["bala"]["id"]}, headers=ctx["admin"])).json()
    assert by_student[0]["can_delete"] is True

    assert (await client.delete(f"{API}/remarks/{remark['id']}", headers=ctx["ravi"])).status_code == 403
    assert (await client.delete(f"{API}/remarks/{remark['id']}", headers=ctx["priya"])).status_code == 204


# --- Absence alerts ------------------------------------------------------------------


async def _mark(client, ctx, day, statuses):
    records = [{"student_id": ctx[name]["id"], "status": status} for name, status in statuses.items()]
    return await client.post(
        f"{API}/classes/{ctx['grade']['id']}/attendance", json={"date": day.isoformat(), "records": records}, headers=ctx["ravi"]
    )


async def test_absence_alerts_once_per_day_and_only_for_today(db, client):
    ctx = await _setup(client, "TCH5")
    today = alerts.today_ist()
    assert (await _mark(client, ctx, today, {"asha": "absent", "bala": "absent"})).status_code == 200
    await _mark(client, ctx, today, {"asha": "absent"})  # saved again: no second alert
    await _mark(client, ctx, today - timedelta(days=3), {"asha": "absent"})  # back-filled: no alert

    alert_list = (await client.get(f"{API}/parent-alerts", headers=ctx["admin"])).json()
    by_student = {a["student_name"]: a for a in alert_list}
    assert len(alert_list) == 2
    assert by_student["Asha"]["kind"] == "absence"
    assert "was absent today" in by_student["Asha"]["message"]
    assert by_student["Bala"]["status_detail"] == "No parent phone number on file."

    # Class teacher sees their class's alerts; another class's teacher doesn't.
    assert len((await client.get(f"{API}/parent-alerts", headers=ctx["ravi"])).json()) == 2
    assert (await client.get(f"{API}/parent-alerts", headers=ctx["kiran"])).json() == []


async def test_alerts_are_sent_when_sms_is_on(db, client, monkeypatch):
    sent = []

    class FakeSender:
        async def send(self, phone, message, kind, variables):
            sent.append((phone, kind, variables["student"]))
            return SmsResult("sent", "", "msg-1")

    monkeypatch.setattr(alerts, "get_sms_sender", lambda: FakeSender())
    ctx = await _setup(client, "TCH6")
    await _mark(client, ctx, alerts.today_ist(), {"asha": "absent", "bala": "present"})

    assert sent == [("98480 22338", "absence", "Asha")]
    alert = (await client.get(f"{API}/parent-alerts", headers=ctx["admin"])).json()[0]
    assert alert["status"] == "sent"


# --- SMS provider --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("98480 22338", "919848022338"), ("+91-98480-22338", "919848022338"), ("09848022338", "919848022338"),
     ("12345", None), ("5848022338", None), ("", None)],
)
def test_normalize_indian_mobile(raw, expected):
    assert normalize_indian_mobile(raw) == expected


async def test_msg91_sender(monkeypatch):
    sender = Msg91SmsSender("key", {"absence": "tmpl-1", "remark": ""})
    calls = []
    monkeypatch.setattr(sender, "_post", lambda body: calls.append(body) or {"type": "success", "message": "req-9"})

    result = await sender.send("9848022338", "text", "absence", {"student": "Asha"})
    assert (result.status, result.message_id) == ("sent", "req-9")
    assert calls[0]["template_id"] == "tmpl-1"
    assert calls[0]["recipients"] == [{"mobiles": "919848022338", "student": "Asha"}]

    assert (await sender.send("9848022338", "text", "remark", {})).status == "not_sent"  # no template
    assert (await sender.send("123", "text", "absence", {})).status == "failed"

    monkeypatch.setattr(sender, "_post", lambda body: {"type": "error", "message": "Invalid template"})
    assert (await sender.send("9848022338", "text", "absence", {})).status == "failed"


def test_sms_is_off_by_default():
    assert isinstance(sms.get_sms_sender(), sms.DisabledSmsSender)
