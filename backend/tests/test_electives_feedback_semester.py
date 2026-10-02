"""Electives, anonymous faculty feedback and semester promotion with detention rules."""

from app.db.helpers import fetch_one
from tests.factories import auth_headers, create_school, create_user, login

PASSWORD = "Secret123!"
API = "/api/v1"


async def _setup(client, code):
    """A CSE batch in semester 3 with DBMS (sem 3) taught by Ravi, and two students who can log in."""
    school_id = await create_school(code=code)
    await create_user(school_id=school_id, email=f"{code}-admin@example.com".lower(), password=PASSWORD, role="admin")
    admin = auth_headers((await login(client, f"{code}-admin@example.com".lower(), PASSWORD)).json()["access_token"])

    async def teacher(name, **extra):
        body = {"email": f"{code}-{name}@example.com".lower(), "full_name": name, "password": PASSWORD, **extra}
        return (await client.post(f"{API}/teachers", json=body, headers=admin)).json()

    hod = await teacher("Rao")
    cse = (await client.post(f"{API}/departments", json={"name": "Computer Science", "code": "CSE", "hod_teacher_id": hod["id"]}, headers=admin)).json()
    ravi, anil = await teacher("Ravi", department_id=cse["id"]), await teacher("Anil", department_id=cse["id"])
    batch = (await client.post(f"{API}/classes", json={"name": "B.Tech CSE", "section": "A", "academic_year": "2026", "class_teacher_id": hod["id"],
                                                        "department_id": cse["id"], "semester": 3}, headers=admin)).json()

    async def subject(name, **extra):
        return (await client.post(f"{API}/subjects", json={"name": name, "department_id": cse["id"], **extra}, headers=admin)).json()

    dbms = await subject("DBMS", semester=3)
    await client.put(f"{API}/classes/{batch['id']}/subjects/{dbms['id']}", json={"teacher_id": ravi["id"]}, headers=admin)
    students = []
    for roll, name in (("S1", "Asha"), ("S2", "Bala")):
        s = (await client.post(f"{API}/students", json={"admission_number": roll, "full_name": name, "class_id": batch["id"]}, headers=admin)).json()
        await client.post(f"{API}/students/{s['id']}/login", json={"password": "StudentPass1"}, headers=admin)
        token = (await client.post(f"{API}/auth/login", json={"college_code": code, "roll_number": roll, "password": "StudentPass1"})).json()["access_token"]
        students.append((s, auth_headers(token)))
    return {"admin": admin, "hod": hod, "ravi": ravi, "anil": anil, "cse": cse, "batch": batch, "dbms": dbms, "subject": subject, "students": students}


async def test_electives_seats_and_rosters(db, client):
    ctx = await _setup(client, "ELE1")
    admin, batch = ctx["admin"], ctx["batch"]
    (asha, asha_h), (bala, bala_h) = ctx["students"]
    ml = await ctx["subject"]("Machine Learning", semester=3)
    cloud = await ctx["subject"]("Cloud Computing", semester=3)

    body = {"class_id": batch["id"], "name": "Professional Elective I",
            "options": [{"subject_id": ml["id"], "teacher_id": ctx["anil"]["id"], "seats": 1}, {"subject_id": cloud["id"], "teacher_id": ctx["ravi"]["id"], "seats": 5}]}
    group = await client.post(f"{API}/electives", json=body, headers=admin)
    assert group.status_code == 201, group.text
    group = group.json()
    assert [(o["subject_name"], o["teacher_name"], o["seats"]) for o in group["options"]] == [("Cloud Computing", "Ravi", 5), ("Machine Learning", "Anil", 1)]
    assert len(group["not_chosen"]) == 2
    ml_option = next(o["id"] for o in group["options"] if o["subject_name"] == "Machine Learning")
    cloud_option = next(o["id"] for o in group["options"] if o["subject_name"] == "Cloud Computing")

    # Students choose in the app; Machine Learning has one seat.
    url = f"{API}/me/parent/children/{asha['id']}/electives"
    assert (await client.post(f"{url}/{group['id']}", json={"option_id": ml_option}, headers=asha_h)).status_code == 200
    full = await client.post(f"{API}/me/parent/children/{bala['id']}/electives/{group['id']}", json={"option_id": ml_option}, headers=bala_h)
    assert full.json()["error"]["code"] == "elective_full"
    mine = (await client.post(f"{API}/me/parent/children/{bala['id']}/electives/{group['id']}", json={"option_id": cloud_option}, headers=bala_h)).json()
    assert mine[0]["my_option_id"] == cloud_option
    assert (await client.get(url, headers=asha_h)).json()[0]["my_option_id"] == ml_option

    # Attendance and mark sheets of an elective list only the students who chose it.
    anil_h = auth_headers((await login(client, "ele1-anil@example.com", PASSWORD)).json()["access_token"])
    sheet = (await client.get(f"{API}/subject-attendance/sheet", params={"class_id": batch["id"], "subject_id": ml["id"], "day": "2026-09-01"},
                              headers=anil_h)).json()
    assert [r["full_name"] for r in sheet["rows"]] == ["Asha"]
    exam = (await client.post(f"{API}/exams", json={"name": "Sem 3", "exam_type": "semester", "academic_year": "2026", "class_ids": [batch["id"]],
                                                     "max_marks": "100", "pass_marks": "40"}, headers=admin)).json()
    papers = {p["subject_name"]: p for p in exam["papers"]}
    rows = (await client.get(f"{API}/exam-papers/{papers['Machine Learning']['id']}/marks", headers=admin)).json()["rows"]
    assert [r["full_name"] for r in rows] == ["Asha"]
    for name, marks in (("DBMS", "80"), ("Machine Learning", "90")):
        await client.put(f"{API}/exam-papers/{papers[name]['id']}/marks", json={"entries": [{"student_id": asha["id"], "marks": marks}]}, headers=admin)
    card = (await client.get(f"{API}/exams/{exam['id']}/students/{asha['id']}/report-card", headers=admin)).json()
    # Cloud Computing isn't Asha's elective, so her result is complete without it.
    assert ([p["subject_name"] for p in card["result"]["papers"]], card["result"]["complete"]) == (["DBMS", "Machine Learning"], True)

    # Closed slots can't be changed by students; the admin can still move a student.
    await client.put(f"{API}/electives/{group['id']}/open", json={"is_open": False}, headers=admin)
    closed = await client.post(f"{url}/{group['id']}", json={"option_id": cloud_option}, headers=asha_h)
    assert closed.json()["error"]["code"] == "elective_closed"
    moved = (await client.put(f"{API}/electives/{group['id']}/assign", json={"student_id": asha["id"], "option_id": cloud_option}, headers=admin)).json()
    assert [len(o["students"]) for o in moved["options"]] == [2, 0]
    duplicate = await client.post(f"{API}/electives", json={**body, "name": "Other"}, headers=admin)
    assert duplicate.json()["error"]["code"] == "subject_in_other_slot"


async def test_anonymous_faculty_feedback(db, client):
    ctx = await _setup(client, "FBK1")
    admin = ctx["admin"]
    (asha, asha_h), (bala, bala_h) = ctx["students"]
    rnd = (await client.post(f"{API}/feedback/rounds", json={"title": "Odd semester 2026"}, headers=admin)).json()

    url = f"{API}/me/parent/children/{asha['id']}/feedback"
    rounds = (await client.get(url, headers=asha_h)).json()
    assert [(s["subject_name"], s["teacher_name"], s["done"]) for s in rounds[0]["subjects"]] == [("DBMS", "Ravi", False)]
    body = {"subject_id": ctx["dbms"]["id"], "ratings": [5, 4, 5, 4, 5], "comment": "Very clear"}
    assert (await client.post(f"{url}/{rnd['id']}", json=body, headers=asha_h)).json()[0]["subjects"][0]["done"] is True
    again = await client.post(f"{url}/{rnd['id']}", json=body, headers=asha_h)
    assert again.json()["error"]["code"] == "already_submitted"
    bad = await client.post(f"{url}/{rnd['id']}", json={**body, "ratings": [6, 1, 1, 1, 1]}, headers=asha_h)
    assert bad.status_code == 422
    await client.post(f"{API}/me/parent/children/{bala['id']}/feedback/{rnd['id']}", json={"subject_id": ctx["dbms"]["id"], "ratings": [3, 2, 3, 2, 3]}, headers=bala_h)

    report = (await client.get(f"{API}/feedback/rounds/{rnd['id']}/report", headers=admin)).json()
    ravi = report["faculty"][0]
    assert (ravi["teacher_name"], ravi["department"], ravi["responses"], ravi["students"]) == ("Ravi", "Computer Science", 2, 2)
    assert (ravi["averages"], ravi["overall"], ravi["comments"]) == ([4.0, 3.0, 4.0, 3.0, 4.0], 3.6, ["Very clear"])
    assert "student" not in str(report).lower().replace("students", "")

    # The HOD sees the department; other faculty can't; Ravi sees his own only after the round closes.
    hod_h = auth_headers((await login(client, "fbk1-rao@example.com", PASSWORD)).json()["access_token"])
    ravi_h = auth_headers((await login(client, "fbk1-ravi@example.com", PASSWORD)).json()["access_token"])
    assert len((await client.get(f"{API}/feedback/rounds/{rnd['id']}/report", headers=hod_h)).json()["faculty"]) == 1
    assert (await client.get(f"{API}/feedback/rounds/{rnd['id']}/report", headers=ravi_h)).status_code == 403
    assert (await client.get(f"{API}/feedback/mine", headers=ravi_h)).json() == []
    await client.put(f"{API}/feedback/rounds/{rnd['id']}/open", json={"is_open": False}, headers=admin)
    assert (await client.get(f"{API}/feedback/mine", headers=ravi_h)).json()[0]["faculty"][0]["overall"] == 3.6
    assert (await client.get(url, headers=asha_h)).json() == []


async def test_semester_promotion_with_detention(db, client):
    ctx = await _setup(client, "SEM1")
    admin, batch = ctx["admin"], ctx["batch"]
    (asha, _), (bala, _) = ctx["students"]
    await ctx["subject"]("Operating Systems", semester=4)
    junior = (await client.post(f"{API}/classes", json={"name": "B.Tech CSE", "section": "A", "academic_year": "2027", "class_teacher_id": ctx["hod"]["id"],
                                                         "semester": 3}, headers=admin)).json()
    ravi_h = auth_headers((await login(client, "sem1-ravi@example.com", PASSWORD)).json()["access_token"])
    for period, bala_status in enumerate(["present", "absent", "absent", "absent"], start=1):
        body = {"class_id": batch["id"], "subject_id": ctx["dbms"]["id"], "date": "2026-09-01", "period": period,
                "records": [{"student_id": asha["id"], "status": "present"}, {"student_id": bala["id"], "status": bala_status}]}
        await client.post(f"{API}/subject-attendance", json=body, headers=ravi_h)

    plan = (await client.get(f"{API}/promotion/semester/plan", params={"class_id": batch["id"], "max_backlogs": 2, "min_attendance": 75}, headers=admin)).json()
    students = {s["full_name"]: s for s in plan["students"]}
    assert (plan["semester"], students["Asha"]["eligible"], students["Asha"]["attendance"]) == (3, True, 100.0)
    assert (students["Bala"]["eligible"], students["Bala"]["reasons"]) == (False, ["attendance 25.0% (needs 75%)"])
    assert [t["class_id"] for t in plan["detain_targets"]] == [junior["id"]]

    no_target = await client.post(f"{API}/promotion/semester", json={"class_id": batch["id"], "detain": [bala["id"]]}, headers=admin)
    assert no_target.json()["error"]["code"] == "detain_target"
    result = await client.post(f"{API}/promotion/semester", json={"class_id": batch["id"], "detain": [bala["id"]], "detain_to_class_id": junior["id"]},
                               headers=admin)
    assert result.status_code == 200, result.text
    assert result.json() == {"promoted": 1, "graduated": 0, "detained": 1, "to_semester": 4, "subjects_added": 1}

    classes = {c["id"]: c for c in (await client.get(f"{API}/classes", headers=admin)).json()}
    assert classes[batch["id"]]["semester"] == 4
    subjects = (await client.get(f"{API}/subject-attendance/my-subjects", headers=admin)).json()
    assert sorted((s["class_id"] == batch["id"], s["subject_name"]) for s in subjects if s["class_id"] == batch["id"]) == [(True, "Operating Systems")]
    assert (await fetch_one("SELECT class_id FROM students WHERE id = %s", (bala["id"],)))["class_id"] == junior["id"]

    # Final semester: graduate the batch.
    done = (await client.post(f"{API}/promotion/semester", json={"class_id": batch["id"], "action": "graduate"}, headers=admin)).json()
    assert (done["graduated"], done["to_semester"]) == (1, None)
    assert (await client.get(f"{API}/promotion/semester/plan", params={"class_id": batch["id"]}, headers=admin)).status_code == 404
