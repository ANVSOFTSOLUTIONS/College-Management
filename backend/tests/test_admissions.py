from app.db.helpers import execute, fetch_one
from app.modules.alerts.service import today_ist
from tests.factories import auth_headers, create_school, create_user, login

PASSWORD = "Secret123!"
API = "/api/v1"
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


async def _setup(client, code):
    school_id = await create_school(code=code)
    await create_user(school_id=school_id, email=f"{code}-admin@example.com".lower(), password=PASSWORD, role="admin")
    admin = auth_headers((await login(client, f"{code}-admin@example.com".lower(), PASSWORD)).json()["access_token"])
    body = {"email": f"{code}-ravi@example.com".lower(), "full_name": "Ravi", "password": PASSWORD}
    ravi_id = (await client.post(f"{API}/teachers", json=body, headers=admin)).json()["id"]
    ravi = auth_headers((await login(client, body["email"], PASSWORD)).json()["access_token"])
    grades = {}
    for name in ("Grade 10", "LKG", "Grade 2"):
        grades[name] = (await client.post(f"{API}/classes", json={"name": name, "section": "A", "academic_year": "2026", "class_teacher_id": ravi_id}, headers=admin)).json()
    return {"code": code, "school_id": school_id, "admin": admin, "ravi": ravi, "grades": grades}


def _application(**overrides):
    body = {
        "student_name": "Asha Rao", "date_of_birth": "2019-04-12", "gender": "female", "class_applied": "Grade 2",
        "previous_school": "Little Stars", "address": "12 MG Road", "father_name": "Srinivas Rao", "father_phone": "98480 22338",
        "mother_name": "Padma Rao", "mother_phone": "", "email": "srinivas@example.com", "message": "Transfer from Pune",
    }
    return {**body, **overrides}


async def _apply(client, ctx, **overrides):
    return await client.post(f"{API}/public/schools/{ctx['code']}/admissions", json=_application(**overrides))


async def test_public_form_lists_classes_in_school_order(db, client):
    ctx = await _setup(client, "ADM1")
    form = (await client.get(f"{API}/public/schools/adm1/admissions")).json()
    assert (form["school_code"], form["open"], form["classes"]) == ("ADM1", True, ["LKG", "Grade 2", "Grade 10"])
    assert (await client.get(f"{API}/public/schools/NOPE/admissions")).status_code == 404
    assert (await client.get(f"{API}/public/schools/{ctx['code']}/site")).json()["admissions_open"] is True
    await client.put(f"{API}/admissions/settings", json={"open": False}, headers=ctx["admin"])
    assert (await client.get(f"{API}/public/schools/{ctx['code']}/site")).json()["admissions_open"] is False


async def test_apply_upload_and_approve_creates_the_student(db, client):
    ctx = await _setup(client, "ADM2")
    response = await _apply(client, ctx)
    assert response.status_code == 201, response.text
    submitted = response.json()
    assert submitted["application_no"] == f"APP/{today_ist().year}/0001"

    upload = f"{API}/public/schools/{ctx['code']}/admissions/{submitted['id']}/documents"
    token = submitted["upload_token"]
    assert (await client.post(upload, data={"token": token, "doc_type": "birth_certificate"}, files={"file": ("birth.pdf", PDF, "application/pdf")})).status_code == 204
    assert (await client.post(upload, data={"token": token, "doc_type": "photo"}, files={"file": ("asha.png", PNG, "image/png")})).status_code == 204
    assert (await client.post(upload, data={"token": "x" * 64, "doc_type": "other"}, files={"file": ("x.pdf", PDF, "application/pdf")})).status_code == 403
    assert (await client.post(upload, data={"token": token, "doc_type": "photo"}, files={"file": ("x.pdf", PDF, "application/pdf")})).status_code == 400

    # The admin is told, sees it with its documents, and approves it.
    bell = [n["title"] for n in (await client.get(f"{API}/notifications", headers=ctx["admin"])).json()["items"]]
    assert "New admission application: Asha Rao" in bell
    assert (await client.get(f"{API}/dashboard/admin", headers=ctx["admin"])).json()["pending_admissions"] == 1
    listed = (await client.get(f"{API}/admissions", params={"status_filter": "new"}, headers=ctx["admin"])).json()
    assert [(a["student_name"], a["father_phone"], len(a["documents"])) for a in listed] == [("Asha Rao", "9848022338", 2)]
    doc = listed[0]["documents"][0]
    assert (await client.get(f"{API}/admissions/{submitted['id']}/documents/{doc['id']}", headers=ctx["admin"])).content == PDF

    suggested = (await client.get(f"{API}/admissions/next-admission-number", headers=ctx["admin"])).json()["admission_number"]
    approved = await client.post(f"{API}/admissions/{submitted['id']}/approve", json={"class_id": ctx["grades"]["Grade 2"]["id"]}, headers=ctx["admin"])
    assert approved.status_code == 200, approved.text
    student_id = approved.json()["student_id"]
    student = (await client.get(f"{API}/students/{student_id}", headers=ctx["admin"])).json()
    assert (student["admission_number"], student["class"]["name"], student["date_of_birth"], student["has_photo"]) == (suggested, "Grade 2", "2019-04-12", True)
    assert {g["relation"]: g["full_name"] for g in student["guardians"]} == {"father": "Srinivas Rao", "mother": "Padma Rao"}
    assert student["primary_contact"] == "father"
    documents = (await client.get(f"{API}/students/{student_id}/documents", headers=ctx["admin"])).json()
    assert [(d["doc_type"], d["status"]) for d in documents] == [("birth_certificate", "approved")]

    # Decided applications are closed to more changes and uploads.
    assert (await client.post(f"{API}/admissions/{submitted['id']}/reject", json={"note": "Too late"}, headers=ctx["admin"])).status_code == 409
    assert (await client.post(upload, data={"token": token, "doc_type": "other"}, files={"file": ("x.pdf", PDF, "application/pdf")})).status_code == 403


async def test_reject_walk_in_and_admission_number_clash(db, client):
    ctx = await _setup(client, "ADM3")
    walk_in = await client.post(f"{API}/admissions", json=_application(student_name="Bala", father_name="", mother_name="Latha", mother_phone="9848022339", father_phone=""), headers=ctx["admin"])
    assert walk_in.status_code == 201 and walk_in.json()["source"] == "office"
    rejected = (await client.post(f"{API}/admissions/{walk_in.json()['id']}/reject", json={"note": "No seats in Grade 2"}, headers=ctx["admin"])).json()
    assert (rejected["status"], rejected["review_note"]) == ("rejected", "No seats in Grade 2")

    await client.post(f"{API}/students", json={"admission_number": "A-1", "full_name": "Existing", "class_id": ctx["grades"]["LKG"]["id"]}, headers=ctx["admin"])
    second = (await _apply(client, ctx, student_name="Chitra")).json()
    clash = await client.post(f"{API}/admissions/{second['id']}/approve", json={"class_id": ctx["grades"]["LKG"]["id"], "admission_number": "A-1"}, headers=ctx["admin"])
    assert clash.status_code == 409 and clash.json()["error"]["code"] == "admission_number_taken"
    assert (await fetch_one("SELECT status FROM admission_applications WHERE id = %s", (second["id"],)))["status"] == "new"
    ok = await client.post(f"{API}/admissions/{second['id']}/approve", json={"class_id": ctx["grades"]["LKG"]["id"], "admission_number": "LKG-7"}, headers=ctx["admin"])
    assert ok.status_code == 200


async def test_validation_closed_admissions_and_access(db, client):
    ctx = await _setup(client, "ADM4")
    assert (await _apply(client, ctx, class_applied="Grade 99")).json()["error"]["code"] == "unknown_class"
    assert (await _apply(client, ctx, father_phone="12345")).status_code == 422
    assert (await _apply(client, ctx, father_phone="", mother_phone="")).status_code == 422
    assert (await _apply(client, ctx, website="http://spam.example")).status_code == 400  # the bot trap

    assert (await client.put(f"{API}/admissions/settings", json={"open": False}, headers=ctx["admin"])).json() == {"open": False, "admission_fee": 0.0}
    assert (await client.get(f"{API}/public/schools/{ctx['code']}/admissions")).json()["open"] is False
    assert (await _apply(client, ctx)).json()["error"]["code"] == "admissions_closed"

    assert (await client.get(f"{API}/admissions", headers=ctx["ravi"])).status_code == 403
    other = await _setup(client, "ADM5")
    walk_in = (await client.post(f"{API}/admissions", json=_application(), headers=other["admin"])).json()
    assert (await client.get(f"{API}/admissions/{walk_in['id']}", headers=ctx["admin"])).status_code == 404

    # A school without the module has no public apply page either.
    await execute("UPDATE schools SET enabled_modules = '[\"fees\"]' WHERE id = %s", (other["school_id"],))
    assert (await client.get(f"{API}/public/schools/{other['code']}/admissions")).status_code == 404
