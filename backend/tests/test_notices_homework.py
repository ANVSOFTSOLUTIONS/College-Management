import zlib
from datetime import timedelta

from app.db.helpers import execute
from app.modules.alerts.service import today_ist
from tests.factories import auth_headers, create_school, create_user, login

PASSWORD = "Secret123!"
API = "/api/v1"
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


async def _setup(client, code):
    """Ravi: class teacher of Grade 5 and its Maths teacher. Priya: English in Grade 5.
    Kiran: class teacher of Grade 6. Asha (Grade 5) has a parent login."""
    phone = f"9{zlib.crc32(code.encode()) % 10**9:09d}"  # one parent mobile per school; logins are rate-limited per mobile
    school_id = await create_school(code=code)
    await create_user(school_id=school_id, email=f"{code}-admin@example.com".lower(), password=PASSWORD, role="admin")
    admin = auth_headers((await login(client, f"{code}-admin@example.com".lower(), PASSWORD)).json()["access_token"])

    async def teacher(key, name):
        body = {"email": f"{code}-{key}@example.com".lower(), "full_name": name, "password": PASSWORD}
        tid = (await client.post(f"{API}/teachers", json=body, headers=admin)).json()["id"]
        return tid, auth_headers((await login(client, body["email"], PASSWORD)).json()["access_token"])

    ravi_id, ravi = await teacher("ravi", "Ravi")
    priya_id, priya = await teacher("priya", "Priya")
    kiran_id, kiran = await teacher("kiran", "Kiran")

    async def grade(name, tid):
        body = {"name": name, "section": "A", "academic_year": "2026", "class_teacher_id": tid}
        return (await client.post(f"{API}/classes", json=body, headers=admin)).json()

    g5, g6 = await grade("Grade 5", ravi_id), await grade("Grade 6", kiran_id)
    maths = (await client.post(f"{API}/subjects", json={"name": "Maths"}, headers=admin)).json()
    english = (await client.post(f"{API}/subjects", json={"name": "English"}, headers=admin)).json()
    science = (await client.post(f"{API}/subjects", json={"name": "Science"}, headers=admin)).json()
    await client.put(f"{API}/classes/{g5['id']}/subjects/{maths['id']}", json={"teacher_id": ravi_id}, headers=admin)
    await client.put(f"{API}/classes/{g5['id']}/subjects/{english['id']}", json={"teacher_id": priya_id}, headers=admin)
    await client.put(f"{API}/classes/{g6['id']}/subjects/{science['id']}", json={"teacher_id": kiran_id}, headers=admin)

    asha_body = {"admission_number": "A-1", "full_name": "Asha", "class_id": g5["id"], "mother": {"full_name": "Padma", "phone": phone}}
    asha = (await client.post(f"{API}/students", json=asha_body, headers=admin)).json()
    parent_password = (await client.post(f"{API}/students/{asha['id']}/parent-login", json={}, headers=admin)).json()["password"]
    parent_login = {"phone": phone, "password": parent_password}
    parent = auth_headers((await client.post(f"{API}/auth/login", json=parent_login)).json()["access_token"])
    return {
        "admin": admin, "ravi": ravi, "priya": priya, "kiran": kiran, "g5": g5, "g6": g6, "maths": maths,
        "english": english, "science": science, "asha": asha, "parent": parent,
    }


async def _titles(client, headers, path="notices", **params):
    return [n["title"] for n in (await client.get(f"{API}/{path}", params=params, headers=headers)).json()]


async def _bell(client, headers):
    return [n["title"] for n in (await client.get(f"{API}/notifications", headers=headers)).json()["items"]]


async def _notice(client, headers, title, **body):
    response = await client.post(f"{API}/notices", json={"title": title, "body": "Details here.", **body}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


# --- Notices ----------------------------------------------------------------------


async def test_notices_reach_only_their_audience(db, client):
    ctx = await _setup(client, "NTC1")
    await _notice(client, ctx["admin"], "School closed Friday", for_staff=True)
    await _notice(client, ctx["admin"], "Staff meeting", for_staff=True, for_parents=False)
    await _notice(client, ctx["admin"], "Grade 6 picnic", class_ids=[ctx["g6"]["id"]])
    await _notice(client, ctx["admin"], "Grade 5 parents meet", class_ids=[ctx["g5"]["id"]], is_pinned=True)

    assert await _titles(client, ctx["admin"]) == ["Grade 5 parents meet", "Grade 6 picnic", "Staff meeting", "School closed Friday"]
    assert await _titles(client, ctx["parent"]) == ["Grade 5 parents meet", "School closed Friday"]
    # Ravi teaches Grade 5, so he sees its class notice too.
    assert await _titles(client, ctx["ravi"]) == ["Grade 5 parents meet", "Staff meeting", "School closed Friday"]
    assert await _titles(client, ctx["kiran"]) == ["Grade 6 picnic", "Staff meeting", "School closed Friday"]

    assert "Notice: Grade 5 parents meet" in await _bell(client, ctx["parent"])
    assert "Notice: Staff meeting" not in await _bell(client, ctx["parent"])
    assert "Notice: Staff meeting" in await _bell(client, ctx["priya"])


async def test_teachers_post_only_to_their_classes(db, client):
    ctx = await _setup(client, "NTC2")
    notice = await _notice(client, ctx["priya"], "English test Monday", class_ids=[ctx["g5"]["id"]])
    assert notice["can_edit"] is True and notice["classes"] == ["Grade 5 - A"]
    assert "English test Monday" in await _titles(client, ctx["parent"])

    body = {"title": "Whole school", "body": "x"}
    assert (await client.post(f"{API}/notices", json=body, headers=ctx["priya"])).status_code == 403
    assert (await client.post(f"{API}/notices", json={**body, "class_ids": [ctx["g6"]["id"]]}, headers=ctx["priya"])).status_code == 403
    staff_only = {**body, "class_ids": [ctx["g5"]["id"]], "for_staff": True}
    assert (await client.post(f"{API}/notices", json=staff_only, headers=ctx["priya"])).status_code == 403
    assert (await client.post(f"{API}/notices", json=body, headers=ctx["parent"])).status_code == 403

    # Only the poster or the admin can change it.
    assert (await client.delete(f"{API}/notices/{notice['id']}", headers=ctx["ravi"])).status_code == 403
    change = {"title": "English test Tuesday", "body": "Moved.", "class_ids": [ctx["g5"]["id"]]}
    edited = await client.put(f"{API}/notices/{notice['id']}", json=change, headers=ctx["priya"])
    assert edited.json()["title"] == "English test Tuesday"
    assert (await client.delete(f"{API}/notices/{notice['id']}", headers=ctx["admin"])).status_code == 204
    assert await _titles(client, ctx["parent"]) == []


async def test_expired_notices_hide_and_validation(db, client):
    ctx = await _setup(client, "NTC3")
    notice = await _notice(client, ctx["admin"], "Fee last date", expires_on=today_ist().isoformat())
    assert await _titles(client, ctx["parent"]) == ["Fee last date"]
    past = (today_ist() - timedelta(days=1)).isoformat()
    assert (await client.post(f"{API}/notices", json={"title": "Old", "body": "x", "expires_on": past}, headers=ctx["admin"])).status_code == 400
    nobody = {"title": "Nobody", "body": "x", "for_parents": False}
    assert (await client.post(f"{API}/notices", json=nobody, headers=ctx["admin"])).status_code == 422

    await execute("UPDATE notices SET expires_on = %s WHERE id = %s", (past, notice["id"]))
    assert await _titles(client, ctx["parent"]) == []
    listed = (await client.get(f"{API}/notices", params={"include_expired": "true"}, headers=ctx["admin"])).json()
    assert listed[0]["is_expired"] is True


async def test_notice_attachment_is_private(db, client):
    ctx = await _setup(client, "NTC4")
    notice = await _notice(client, ctx["admin"], "Grade 6 circular", class_ids=[ctx["g6"]["id"]])
    files = {"file": ("circular.pdf", PDF, "application/pdf")}
    uploaded = await client.post(f"{API}/notices/{notice['id']}/attachment", files=files, headers=ctx["admin"])
    assert uploaded.json()["attachment_name"] == "circular.pdf"
    assert (await client.get(f"{API}/notices/{notice['id']}/attachment", headers=ctx["kiran"])).content == PDF
    assert (await client.get(f"{API}/notices/{notice['id']}/attachment", headers=ctx["parent"])).status_code == 404
    exe = {"file": ("x.exe", b"MZ", "application/octet-stream")}
    assert (await client.post(f"{API}/notices/{notice['id']}/attachment", files=exe, headers=ctx["admin"])).status_code == 400
    removed = await client.delete(f"{API}/notices/{notice['id']}/attachment", headers=ctx["admin"])
    assert removed.json()["attachment_name"] is None


async def test_notices_do_not_leak_across_schools(db, client):
    ctx = await _setup(client, "NTC5")
    other = await _setup(client, "NTC6")
    notice = await _notice(client, other["admin"], "Other school holiday")
    assert await _titles(client, ctx["admin"]) == []
    assert (await client.get(f"{API}/notices/{notice['id']}/attachment", headers=ctx["admin"])).status_code == 404
    assert (await client.delete(f"{API}/notices/{notice['id']}", headers=ctx["admin"])).status_code == 404


# --- Homework ---------------------------------------------------------------------


async def _homework(client, headers, ctx, subject="maths", cls="g5", **extra):
    body = {
        "class_id": ctx[cls]["id"], "subject_id": ctx[subject]["id"], "title": "Exercise 4.2", "details": "Questions 1-10",
        "due_on": (today_ist() + timedelta(days=2)).isoformat(), **extra,
    }
    return await client.post(f"{API}/homework", json=body, headers=headers)


async def test_subject_and_class_teachers_post_homework(db, client):
    ctx = await _setup(client, "HWK1")
    maths = await _homework(client, ctx["ravi"], ctx)
    assert maths.status_code == 201, maths.text
    assert (maths.json()["subject_name"], maths.json()["assigned_on"]) == ("Maths", today_ist().isoformat())
    # Priya teaches English here; Ravi as class teacher may post English too.
    assert (await _homework(client, ctx["priya"], ctx, subject="english", title="Essay")).status_code == 201
    assert (await _homework(client, ctx["ravi"], ctx, subject="english", title="Reading")).status_code == 201
    # Priya does not teach Maths; Kiran does not teach Grade 5; Science is not a Grade 5 subject.
    assert (await _homework(client, ctx["priya"], ctx)).status_code == 403
    assert (await _homework(client, ctx["kiran"], ctx)).status_code == 403
    assert (await _homework(client, ctx["admin"], ctx, subject="science")).status_code == 404
    assert (await _homework(client, ctx["parent"], ctx)).status_code == 403

    expected = ["Essay", "Exercise 4.2", "Reading"]
    assert sorted(await _titles(client, ctx["parent"], "homework")) == expected
    assert sorted(await _titles(client, ctx["parent"], "homework", student_id=ctx["asha"]["id"])) == expected
    assert await _titles(client, ctx["kiran"], "homework") == []
    assert "Homework: Maths" in await _bell(client, ctx["parent"])


async def test_homework_dates_editing_and_window(db, client):
    ctx = await _setup(client, "HWK2")
    today = today_ist()
    yesterday = (today - timedelta(days=1)).isoformat()
    assert (await _homework(client, ctx["ravi"], ctx, due_on=yesterday)).status_code == 400
    assert (await _homework(client, ctx["ravi"], ctx, assigned_on=today.isoformat(), due_on=yesterday)).status_code == 422
    old = await _homework(
        client, ctx["ravi"], ctx, title="Old work",
        assigned_on=(today - timedelta(days=30)).isoformat(), due_on=(today - timedelta(days=20)).isoformat(),
    )
    assert old.status_code == 201
    assert await _titles(client, ctx["parent"], "homework") == []  # older than two weeks
    assert await _titles(client, ctx["parent"], "homework", since=(today - timedelta(days=30)).isoformat()) == ["Old work"]

    item = (await _homework(client, ctx["ravi"], ctx)).json()
    change = {"class_id": ctx["g5"]["id"], "subject_id": ctx["maths"]["id"], "title": "Exercise 4.3", "due_on": item["due_on"]}
    assert (await client.put(f"{API}/homework/{item['id']}", json=change, headers=ctx["priya"])).status_code == 403
    assert (await client.put(f"{API}/homework/{item['id']}", json=change, headers=ctx["ravi"])).json()["title"] == "Exercise 4.3"

    files = {"file": ("sheet.pdf", PDF, "application/pdf")}
    uploaded = await client.post(f"{API}/homework/{item['id']}/attachment", files=files, headers=ctx["ravi"])
    assert uploaded.json()["attachment_name"] == "sheet.pdf"
    assert (await client.get(f"{API}/homework/{item['id']}/attachment", headers=ctx["parent"])).content == PDF
    assert (await client.get(f"{API}/homework/{item['id']}/attachment", headers=ctx["kiran"])).status_code == 404
    assert (await client.delete(f"{API}/homework/{item['id']}", headers=ctx["ravi"])).status_code == 204


async def test_parent_cannot_read_other_childrens_homework(db, client):
    ctx = await _setup(client, "HWK3")
    await _homework(client, ctx["kiran"], ctx, subject="science", cls="g6")
    assert await _titles(client, ctx["parent"], "homework") == []
    bala = {"admission_number": "B-1", "full_name": "Bala", "class_id": ctx["g6"]["id"]}
    other_child = (await client.post(f"{API}/students", json=bala, headers=ctx["admin"])).json()
    assert (await client.get(f"{API}/homework", params={"student_id": other_child["id"]}, headers=ctx["parent"])).status_code == 404


async def test_posting_options_follow_what_a_teacher_teaches(db, client):
    ctx = await _setup(client, "HWK4")

    async def options(who):
        return {o["name"]: [s["name"] for s in o["subjects"]] for o in (await client.get(f"{API}/homework/options", headers=ctx[who])).json()}

    assert await options("ravi") == {"Grade 5": ["English", "Maths"]}  # class teacher: every subject
    assert await options("priya") == {"Grade 5": ["English"]}
    assert await options("admin") == {"Grade 5": ["English", "Maths"], "Grade 6": ["Science"]}
    assert (await client.get(f"{API}/homework/options", headers=ctx["parent"])).status_code == 403
