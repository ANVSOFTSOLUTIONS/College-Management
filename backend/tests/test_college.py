"""College structure: departments, batches with semesters, credits, SGPA / CGPA, and student logins."""

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


async def test_sgpa_and_cgpa(db, client):
    admin, hod = await _college(client, "COL2")
    batch = (await client.post(f"{API}/classes", json={"name": "B.Sc", "section": "A", "academic_year": "2026", "class_teacher_id": hod["id"],
                                                        "semester": 1}, headers=admin)).json()
    maths = (await client.post(f"{API}/subjects", json={"name": "Maths", "credits": 4}, headers=admin)).json()
    lab = (await client.post(f"{API}/subjects", json={"name": "Physics Lab", "credits": 2, "subject_type": "lab"}, headers=admin)).json()
    for subject in (maths, lab):
        await client.put(f"{API}/classes/{batch['id']}/subjects/{subject['id']}", json={"teacher_id": hod["id"]}, headers=admin)
    student = (await client.post(f"{API}/students", json={"admission_number": "21A01", "full_name": "Asha", "class_id": batch["id"]}, headers=admin)).json()

    async def exam(name, exam_type, maths_marks, lab_marks):
        created = (await client.post(f"{API}/exams", json={"name": name, "exam_type": exam_type, "academic_year": "2026", "class_ids": [batch["id"]],
                                                            "max_marks": "100", "pass_marks": "40"}, headers=admin)).json()
        assert created["exam_type"] == exam_type
        papers = {p["subject_name"]: p for p in created["papers"]}
        for subject, marks in (("Maths", maths_marks), ("Physics Lab", lab_marks)):
            entry = {"student_id": student["id"], "marks": marks} if marks is not None else {"student_id": student["id"], "is_absent": True}
            await client.put(f"{API}/exam-papers/{papers[subject]['id']}/marks", json={"entries": [entry]}, headers=admin)
        await client.post(f"{API}/exams/{created['id']}/publish", headers=admin)
        return created

    # Semester 1: Maths 92 (O, 10) x 4 credits, Lab 75 (A, 8) x 2 -> SGPA (40 + 16) / 6 = 9.33.
    sem1 = await exam("Sem 1", "semester", "92", "75")
    card = (await client.get(f"{API}/exams/{sem1['id']}/students/{student['id']}/report-card", headers=admin)).json()
    papers = {p["subject_name"]: p for p in card["result"]["papers"]}
    assert (papers["Maths"]["grade"], papers["Maths"]["grade_point"], papers["Physics Lab"]["grade"]) == ("O", 10, "A")
    assert (card["result"]["sgpa"], card["result"]["credits_earned"], card["cgpa"]) == (9.33, 6.0, 9.33)

    # A mid exam doesn't count towards CGPA.
    await exam("Mid 2", "internal", "20", "30")
    # Semester 2: Maths 35 is below the pass mark (F, 0), Lab absent (AB, 0) -> SGPA 0, CGPA 56 / 12 = 4.67.
    sem2 = await exam("Sem 2", "semester", "35", None)
    card = (await client.get(f"{API}/exams/{sem2['id']}/students/{student['id']}/report-card", headers=admin)).json()
    grades = [p["grade"] for p in card["result"]["papers"]]
    assert grades == ["F", "AB"]
    assert (card["result"]["sgpa"], card["result"]["credits_earned"], card["result"]["passed"], card["cgpa"]) == (0.0, 0.0, False, 4.67)


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
