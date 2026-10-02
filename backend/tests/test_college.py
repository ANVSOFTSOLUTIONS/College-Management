"""College structure: departments, batches with semesters, credits, SGPA / CGPA, and student logins."""

from app.db.helpers import execute
from app.modules.alerts.service import today_ist
from tests.factories import auth_headers, create_school, create_user, login

PASSWORD = "Secret123!"
API = "/api/v1"


async def _college(client, code):
    school_id = await create_school(code=code)
    await create_user(school_id=school_id, email=f"{code}-admin@example.com".lower(), password=PASSWORD, role="admin")
    admin = auth_headers((await login(client, f"{code}-admin@example.com".lower(), PASSWORD)).json()["access_token"])
    body = {"email": f"{code}-hod@example.com".lower(), "full_name": "Dr. Rao", "password": PASSWORD}
    hod = (await client.post(f"{API}/teachers", json=body, headers=admin)).json()
    return admin, hod


async def _student_login(client, code, roll, password):
    return await client.post(f"{API}/auth/login", json={"college_code": code, "roll_number": roll, "password": password})


async def test_departments_batches_and_subject_credits(db, client):
    admin, hod = await _college(client, "COL1")
    cse = await client.post(f"{API}/departments", json={"name": "Computer Science", "code": "cse", "hod_teacher_id": hod["id"]}, headers=admin)
    assert cse.status_code == 201
    cse = cse.json()
    assert (cse["code"], cse["hod"]["full_name"]) == ("CSE", "Dr. Rao")
    duplicate = await client.post(f"{API}/departments", json={"name": "CS again", "code": "CSE"}, headers=admin)
    assert duplicate.status_code == 409

    # Faculty joined to a department take its name.
    body = {"email": "col1-f@example.com", "full_name": "Anil", "password": PASSWORD, "department_id": cse["id"], "designation": "Assistant Professor"}
    faculty = (await client.post(f"{API}/teachers", json=body, headers=admin)).json()
    assert (faculty["department"], faculty["designation"], faculty["department_id"]) == ("Computer Science", "Assistant Professor", cse["id"])

    batch = await client.post(
        f"{API}/classes",
        json={"name": "B.Tech CSE", "section": "A", "academic_year": "2026-27", "class_teacher_id": faculty["id"],
              "department_id": cse["id"], "program": "B.Tech", "semester": 3, "regulation": "R23"},
        headers=admin,
    )
    assert batch.status_code == 201
    batch = batch.json()
    assert (batch["department_name"], batch["program"], batch["semester"], batch["regulation"]) == ("Computer Science", "B.Tech", 3, "R23")
    listed = (await client.get(f"{API}/classes", headers=admin)).json()
    assert (listed[0]["department_name"], listed[0]["semester"]) == ("Computer Science", 3)

    subject = (await client.post(f"{API}/subjects", json={"name": "Data Structures", "code": "CS301", "credits": 4, "subject_type": "theory",
                                                           "department_id": cse["id"], "semester": 3}, headers=admin)).json()
    assert (subject["credits"], subject["subject_type"], subject["semester"]) == (4.0, "theory", 3)

    departments = (await client.get(f"{API}/departments", headers=admin)).json()
    assert (departments[0]["faculty_count"], departments[0]["class_count"]) == (1, 1)
    # A department with batches can't be deleted.
    assert (await client.delete(f"{API}/departments/{cse['id']}", headers=admin)).status_code == 409


async def _graded_batch(client, code):
    """A batch with Maths (4 credits) and Physics Lab (2 credits), faculty and one student."""
    admin, hod = await _college(client, code)
    batch = (await client.post(f"{API}/classes", json={"name": "B.Sc", "section": "A", "academic_year": "2026", "class_teacher_id": hod["id"],
                                                        "semester": 1}, headers=admin)).json()
    maths = (await client.post(f"{API}/subjects", json={"name": "Maths", "credits": 4}, headers=admin)).json()
    lab = (await client.post(f"{API}/subjects", json={"name": "Physics Lab", "credits": 2, "subject_type": "lab"}, headers=admin)).json()
    for subject in (maths, lab):
        await client.put(f"{API}/classes/{batch['id']}/subjects/{subject['id']}", json={"teacher_id": hod["id"]}, headers=admin)
    student = (await client.post(f"{API}/students", json={"admission_number": "21A01", "full_name": "Asha", "class_id": batch["id"]}, headers=admin)).json()
    published = [0]

    async def exam(name, exam_type, marks, **extra):
        """Creates and publishes an exam; marks maps subject name to marks out of 100 (None = absent, missing = not written)."""
        body = {"name": name, "exam_type": exam_type, "academic_year": "2026", "class_ids": [batch["id"]], "max_marks": "100", "pass_marks": "40", **extra}
        created = await client.post(f"{API}/exams", json=body, headers=admin)
        assert created.status_code == 201, created.text
        created = created.json()
        for paper in created["papers"]:
            if paper["subject_name"] not in marks:
                continue
            value = marks[paper["subject_name"]]
            entry = {"student_id": student["id"], "marks": str(value)} if value is not None else {"student_id": student["id"], "is_absent": True}
            saved = await client.put(f"{API}/exam-papers/{paper['id']}/marks", json={"entries": [entry]}, headers=admin)
            assert saved.status_code == 200, saved.text
        await client.post(f"{API}/exams/{created['id']}/publish", headers=admin)
        # Publish times a minute apart, so "latest attempt" is well defined.
        published[0] += 1
        await execute("UPDATE exams SET published_at = TIMESTAMPADD(MINUTE, %s, '2026-06-01 10:00:00') WHERE id = %s", (published[0], created["id"]))
        return created

    async def card(exam_id):
        return (await client.get(f"{API}/exams/{exam_id}/students/{student['id']}/report-card", headers=admin)).json()

    return admin, batch, student, exam, card


async def test_sgpa_and_cgpa(db, client):
    admin, batch, student, exam, card = await _graded_batch(client, "COL2")

    # Maths 92 (O, 10) x 4 credits, Lab 75 (A, 8) x 2 -> SGPA (40 + 16) / 6 = 9.33.
    sem1 = await exam("Sem 1", "semester", {"Maths": 92, "Physics Lab": 75})
    result = await card(sem1["id"])
    papers = {p["subject_name"]: p for p in result["result"]["papers"]}
    assert (papers["Maths"]["grade"], papers["Maths"]["grade_point"], papers["Physics Lab"]["grade"]) == ("O", 10, "A")
    assert (result["result"]["sgpa"], result["result"]["credits_earned"], result["cgpa"]) == (9.33, 6.0, 9.33)

    # An internal exam doesn't count towards CGPA.
    await exam("Mid 2", "internal", {"Maths": 20, "Physics Lab": 30})
    assert (await card(sem1["id"]))["cgpa"] == 9.33


async def test_backlog_cleared_by_supplementary(db, client):
    admin, batch, student, exam, card = await _graded_batch(client, "COL7")
    sem1 = await exam("Sem 1", "semester", {"Maths": 35, "Physics Lab": 75})
    result = await card(sem1["id"])
    # Maths below the pass mark: F, no credits. SGPA (0 x 4 + 8 x 2) / 6 = 2.67.
    assert ([p["grade"] for p in result["result"]["papers"]], result["result"]["sgpa"], result["cgpa"]) == (["F", "A"], 2.67, 2.67)

    backlogs = (await client.get(f"{API}/exams/backlogs", params={"class_id": batch["id"]}, headers=admin)).json()
    assert [(b["full_name"], [x["subject_name"] for x in b["backlogs"]]) for b in backlogs] == [("Asha", ["Maths"])]

    # The supplementary mark sheet lists only students with a backlog in the subject.
    supp = (await client.post(f"{API}/exams", json={"name": "Sem 1 Supplementary", "exam_type": "supplementary", "academic_year": "2026",
                                                     "class_ids": [batch["id"]], "max_marks": "100", "pass_marks": "40"}, headers=admin)).json()
    maths_paper = next(p for p in supp["papers"] if p["subject_name"] == "Maths")
    lab_paper = next(p for p in supp["papers"] if p["subject_name"] == "Physics Lab")
    assert [r["full_name"] for r in (await client.get(f"{API}/exam-papers/{maths_paper['id']}/marks", headers=admin)).json()["rows"]] == ["Asha"]
    assert (await client.get(f"{API}/exam-papers/{lab_paper['id']}/marks", headers=admin)).json()["rows"] == []
    await client.delete(f"{API}/exams/{supp['id']}", headers=admin)

    # Passing the supplementary replaces the F: Maths 70 (A, 8) -> CGPA (8 x 4 + 8 x 2) / 6 = 8.0.
    supp = await exam("Sem 1 Supplementary", "supplementary", {"Maths": 70})
    result = await card(supp["id"])
    assert ([p["subject_name"] for p in result["result"]["papers"]], result["cgpa"]) == (["Maths"], 8.0)
    assert (await client.get(f"{API}/exams/backlogs", params={"class_id": batch["id"]}, headers=admin)).json() == []


async def test_internal_and_external_marks_combined(db, client):
    admin, batch, student, exam, card = await _graded_batch(client, "COL8")
    mid1 = await exam("Mid 1", "internal", {"Maths": 80, "Physics Lab": 100})
    mid2 = await exam("Mid 2", "internal", {"Maths": 60, "Physics Lab": None})  # absent in the lab mid
    bad = await client.post(f"{API}/exams", json={"name": "X", "exam_type": "internal", "academic_year": "2026", "class_ids": [batch["id"]],
                                                   "internal_exam_ids": [mid1["id"]], "internal_weight": 30}, headers=admin)
    assert bad.json()["error"]["code"] == "internals_only_for_semester"

    # Internal 30 + external 70. Maths: internal avg 70% -> 21; semester 50/100 -> 35; total 56 (B).
    # Lab: internal avg 50% -> 15; semester 30/100 -> 21 -> below the semester pass mark: F.
    sem = await exam("Sem 1", "semester", {"Maths": 50, "Physics Lab": 30}, internal_exam_ids=[mid1["id"], mid2["id"]], internal_weight=30)
    assert (sem["internal_exam_ids"], sem["internal_weight"]) == ([mid1["id"], mid2["id"]], 30)
    papers = {p["subject_name"]: p for p in (await card(sem["id"]))["result"]["papers"]}
    assert (papers["Maths"]["internal"], papers["Maths"]["external"], papers["Maths"]["combined"], papers["Maths"]["grade"]) == (21.0, 35.0, 56.0, "B")
    assert (papers["Physics Lab"]["combined"], papers["Physics Lab"]["grade"]) == (36.0, "F")

    backlogs = (await client.get(f"{API}/me/parent/children/{student['id']}/backlogs", headers=await _login_student(client, admin, student, "COL8"))).json()
    assert [(b["subject_name"], b["grade"]) for b in backlogs] == [("Physics Lab", "F")]


async def _login_student(client, admin, student, code):
    await client.post(f"{API}/students/{student['id']}/login", json={"password": "StudentPass1"}, headers=admin)
    return auth_headers((await _student_login(client, code, student["admission_number"], "StudentPass1")).json()["access_token"])


async def test_student_login_and_portal(db, client):
    admin, hod = await _college(client, "COL3")
    batch = (await client.post(f"{API}/classes", json={"name": "MBA", "section": "A", "academic_year": "2026", "class_teacher_id": hod["id"]}, headers=admin)).json()
    asha = (await client.post(f"{API}/students", json={"admission_number": "22MBA01", "full_name": "Asha", "class_id": batch["id"],
                                                        "email": "asha@student.edu", "phone": "9848022338", "quota": "Convener"}, headers=admin)).json()
    bala = (await client.post(f"{API}/students", json={"admission_number": "22MBA02", "full_name": "Bala", "class_id": batch["id"]}, headers=admin)).json()
    assert (asha["email"], asha["quota"]) == ("asha@student.edu", "Convener")

    credentials = await client.post(f"{API}/students/{asha['id']}/login", json={"password": "AshaPass1"}, headers=admin)
    assert credentials.status_code == 200
    assert (credentials.json()["school_code"], credentials.json()["admission_number"]) == ("COL3", "22MBA01")

    # Code and roll number are case-insensitive; the student must change the password first.
    signed_in = await _student_login(client, "col3", "22mba01", "AshaPass1")
    assert signed_in.status_code == 200
    user = signed_in.json()["user"]
    assert (user["role"], user["must_change_password"]) == ("student", True)
    student = auth_headers(signed_in.json()["access_token"])

    # The portal shows only their own record.
    mine = (await client.get(f"{API}/me/parent/children", headers=student)).json()
    assert [c["full_name"] for c in mine] == ["Asha"]
    assert (await client.get(f"{API}/me/parent/children/{asha['id']}", headers=student)).status_code == 200
    assert (await client.get(f"{API}/me/parent/children/{bala['id']}", headers=student)).status_code == 404
    assert (await client.get(f"{API}/me/parent/children/{asha['id']}/results", headers=student)).status_code == 200
    assert (await client.get(f"{API}/notices", headers=student)).status_code == 200
    # ...and none of the staff screens.
    assert (await client.get(f"{API}/students", headers=student)).status_code == 403

    # Bulk: only Bala still needs a login.
    bulk = (await client.post(f"{API}/students/logins", json={"class_id": batch["id"]}, headers=admin)).json()
    assert [c["full_name"] for c in bulk] == ["Bala"]
    assert (await _student_login(client, "COL3", "22MBA02", bulk[0]["password"])).status_code == 200

    # A new roll number moves the sign-in id; switching the login off blocks sign-in.
    await client.patch(f"{API}/students/{asha['id']}", json={"admission_number": "22MBA99"}, headers=admin)
    assert (await _student_login(client, "COL3", "22MBA01", "AshaPass1")).status_code == 401
    assert (await _student_login(client, "COL3", "22MBA99", "AshaPass1")).status_code == 200
    await client.delete(f"{API}/students/{asha['id']}/login", headers=admin)
    assert (await _student_login(client, "COL3", "22MBA99", "AshaPass1")).status_code == 401

    # A student's own login doesn't count as a parent login.
    detail = (await client.get(f"{API}/students/{bala['id']}", headers=admin)).json()
    assert (detail["login_enabled"], detail["parent_login_phone"]) == (True, None)


async def test_students_see_student_notices(db, client):
    admin, hod = await _college(client, "COL4")
    batch = (await client.post(f"{API}/classes", json={"name": "BCA", "section": "A", "academic_year": "2026", "class_teacher_id": hod["id"]}, headers=admin)).json()
    student = (await client.post(f"{API}/students", json={"admission_number": "R1", "full_name": "Ravi", "class_id": batch["id"]}, headers=admin)).json()
    await client.post(f"{API}/students/{student['id']}/login", json={"password": "RaviPass1"}, headers=admin)
    headers = auth_headers((await _student_login(client, "COL4", "R1", "RaviPass1")).json()["access_token"])

    for title, for_students, for_parents in (("Exam timetable out", True, False), ("Parents meeting", False, True)):
        body = {"title": title, "body": "Details inside.", "for_students": for_students, "for_parents": for_parents}
        assert (await client.post(f"{API}/notices", json=body, headers=admin)).status_code == 201
    titles = [n["title"] for n in (await client.get(f"{API}/notices", headers=headers)).json()]
    assert titles == ["Exam timetable out"]


async def test_student_app_calls(db, client):
    """The calls the mobile app makes for a student: home, assignments, timetable, leave."""
    admin, hod = await _college(client, "COL5")
    batch = (await client.post(f"{API}/classes", json={"name": "BBA", "section": "A", "academic_year": "2026", "class_teacher_id": hod["id"]}, headers=admin)).json()
    student = (await client.post(f"{API}/students", json={"admission_number": "S5", "full_name": "Sita", "class_id": batch["id"]}, headers=admin)).json()
    await client.post(f"{API}/students/{student['id']}/login", json={"password": "SitaPass1"}, headers=admin)
    headers = auth_headers((await _student_login(client, "COL5", "S5", "SitaPass1")).json()["access_token"])

    children = (await client.get(f"{API}/me/parent/children", headers=headers)).json()
    sid = children[0]["student_id"]
    assert (await client.get(f"{API}/me/parent/children/{sid}", headers=headers)).status_code == 200
    assert (await client.get(f"{API}/homework", params={"student_id": sid}, headers=headers)).status_code == 200
    assert (await client.get(f"{API}/timetable/mine", params={"student_id": sid}, headers=headers)).status_code == 200
    for what in ("library", "hostel", "transport"):
        assert (await client.get(f"{API}/me/parent/children/{sid}/{what}", headers=headers)).status_code == 200
    body = {"student_id": sid, "leave_type": "sick", "from_date": "2026-10-05", "to_date": "2026-10-06", "reason": "Fever"}
    applied = await client.post(f"{API}/leave", json=body, headers=headers)
    assert applied.status_code == 201, applied.text
    mine = (await client.get(f"{API}/leave/mine", headers=headers)).json()
    assert [(l["applicant_name"], l["days"]) for l in mine] == [("Sita", 2)]


async def test_hod_dashboard_and_faculty_leave(db, client):
    admin, hod = await _college(client, "COL6")
    cse = (await client.post(f"{API}/departments", json={"name": "Computer Science", "code": "CSE", "hod_teacher_id": hod["id"]}, headers=admin)).json()
    ece = (await client.post(f"{API}/departments", json={"name": "Electronics", "code": "ECE"}, headers=admin)).json()
    await client.patch(f"{API}/teachers/{hod['id']}", json={"department_id": cse["id"]}, headers=admin)
    body = {"email": "col6-f@example.com", "full_name": "Anil", "password": PASSWORD, "department_id": cse["id"]}
    anil = (await client.post(f"{API}/teachers", json=body, headers=admin)).json()
    body = {"email": "col6-e@example.com", "full_name": "Ravi", "password": PASSWORD, "department_id": ece["id"]}
    await client.post(f"{API}/teachers", json=body, headers=admin)
    batch = (await client.post(f"{API}/classes", json={"name": "B.Tech CSE", "section": "A", "academic_year": "2026", "class_teacher_id": anil["id"],
                                                        "department_id": cse["id"], "semester": 3}, headers=admin)).json()
    student = (await client.post(f"{API}/students", json={"admission_number": "C1", "full_name": "Asha", "class_id": batch["id"]}, headers=admin)).json()

    hod_login = (await login(client, "col6-hod@example.com", PASSWORD)).json()
    assert hod_login["user"]["is_hod"] is True
    assert (await login(client, "col6-f@example.com", PASSWORD)).json()["user"]["is_hod"] is False
    hod_headers = auth_headers(hod_login["access_token"])
    anil_headers = auth_headers((await login(client, "col6-f@example.com", PASSWORD)).json()["access_token"])
    ravi_headers = auth_headers((await login(client, "col6-e@example.com", PASSWORD)).json()["access_token"])

    # Anil marks Asha absent; she shows up as low attendance.
    await client.post(f"{API}/classes/{batch['id']}/attendance", json={"date": today_ist().isoformat(), "records": [{"student_id": student["id"], "status": "absent"}]},
                      headers=anil_headers)
    await client.post(f"{API}/staff-punch/in", headers=anil_headers)
    overview = (await client.get(f"{API}/hod/overview", headers=hod_headers)).json()
    dept = overview["departments"][0]
    assert dept["code"] == "CSE"
    assert {f["full_name"]: f["status"] for f in dept["faculty"]}.keys() == {"Dr. Rao", "Anil"}
    assert {f["full_name"]: f["status"] for f in dept["faculty"]}["Dr. Rao"] == "not_in"
    assert [(b["name"], b["marked"], b["absent"]) for b in dept["batches"]] == [("B.Tech CSE", True, 1)]
    assert [(s["full_name"], s["percent"]) for s in dept["low_attendance"]] == [("Asha", 0.0)]
    assert (await client.get(f"{API}/hod/overview", headers=anil_headers)).status_code == 403

    # The HOD reviews CSE faculty leave, not ECE's.
    leave = {"leave_type": "casual", "from_date": "2026-10-05", "to_date": "2026-10-05", "reason": "Family function"}
    anil_leave = (await client.post(f"{API}/leave", json=leave, headers=anil_headers)).json()
    ravi_leave = (await client.post(f"{API}/leave", json=leave, headers=ravi_headers)).json()
    inbox = (await client.get(f"{API}/leave/inbox", headers=hod_headers)).json()
    assert [(l["applicant_name"], l["can_review"]) for l in inbox] == [("Anil", True)]
    assert (await client.get(f"{API}/hod/overview", headers=hod_headers)).json()["pending_leaves"] == 1
    assert (await client.post(f"{API}/leave/{ravi_leave['id']}/review", json={"status": "approved", "note": ""}, headers=hod_headers)).status_code == 403
    approved = await client.post(f"{API}/leave/{anil_leave['id']}/review", json={"status": "approved", "note": ""}, headers=hod_headers)
    assert approved.json()["status"] == "approved"


async def test_college_website_details_and_live_placements(db, client):
    admin, hod = await _college(client, "WEB1")
    await client.post(f"{API}/departments", json={"name": "Computer Science", "code": "CSE"}, headers=admin)
    info = {
        "established": "1998",
        "accreditation": "NAAC A+ | AICTE approved",
        "highlights": [{"value": "25+", "label": "Years"}, {"value": "3000+", "label": "Students"}],
        "programs": [{"name": "B.Tech CSE", "level": "UG", "duration": "4 years", "seats": "180", "description": "Core computing."}],
        "principal_name": "Dr. K. Rao",
        "principal_title": "Principal",
        "principal_message": "Welcome to our campus.",
    }
    saved = await client.put(f"{API}/school-site/college-info", json=info, headers=admin)
    assert saved.status_code == 200, saved.text
    site = saved.json()
    assert (site["established"], site["highlights"][1]["value"], site["programs"][0]["seats"]) == ("1998", "3000+", "180")
    assert [d["code"] for d in site["departments"]] == ["CSE"]

    # No one placed yet: no placements block on the public site.
    public = (await client.get(f"{API}/public/schools/WEB1/site")).json()
    assert public["principal_name"] == "Dr. K. Rao" and public["placements"] is None

    batch = (await client.post(f"{API}/classes", json={"name": "B.Tech", "section": "A", "academic_year": "2026", "class_teacher_id": hod["id"]}, headers=admin)).json()
    student = (await client.post(f"{API}/students", json={"admission_number": "W1", "full_name": "Asha", "class_id": batch["id"]}, headers=admin)).json()
    await client.post(f"{API}/students/{student['id']}/login", json={"password": "AshaPass1"}, headers=admin)
    asha = auth_headers((await _student_login(client, "WEB1", "W1", "AshaPass1")).json()["access_token"])
    await client.post(f"{API}/placements/companies", json={"name": "Infosys"}, headers=admin)
    company = (await client.get(f"{API}/placements/companies", headers=admin)).json()[0]
    drive = (await client.post(f"{API}/placements/drives", json={"company_id": company["id"], "role_title": "SE", "package_lpa": 4.5}, headers=admin)).json()
    await client.post(f"{API}/placements/drives/{drive['id']}/apply", headers=asha)
    application = (await client.get(f"{API}/placements/drives/{drive['id']}/applications", headers=admin)).json()[0]
    await client.put(f"{API}/placements/applications/{application['id']}/status", json={"status": "selected"}, headers=admin)

    placements = (await client.get(f"{API}/public/schools/WEB1/site")).json()["placements"]
    assert (placements["recruiters"], placements["students_placed"], placements["highest_package"]) == (["Infosys"], 1, 4.5)
    assert (await client.put(f"{API}/school-site/customize", json={"hidden_sections": ["placements", "programs"]}, headers=admin)).status_code == 200


async def test_subject_wise_attendance(db, client):
    admin, hod = await _college(client, "COL9")
    anil = (await client.post(f"{API}/teachers", json={"email": "col9-a@example.com", "full_name": "Anil", "password": PASSWORD}, headers=admin)).json()
    ravi = (await client.post(f"{API}/teachers", json={"email": "col9-r@example.com", "full_name": "Ravi", "password": PASSWORD}, headers=admin)).json()
    batch = (await client.post(f"{API}/classes", json={"name": "B.Tech CSE", "section": "A", "academic_year": "2026", "class_teacher_id": hod["id"]}, headers=admin)).json()
    ds = (await client.post(f"{API}/subjects", json={"name": "Data Structures"}, headers=admin)).json()
    dbms = (await client.post(f"{API}/subjects", json={"name": "DBMS"}, headers=admin)).json()
    await client.put(f"{API}/classes/{batch['id']}/subjects/{ds['id']}", json={"teacher_id": anil["id"]}, headers=admin)
    await client.put(f"{API}/classes/{batch['id']}/subjects/{dbms['id']}", json={"teacher_id": ravi["id"]}, headers=admin)
    asha = (await client.post(f"{API}/students", json={"admission_number": "S1", "full_name": "Asha", "class_id": batch["id"]}, headers=admin)).json()
    bala = (await client.post(f"{API}/students", json={"admission_number": "S2", "full_name": "Bala", "class_id": batch["id"]}, headers=admin)).json()
    anil_h = auth_headers((await login(client, "col9-a@example.com", PASSWORD)).json()["access_token"])

    mine = (await client.get(f"{API}/subject-attendance/my-subjects", headers=anil_h)).json()
    assert [(m["class_name"], m["subject_name"]) for m in mine] == [("B.Tech CSE", "Data Structures")]
    # Anil can't mark Ravi's subject.
    body = {"class_id": batch["id"], "subject_id": dbms["id"], "date": "2026-09-01", "records": [{"student_id": asha["id"], "status": "present"}]}
    assert (await client.post(f"{API}/subject-attendance", json=body, headers=anil_h)).status_code == 403

    # Four Data Structures hours: Asha attends all (one late), Bala attends two.
    for i, (a, b) in enumerate([("present", "present"), ("late", "absent"), ("present", "absent"), ("present", "present")]):
        body = {"class_id": batch["id"], "subject_id": ds["id"], "date": "2026-09-01", "period": i + 1,
                "records": [{"student_id": asha["id"], "status": a}, {"student_id": bala["id"], "status": b}]}
        saved = await client.post(f"{API}/subject-attendance", json=body, headers=anil_h)
        assert saved.status_code == 200 and saved.json()["marked"], saved.text
    sheet = (await client.get(f"{API}/subject-attendance/sheet", params={"class_id": batch["id"], "subject_id": ds["id"], "day": "2026-09-01", "period": 2},
                              headers=anil_h)).json()
    assert [(r["full_name"], r["status"]) for r in sheet["rows"]] == [("Asha", "late"), ("Bala", "absent")]

    summary = {s["full_name"]: s["subjects"] for s in (await client.get(f"{API}/subject-attendance/summary", params={"class_id": batch["id"]}, headers=admin)).json()}
    assert [(x["subject_name"], x["percent"], x["short"]) for x in summary["Asha"]] == [("Data Structures", 100.0, False)]
    assert [(x["held"], x["attended"], x["percent"], x["short"]) for x in summary["Bala"]] == [(4, 2, 50.0, True)]

    await client.post(f"{API}/students/{bala['id']}/login", json={"password": "BalaPass12"}, headers=admin)
    bala_h = auth_headers((await _student_login(client, "COL9", "S2", "BalaPass12")).json()["access_token"])
    mine = (await client.get(f"{API}/me/parent/children/{bala['id']}/subject-attendance", headers=bala_h)).json()
    assert [(x["subject_name"], x["percent"], x["short"]) for x in mine] == [("Data Structures", 50.0, True)]
