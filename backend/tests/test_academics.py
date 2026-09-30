from tests.factories import auth_headers, create_school, create_student, create_user, login

PASSWORD = "Secret123!"
API = "/api/v1"


async def _admin(client, code):
    school_id = await create_school(code=code)
    email = f"{code.lower()}-admin@example.com"
    await create_user(school_id=school_id, email=email, password=PASSWORD, role="admin")
    response = await login(client, email, PASSWORD)
    return school_id, auth_headers(response.json()["access_token"])


async def _create_teacher(client, headers, email, full_name="Ravi Kumar", **extra):
    body = {"email": email, "full_name": full_name, "password": PASSWORD, **extra}
    response = await client.post(f"{API}/teachers", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def _create_class(client, headers, teacher_id, name="Grade 5", section="A"):
    response = await client.post(
        f"{API}/classes",
        json={"name": name, "section": section, "academic_year": "2026", "class_teacher_id": teacher_id},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


# --- Teachers -----------------------------------------------------------------


async def test_admin_creates_teacher_who_can_log_in(db, client):
    _, headers = await _admin(client, "ACAD1")
    teacher = await _create_teacher(
        client,
        headers,
        "Ravi@Example.com",
        phone="9000000001",
        department="Mathematics",
        qualification="M.Sc, B.Ed",
        employee_code="EMP-1",
        joined_on="2024-06-01",
    )
    assert teacher["email"] == "ravi@example.com"
    assert teacher["qualification"] == "M.Sc, B.Ed"
    assert teacher["status"] == "active"

    listed = (await client.get(f"{API}/teachers", headers=headers)).json()
    assert [t["id"] for t in listed] == [teacher["id"]]

    teacher_login = await login(client, "ravi@example.com", PASSWORD)
    assert teacher_login.status_code == 200
    assert teacher_login.json()["user"]["role"] == "teacher"


async def test_duplicate_email_and_employee_code_are_rejected(db, client):
    _, headers = await _admin(client, "ACAD2")
    await _create_teacher(client, headers, "one@example.com", employee_code="EMP-1")

    same_email = await client.post(
        f"{API}/teachers", json={"email": "ONE@example.com", "full_name": "X", "password": PASSWORD}, headers=headers
    )
    assert same_email.status_code == 409
    assert same_email.json()["error"]["code"] == "email_taken"

    same_code = await client.post(
        f"{API}/teachers",
        json={"email": "two@example.com", "full_name": "Y", "password": PASSWORD, "employee_code": "EMP-1"},
        headers=headers,
    )
    assert same_code.status_code == 409
    assert same_code.json()["error"]["code"] == "employee_code_taken"


async def test_admin_updates_teacher_details_and_password(db, client):
    _, headers = await _admin(client, "ACAD3")
    teacher = await _create_teacher(client, headers, "t3@example.com")

    response = await client.patch(
        f"{API}/teachers/{teacher['id']}",
        json={"full_name": "Ravi K", "phone": "9111111111", "password": "NewSecret99"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["full_name"] == "Ravi K"
    assert response.json()["phone"] == "9111111111"

    assert (await login(client, "t3@example.com", PASSWORD)).status_code == 401
    assert (await login(client, "t3@example.com", "NewSecret99")).status_code == 200


async def test_class_teacher_cannot_be_removed_until_reassigned(db, client):
    _, headers = await _admin(client, "ACAD4")
    ravi = await _create_teacher(client, headers, "ravi4@example.com", full_name="Ravi")
    priya = await _create_teacher(client, headers, "priya4@example.com", full_name="Priya")
    grade = await _create_class(client, headers, ravi["id"])

    blocked = await client.delete(f"{API}/teachers/{ravi['id']}", headers=headers)
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "teacher_is_class_teacher"

    await client.patch(f"{API}/classes/{grade['id']}", json={"class_teacher_id": priya["id"]}, headers=headers)
    removed = await client.delete(f"{API}/teachers/{ravi['id']}", headers=headers)
    assert removed.status_code == 200
    assert removed.json()["status"] == "inactive"
    assert (await login(client, "ravi4@example.com", PASSWORD)).status_code == 401

    reactivated = await client.patch(f"{API}/teachers/{ravi['id']}", json={"status": "active"}, headers=headers)
    assert reactivated.json()["status"] == "active"
    assert (await login(client, "ravi4@example.com", PASSWORD)).status_code == 200


async def test_removing_teacher_clears_their_subjects(db, client):
    _, headers = await _admin(client, "ACAD5")
    class_teacher = await _create_teacher(client, headers, "ct5@example.com", full_name="Class Teacher")
    subject_teacher = await _create_teacher(client, headers, "st5@example.com", full_name="Subject Teacher")
    grade = await _create_class(client, headers, class_teacher["id"])
    maths = (await client.post(f"{API}/subjects", json={"name": "Maths"}, headers=headers)).json()
    await client.put(
        f"{API}/classes/{grade['id']}/subjects/{maths['id']}", json={"teacher_id": subject_teacher["id"]}, headers=headers
    )

    await client.delete(f"{API}/teachers/{subject_teacher['id']}", headers=headers)
    detail = (await client.get(f"{API}/classes/{grade['id']}", headers=headers)).json()
    assert detail["subjects"] == []


# --- Subjects -----------------------------------------------------------------


async def test_subject_crud_and_duplicate_name(db, client):
    _, headers = await _admin(client, "ACAD6")
    created = await client.post(f"{API}/subjects", json={"name": "Telugu", "code": "TEL"}, headers=headers)
    assert created.status_code == 201
    subject_id = created.json()["id"]

    duplicate = await client.post(f"{API}/subjects", json={"name": "Telugu"}, headers=headers)
    assert duplicate.status_code == 409

    renamed = await client.put(f"{API}/subjects/{subject_id}", json={"name": "Telugu (L1)", "code": "TEL"}, headers=headers)
    assert renamed.json()["name"] == "Telugu (L1)"

    assert (await client.delete(f"{API}/subjects/{subject_id}", headers=headers)).status_code == 204
    assert (await client.get(f"{API}/subjects", headers=headers)).json() == []


# --- Classes ------------------------------------------------------------------


async def test_class_with_class_teacher_and_subject_teachers(db, client):
    _, headers = await _admin(client, "ACAD7")
    ravi = await _create_teacher(client, headers, "ravi7@example.com", full_name="Ravi")
    priya = await _create_teacher(client, headers, "priya7@example.com", full_name="Priya")
    maths = (await client.post(f"{API}/subjects", json={"name": "Maths"}, headers=headers)).json()
    english = (await client.post(f"{API}/subjects", json={"name": "English"}, headers=headers)).json()

    grade = await _create_class(client, headers, ravi["id"], name="Grade 6", section="B")
    assert grade["class_teacher"]["full_name"] == "Ravi"

    await client.put(f"{API}/classes/{grade['id']}/subjects/{maths['id']}", json={"teacher_id": ravi["id"]}, headers=headers)
    await client.put(f"{API}/classes/{grade['id']}/subjects/{english['id']}", json={"teacher_id": priya["id"]}, headers=headers)
    # Reassigning a subject replaces its teacher.
    detail = (
        await client.put(f"{API}/classes/{grade['id']}/subjects/{maths['id']}", json={"teacher_id": priya["id"]}, headers=headers)
    ).json()
    assert {s["subject_name"]: s["teacher"]["full_name"] for s in detail["subjects"]} == {"English": "Priya", "Maths": "Priya"}

    priya_view = (await client.get(f"{API}/teachers/{priya['id']}", headers=headers)).json()
    assert sorted(s["subject_name"] for s in priya_view["subjects"]) == ["English", "Maths"]

    after = (await client.delete(f"{API}/classes/{grade['id']}/subjects/{english['id']}", headers=headers)).json()
    assert [s["subject_name"] for s in after["subjects"]] == ["Maths"]

    listed = (await client.get(f"{API}/classes", headers=headers)).json()
    assert listed[0]["class_teacher_name"] == "Ravi"
    assert listed[0]["student_count"] == 0


async def test_duplicate_class_section_is_rejected(db, client):
    _, headers = await _admin(client, "ACAD8")
    ravi = await _create_teacher(client, headers, "ravi8@example.com")
    await _create_class(client, headers, ravi["id"])
    duplicate = await client.post(
        f"{API}/classes",
        json={"name": "Grade 5", "section": "A", "academic_year": "2026", "class_teacher_id": ravi["id"]},
        headers=headers,
    )
    assert duplicate.status_code == 409


async def test_class_with_students_cannot_be_deleted(db, client):
    school_id, headers = await _admin(client, "ACAD9")
    ravi = await _create_teacher(client, headers, "ravi9@example.com")
    grade = await _create_class(client, headers, ravi["id"])
    empty = await _create_class(client, headers, ravi["id"], section="B")
    await create_student(school_id=school_id, class_id=grade["id"], admission_number="S1", full_name="Asha")

    blocked = await client.delete(f"{API}/classes/{grade['id']}", headers=headers)
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "class_has_students"
    assert (await client.delete(f"{API}/classes/{empty['id']}", headers=headers)).status_code == 204


async def test_inactive_or_other_school_teacher_cannot_be_assigned(db, client):
    _, headers = await _admin(client, "ACADA")
    _, other_headers = await _admin(client, "ACADB")
    outsider = await _create_teacher(client, other_headers, "outsider@example.com")
    ravi = await _create_teacher(client, headers, "ravia@example.com")
    grade = await _create_class(client, headers, ravi["id"])
    maths = (await client.post(f"{API}/subjects", json={"name": "Maths"}, headers=headers)).json()

    response = await client.put(
        f"{API}/classes/{grade['id']}/subjects/{maths['id']}", json={"teacher_id": outsider["id"]}, headers=headers
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_teacher"

    # Other schools' teachers and classes are invisible.
    assert (await client.get(f"{API}/teachers/{outsider['id']}", headers=headers)).status_code == 404
    assert (await client.get(f"{API}/classes/{grade['id']}", headers=other_headers)).status_code == 404


async def test_teachers_cannot_use_admin_endpoints(db, client):
    _, headers = await _admin(client, "ACADC")
    await _create_teacher(client, headers, "tc@example.com")
    teacher_headers = auth_headers((await login(client, "tc@example.com", PASSWORD)).json()["access_token"])

    for method, path in [("get", "/teachers"), ("get", "/subjects"), ("post", "/subjects")]:
        response = await getattr(client, method)(f"{API}{path}", headers=teacher_headers, **({"json": {"name": "X"}} if method == "post" else {}))
        assert response.status_code == 403
