"""Hall tickets with attendance rule and seating, scholarships, and certificate requests from the app."""

from tests.factories import auth_headers, create_school, create_user, login

PASSWORD = "Secret123!"
API = "/api/v1"


async def _college(client, code, students=(("S1", "Asha"), ("S2", "Bala"))):
    school_id = await create_school(code=code)
    await create_user(school_id=school_id, email=f"{code}-admin@example.com".lower(), password=PASSWORD, role="admin")
    admin = auth_headers((await login(client, f"{code}-admin@example.com".lower(), PASSWORD)).json()["access_token"])
    body = {"email": f"{code}-f@example.com".lower(), "full_name": "Ravi", "password": PASSWORD}
    faculty = (await client.post(f"{API}/teachers", json=body, headers=admin)).json()
    batches = []
    for section in ("A", "B"):
        batches.append((await client.post(f"{API}/classes", json={"name": "B.Tech CSE", "section": section, "academic_year": "2026",
                                                                   "class_teacher_id": faculty["id"]}, headers=admin)).json())
    dbms = (await client.post(f"{API}/subjects", json={"name": "DBMS", "code": "CS301"}, headers=admin)).json()
    for b in batches:
        await client.put(f"{API}/classes/{b['id']}/subjects/{dbms['id']}", json={"teacher_id": faculty["id"]}, headers=admin)
    made = []
    for i, (roll, name) in enumerate(students):
        s = (await client.post(f"{API}/students", json={"admission_number": roll, "full_name": name, "class_id": batches[i % 2]["id"]}, headers=admin)).json()
        made.append(s)
    return admin, faculty, batches, dbms, made


async def _student_headers(client, admin, code, student):
    await client.post(f"{API}/students/{student['id']}/login", json={"password": "StudentPass1"}, headers=admin)
    token = (await client.post(f"{API}/auth/login", json={"college_code": code, "roll_number": student["admission_number"], "password": "StudentPass1"})).json()
    return auth_headers(token["access_token"])


async def test_hall_tickets_attendance_rule_and_seating(db, client):
    admin, faculty, (a, b), dbms, (asha, bala, chitra, dev) = await _college(client, "HTK1", (("S1", "Asha"), ("S2", "Bala"), ("S3", "Chitra"), ("S4", "Dev")))
    # Asha (A) attends 1 of 4 DBMS hours: 25%.
    faculty_h = auth_headers((await login(client, "htk1-f@example.com", PASSWORD)).json()["access_token"])
    for period, st in enumerate(["present", "absent", "absent", "absent"], start=1):
        body = {"class_id": a["id"], "subject_id": dbms["id"], "date": "2026-09-01", "period": period,
                "records": [{"student_id": asha["id"], "status": st}, {"student_id": chitra["id"], "status": "present"}]}
        await client.post(f"{API}/subject-attendance", json=body, headers=faculty_h)
    exam = (await client.post(f"{API}/exams", json={"name": "Sem 1", "exam_type": "semester", "academic_year": "2026", "class_ids": [a["id"], b["id"]],
                                                     "max_marks": "100", "pass_marks": "40"}, headers=admin)).json()
    url = f"{API}/exams/{exam['id']}/hall-tickets"

    sheet = (await client.put(f"{url}/settings", json={"min_attendance": 75, "released": True}, headers=admin)).json()
    rows = {r["full_name"]: r for r in sheet["students"]}
    assert (rows["Asha"]["attendance"], rows["Asha"]["eligible"], rows["Chitra"]["eligible"], rows["Bala"]["attendance"]) == (25.0, False, True, None)

    # Two rooms of 2: seats alternate batches (A, B, A, B); Asha is not seated.
    sheet = (await client.put(f"{url}/rooms", json=[{"name": "Room 101", "capacity": 2}, {"name": "Room 102", "capacity": 2}], headers=admin)).json()
    seats = {r["full_name"]: (r["room"], r["seat"]) for r in sheet["students"]}
    assert seats == {"Chitra": ("Room 101", 1), "Bala": ("Room 101", 2), "Dev": ("Room 102", 1), "Asha": (None, None)}
    assert ([r["seated"] for r in sheet["rooms"]], sheet["unseated"]) == ([2, 1], 0)

    # Condonation: the office allows Asha.
    sheet = (await client.put(f"{url}/override", json={"student_id": asha["id"], "allowed": True}, headers=admin)).json()
    assert next(r for r in sheet["students"] if r["full_name"] == "Asha")["eligible"] is True

    asha_h = await _student_headers(client, admin, "HTK1", asha)
    tickets = (await client.get(f"{API}/me/parent/children/{asha['id']}/hall-tickets", headers=asha_h)).json()
    assert [(t["exam_name"], t["eligible"], t["room"], [p["subject_name"] for p in t["papers"]]) for t in tickets] == [("Sem 1", True, "Room 101", ["DBMS"])]
    await client.put(f"{url}/settings", json={"min_attendance": 75, "released": False}, headers=admin)
    assert (await client.get(f"{API}/me/parent/children/{asha['id']}/hall-tickets", headers=asha_h)).json() == []


async def test_scholarships(db, client):
    admin, faculty, (a, b), dbms, (asha, bala) = await _college(client, "SCH1")
    body = {"student_id": asha["id"], "scheme": "Vidya Deevena", "academic_year": "2026-27", "application_no": "JVD123", "amount_sanctioned": "35000"}
    created = await client.post(f"{API}/scholarships", json=body, headers=admin)
    assert created.status_code == 201, created.text
    record = created.json()
    assert (record["status"], record["amount_sanctioned"], record["full_name"]) == ("applied", 35000.0, "Asha")
    assert (await client.post(f"{API}/scholarships", json=body, headers=admin)).json()["error"]["code"] == "scholarship_exists"
    await client.post(f"{API}/scholarships", json={"student_id": bala["id"], "scheme": "Vidya Deevena", "academic_year": "2026-27"}, headers=admin)

    updated = (await client.put(f"{API}/scholarships/{record['id']}", json={"status": "disbursed", "amount_received": "35000"}, headers=admin)).json()
    assert (updated["status"], updated["amount_received"], updated["application_no"]) == ("disbursed", 35000.0, "JVD123")
    summary = (await client.get(f"{API}/scholarships/summary", params={"academic_year": "2026-27"}, headers=admin)).json()
    assert summary == [{"scheme": "Vidya Deevena", "students": 2, "sanctioned": 35000.0, "received": 35000.0, "pending": 1}]
    assert len((await client.get(f"{API}/scholarships", params={"status": "applied"}, headers=admin)).json()) == 1

    asha_h = await _student_headers(client, admin, "SCH1", asha)
    mine = (await client.get(f"{API}/me/parent/children/{asha['id']}/scholarships", headers=asha_h)).json()
    assert [(m["scheme"], m["status"]) for m in mine] == [("Vidya Deevena", "disbursed")]


async def test_certificate_requests(db, client):
    admin, faculty, (a, b), dbms, (asha, bala) = await _college(client, "CRQ1")
    asha_h = await _student_headers(client, admin, "CRQ1", asha)
    url = f"{API}/me/parent/children/{asha['id']}/certificate-requests"
    made = await client.post(url, json={"kind": "bonafide", "purpose": "Bank education loan"}, headers=asha_h)
    assert made.status_code == 201, made.text
    assert made.json()[0]["status"] == "pending"
    assert (await client.post(url, json={"kind": "bonafide", "purpose": "Again"}, headers=asha_h)).json()["error"]["code"] == "request_pending"

    pending = (await client.get(f"{API}/certificate-requests", params={"status": "pending"}, headers=admin)).json()
    assert [(r["full_name"], r["title"]) for r in pending] == [("Asha", "Bonafide Certificate")]
    approved = (await client.post(f"{API}/certificate-requests/{pending[0]['id']}/approve", json={}, headers=admin)).json()
    assert approved["status"] == "issued" and approved["serial_no"].startswith("BON")
    certificate = (await client.get(f"{API}/certificates/{approved['certificate_id']}", headers=admin)).json()
    assert certificate["details"]["purpose"] == "Bank education loan"

    await client.post(url, json={"kind": "tc", "purpose": "Higher studies"}, headers=asha_h)
    tc = next(r for r in (await client.get(url, headers=asha_h)).json() if r["kind"] == "tc")
    assert (await client.post(f"{API}/certificate-requests/{tc['id']}/reject", json={"note": ""}, headers=admin)).json()["error"]["code"] == "note_required"
    rejected = (await client.post(f"{API}/certificate-requests/{tc['id']}/reject", json={"note": "Clear library dues first"}, headers=admin)).json()
    assert (rejected["status"], rejected["note"]) == ("rejected", "Clear library dues first")
