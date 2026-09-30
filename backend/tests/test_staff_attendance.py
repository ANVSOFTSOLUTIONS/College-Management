from tests.factories import auth_headers, create_school, create_teacher, create_user, login

PASSWORD = "Secret123!"


async def _setup_school(*, code, admin_email, teacher_names):
    school_id = await create_school(code=code)
    await create_user(school_id=school_id, email=admin_email, password=PASSWORD, role="admin")
    teacher_ids = []
    for index, name in enumerate(teacher_names, start=1):
        user_id = await create_user(
            school_id=school_id,
            email=f"{code.lower()}-teacher{index}@example.com",
            password=PASSWORD,
            role="teacher",
            full_name=name,
        )
        teacher_ids.append(await create_teacher(school_id=school_id, user_id=user_id, department="Maths"))
    return school_id, teacher_ids


async def _admin_headers(client, email):
    response = await login(client, email, PASSWORD)
    return auth_headers(response.json()["access_token"])


async def test_admin_marks_and_reads_staff_attendance(db, client):
    _, (ravi, priya) = await _setup_school(
        code="STAFF1", admin_email="staff1-admin@example.com", teacher_names=["Ravi", "Priya"]
    )
    headers = await _admin_headers(client, "staff1-admin@example.com")

    before = await client.get("/api/v1/staff-attendance", params={"date": "2026-09-25"}, headers=headers)
    assert before.status_code == 200
    assert [(e["full_name"], e["status"]) for e in before.json()["entries"]] == [("Priya", None), ("Ravi", None)]

    marked = await client.post(
        "/api/v1/staff-attendance",
        json={"date": "2026-09-25", "records": [{"teacher_id": ravi, "status": "leave"}, {"teacher_id": priya, "status": "present"}]},
        headers=headers,
    )
    assert marked.status_code == 200
    assert marked.json()["marked_count"] == 2

    # Re-marking the same day updates rather than duplicating.
    await client.post(
        "/api/v1/staff-attendance",
        json={"date": "2026-09-25", "records": [{"teacher_id": ravi, "status": "late"}]},
        headers=headers,
    )
    after = await client.get("/api/v1/staff-attendance", params={"date": "2026-09-25"}, headers=headers)
    assert {e["full_name"]: e["status"] for e in after.json()["entries"]} == {"Priya": "present", "Ravi": "late"}

    other_day = await client.get("/api/v1/staff-attendance", params={"date": "2026-09-24"}, headers=headers)
    assert all(e["status"] is None for e in other_day.json()["entries"])


async def test_teacher_cannot_access_staff_attendance(db, client):
    await _setup_school(code="STAFF2", admin_email="staff2-admin@example.com", teacher_names=["Ravi"])
    teacher = await login(client, "staff2-teacher1@example.com", PASSWORD)
    headers = auth_headers(teacher.json()["access_token"])

    response = await client.get("/api/v1/staff-attendance", params={"date": "2026-09-25"}, headers=headers)
    assert response.status_code == 403


async def test_admin_cannot_mark_or_see_other_schools_teachers(db, client):
    await _setup_school(code="STAFFA", admin_email="staffa-admin@example.com", teacher_names=["Ravi"])
    _, (other_teacher,) = await _setup_school(
        code="STAFFB", admin_email="staffb-admin@example.com", teacher_names=["Outsider"]
    )
    headers = await _admin_headers(client, "staffa-admin@example.com")

    listed = await client.get("/api/v1/staff-attendance", params={"date": "2026-09-25"}, headers=headers)
    assert [e["full_name"] for e in listed.json()["entries"]] == ["Ravi"]

    response = await client.post(
        "/api/v1/staff-attendance",
        json={"date": "2026-09-25", "records": [{"teacher_id": other_teacher, "status": "present"}]},
        headers=headers,
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "unknown_teacher"


async def test_invalid_status_is_rejected(db, client):
    _, (ravi,) = await _setup_school(code="STAFF3", admin_email="staff3-admin@example.com", teacher_names=["Ravi"])
    headers = await _admin_headers(client, "staff3-admin@example.com")

    response = await client.post(
        "/api/v1/staff-attendance",
        json={"date": "2026-09-25", "records": [{"teacher_id": ravi, "status": "holiday"}]},
        headers=headers,
    )
    assert response.status_code == 422
