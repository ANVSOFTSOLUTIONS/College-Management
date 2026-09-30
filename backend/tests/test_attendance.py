from tests.factories import (
    auth_headers,
    create_class,
    create_school,
    create_student,
    create_teacher,
    create_user,
    login,
)


async def _setup_school_with_class(db, *, code, teacher_email):
    school_id = await create_school(code=code)
    teacher_user_id = await create_user(
        school_id=school_id, email=teacher_email, password="Secret123!", role="teacher"
    )
    teacher_id = await create_teacher(school_id=school_id, user_id=teacher_user_id)
    class_id = await create_class(school_id=school_id, teacher_id=teacher_id)
    student_ids = [
        await create_student(school_id=school_id, class_id=class_id, admission_number="S1", full_name="Alice"),
        await create_student(school_id=school_id, class_id=class_id, admission_number="S2", full_name="Bob"),
    ]
    return school_id, teacher_id, class_id, student_ids


async def test_teacher_can_view_own_class_roster(db, client):
    school_id, teacher_id, class_id, student_ids = await _setup_school_with_class(
        db, code="ROSTER1", teacher_email="roster-teacher@example.com"
    )
    login_response = await login(client, "roster-teacher@example.com", "Secret123!")
    token = login_response.json()["access_token"]

    response = await client.get(f"/api/v1/classes/{class_id}/students", headers=auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert len(body["students"]) == 2
    assert {s["full_name"] for s in body["students"]} == {"Alice", "Bob"}


async def test_teacher_cannot_access_other_teachers_class_same_school(db, client):
    school_id = await create_school(code="SAMESCHOOL")
    owner_user_id = await create_user(
        school_id=school_id, email="owner@example.com", password="Secret123!", role="teacher"
    )
    owner_teacher_id = await create_teacher(school_id=school_id, user_id=owner_user_id)
    class_id = await create_class(school_id=school_id, teacher_id=owner_teacher_id)

    other_user_id = await create_user(
        school_id=school_id, email="other@example.com", password="Secret123!", role="teacher"
    )
    await create_teacher(school_id=school_id, user_id=other_user_id)

    login_response = await login(client, "other@example.com", "Secret123!")
    token = login_response.json()["access_token"]

    response = await client.get(f"/api/v1/classes/{class_id}/students", headers=auth_headers(token))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


async def test_teacher_from_other_school_cannot_see_class_exists(db, client):
    _, _, class_id, _ = await _setup_school_with_class(db, code="SCHOOL_A", teacher_email="a-teacher@example.com")
    await create_school(code="SCHOOL_B")
    other_user_id = await create_user(
        school_id=(await create_school(code="SCHOOL_C")),
        email="b-teacher@example.com",
        password="Secret123!",
        role="teacher",
    )

    login_response = await login(client, "b-teacher@example.com", "Secret123!")
    token = login_response.json()["access_token"]

    response = await client.get(f"/api/v1/classes/{class_id}/students", headers=auth_headers(token))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "class_not_found"


async def test_admin_can_access_any_class_in_their_school(db, client):
    school_id, _, class_id, _ = await _setup_school_with_class(
        db, code="ADMINACCESS", teacher_email="admin-scope-teacher@example.com"
    )
    await create_user(
        school_id=school_id, email="admin@example.com", password="Secret123!", role="admin"
    )

    login_response = await login(client, "admin@example.com", "Secret123!")
    token = login_response.json()["access_token"]

    response = await client.get(f"/api/v1/classes/{class_id}/students", headers=auth_headers(token))

    assert response.status_code == 200


async def test_mark_and_retrieve_attendance(db, client):
    school_id, teacher_id, class_id, student_ids = await _setup_school_with_class(
        db, code="MARKATT", teacher_email="mark-teacher@example.com"
    )
    login_response = await login(client, "mark-teacher@example.com", "Secret123!")
    token = login_response.json()["access_token"]
    headers = auth_headers(token)

    mark_response = await client.post(
        f"/api/v1/classes/{class_id}/attendance",
        headers=headers,
        json={
            "date": "2026-09-20",
            "records": [
                {"student_id": str(student_ids[0]), "status": "present"},
                {"student_id": str(student_ids[1]), "status": "absent"},
            ],
        },
    )
    assert mark_response.status_code == 200
    assert mark_response.json()["marked_count"] == 2

    get_response = await client.get(
        f"/api/v1/classes/{class_id}/attendance", headers=headers, params={"date": "2026-09-20"}
    )
    assert get_response.status_code == 200
    entries = {entry["student_id"]: entry["status"] for entry in get_response.json()["entries"]}
    assert entries[str(student_ids[0])] == "present"
    assert entries[str(student_ids[1])] == "absent"


async def test_mark_attendance_rejects_student_outside_roster(db, client):
    school_id, teacher_id, class_id, student_ids = await _setup_school_with_class(
        db, code="BADSTUDENT", teacher_email="badstudent-teacher@example.com"
    )
    login_response = await login(client, "badstudent-teacher@example.com", "Secret123!")
    token = login_response.json()["access_token"]

    response = await client.post(
        f"/api/v1/classes/{class_id}/attendance",
        headers=auth_headers(token),
        json={"date": "2026-09-20", "records": [{"student_id": "0" * 24, "status": "present"}]},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "unknown_student"


async def test_teacher_lists_only_own_classes(db, client):
    school_id = await create_school(code="LISTCLASSES")
    teacher_user_id = await create_user(
        school_id=school_id, email="list-teacher@example.com", password="Secret123!", role="teacher"
    )
    teacher_id = await create_teacher(school_id=school_id, user_id=teacher_user_id)
    await create_class(school_id=school_id, teacher_id=teacher_id, name="Grade 6", section="B")

    other_teacher_user_id = await create_user(
        school_id=school_id, email="other-list-teacher@example.com", password="Secret123!", role="teacher"
    )
    other_teacher_id = await create_teacher(school_id=school_id, user_id=other_teacher_user_id)
    await create_class(school_id=school_id, teacher_id=other_teacher_id, name="Grade 7", section="C")

    login_response = await login(client, "list-teacher@example.com", "Secret123!")
    token = login_response.json()["access_token"]

    response = await client.get("/api/v1/classes", headers=auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["name"] == "Grade 6"


async def test_admin_lists_all_classes_in_school(db, client):
    school_id = await create_school(code="ADMINLISTCLASSES")
    teacher_user_id = await create_user(
        school_id=school_id, email="admin-list-teacher@example.com", password="Secret123!", role="teacher"
    )
    teacher_id = await create_teacher(school_id=school_id, user_id=teacher_user_id)
    await create_class(school_id=school_id, teacher_id=teacher_id, name="Grade 8", section="A")
    await create_class(school_id=school_id, teacher_id=teacher_id, name="Grade 9", section="A")
    await create_user(school_id=school_id, email="admin-list@example.com", password="Secret123!", role="admin")

    login_response = await login(client, "admin-list@example.com", "Secret123!")
    token = login_response.json()["access_token"]

    response = await client.get("/api/v1/classes", headers=auth_headers(token))

    assert response.status_code == 200
    assert len(response.json()) == 2


async def test_unauthenticated_request_rejected(db, client):
    _, _, class_id, _ = await _setup_school_with_class(
        db, code="NOAUTH", teacher_email="noauth-teacher@example.com"
    )

    response = await client.get(f"/api/v1/classes/{class_id}/students")

    assert response.status_code == 401
