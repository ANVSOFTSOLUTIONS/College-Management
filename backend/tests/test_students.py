from tests.factories import auth_headers, create_class, create_school, create_teacher, create_user, login

PASSWORD = "Secret123!"
API = "/api/v1"

FATHER = {"full_name": "Srinivas Rao", "phone": "9000000001", "email": "srinivas@example.com", "occupation": "Farmer"}
MOTHER = {"full_name": "Padma Rao", "phone": "9000000002"}


async def _school(client, code):
    """A school with an admin, two teachers each owning one class."""
    school_id = await create_school(code=code)
    await create_user(school_id=school_id, email=f"{code}-admin@example.com".lower(), password=PASSWORD, role="admin")
    classes = {}
    for key, name in (("a", "Grade 1"), ("b", "Grade 2")):
        user_id = await create_user(
            school_id=school_id, email=f"{code}-teacher-{key}@example.com".lower(), password=PASSWORD, role="teacher"
        )
        teacher_id = await create_teacher(school_id=school_id, user_id=user_id)
        classes[key] = await create_class(school_id=school_id, teacher_id=teacher_id, name=name)

    async def headers(who):
        email = f"{code}-{who}@example.com".lower()
        return auth_headers((await login(client, email, PASSWORD)).json()["access_token"])

    return classes, headers


async def _add(client, headers, class_id, admission_number, **extra):
    body = {"admission_number": admission_number, "full_name": f"Student {admission_number}", "class_id": class_id, **extra}
    return await client.post(f"{API}/students", json=body, headers=headers)


async def test_admin_adds_student_with_parents(db, client):
    classes, headers = await _school(client, "STU1")
    admin = await headers("admin")

    response = await _add(
        client,
        admin,
        classes["a"],
        "A-1",
        date_of_birth="2018-04-12",
        gender="female",
        blood_group="B+",
        address="Madhapur, Hyderabad",
        father=FATHER,
        mother=MOTHER,
        guardian={"full_name": "Rama Rao", "relation_label": "Grandfather", "phone": "9000000003"},
        primary_contact="mother",
    )
    assert response.status_code == 201, response.text
    student = response.json()
    assert student["class"]["name"] == "Grade 1"
    assert [g["relation"] for g in student["guardians"]] == ["father", "mother", "guardian"]
    assert student["guardians"][2]["relation_label"] == "Grandfather"
    assert student["primary_contact"] == "mother"

    listed = (await client.get(f"{API}/students", headers=admin)).json()
    assert listed[0]["primary_contact_name"] == "Padma Rao"
    assert listed[0]["primary_contact_phone"] == "9000000002"


async def test_primary_contact_must_exist_and_defaults_sensibly(db, client):
    classes, headers = await _school(client, "STU2")
    admin = await headers("admin")

    bad = await _add(client, admin, classes["a"], "A-1", father=FATHER, primary_contact="mother")
    assert bad.status_code == 422

    ok = (await _add(client, admin, classes["a"], "A-2", mother=MOTHER)).json()
    assert ok["primary_contact"] == "mother"

    # Removing the primary contact falls back to another guardian.
    updated = (
        await client.patch(f"{API}/students/{ok['id']}", json={"father": FATHER, "mother": None}, headers=admin)
    ).json()
    assert [g["relation"] for g in updated["guardians"]] == ["father"]
    assert updated["primary_contact"] == "father"


async def test_duplicate_admission_number_is_rejected(db, client):
    classes, headers = await _school(client, "STU3")
    admin = await headers("admin")
    await _add(client, admin, classes["a"], "A-1")
    duplicate = await _add(client, admin, classes["b"], "A-1")
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "admission_number_taken"


async def test_class_teacher_manages_only_their_own_class(db, client):
    classes, headers = await _school(client, "STU4")
    admin, teacher_a = await headers("admin"), await headers("teacher-a")
    in_b = (await _add(client, admin, classes["b"], "B-1")).json()

    created = await _add(client, teacher_a, classes["a"], "A-1", father=FATHER)
    assert created.status_code == 201
    assert (await _add(client, teacher_a, classes["b"], "B-2")).status_code == 403

    listed = (await client.get(f"{API}/students", headers=teacher_a)).json()
    assert [s["admission_number"] for s in listed] == ["A-1"]
    assert (await client.get(f"{API}/students", params={"class_id": classes["b"]}, headers=teacher_a)).status_code == 403
    assert (await client.get(f"{API}/students/{in_b['id']}", headers=teacher_a)).status_code == 404
    assert (await client.patch(f"{API}/students/{in_b['id']}", json={"full_name": "X"}, headers=teacher_a)).status_code == 404

    # Can edit their own student, but not move them into someone else's class or mark them left.
    own = created.json()["id"]
    assert (await client.patch(f"{API}/students/{own}", json={"address": "New address"}, headers=teacher_a)).status_code == 200
    assert (await client.patch(f"{API}/students/{own}", json={"class_id": classes["b"]}, headers=teacher_a)).status_code == 403
    assert (await client.patch(f"{API}/students/{own}", json={"status": "left"}, headers=teacher_a)).status_code == 403
    assert (await client.delete(f"{API}/students/{own}", headers=teacher_a)).status_code == 403


async def test_left_students_drop_out_of_lists_and_rosters(db, client):
    classes, headers = await _school(client, "STU5")
    admin = await headers("admin")
    staying = (await _add(client, admin, classes["a"], "A-1")).json()
    leaving = (await _add(client, admin, classes["a"], "A-2")).json()

    left = await client.delete(f"{API}/students/{leaving['id']}", headers=admin)
    assert left.json()["status"] == "left"

    active = (await client.get(f"{API}/students", headers=admin)).json()
    assert [s["id"] for s in active] == [staying["id"]]
    everyone = (await client.get(f"{API}/students", params={"include_left": "true"}, headers=admin)).json()
    assert len(everyone) == 2

    roster = (await client.get(f"{API}/classes/{classes['a']}/students", headers=admin)).json()
    assert [s["id"] for s in roster["students"]] == [staying["id"]]


async def test_search_by_name_or_admission_number(db, client):
    classes, headers = await _school(client, "STU6")
    admin = await headers("admin")
    await client.post(f"{API}/students", json={"admission_number": "GW-1", "full_name": "Asha", "class_id": classes["a"]}, headers=admin)
    await client.post(f"{API}/students", json={"admission_number": "GW-2", "full_name": "Ravi", "class_id": classes["a"]}, headers=admin)

    by_name = (await client.get(f"{API}/students", params={"q": "ash"}, headers=admin)).json()
    assert [s["full_name"] for s in by_name] == ["Asha"]
    by_number = (await client.get(f"{API}/students", params={"q": "GW-2"}, headers=admin)).json()
    assert [s["full_name"] for s in by_number] == ["Ravi"]


async def test_other_schools_students_are_invisible(db, client):
    classes_x, headers_x = await _school(client, "STUX")
    classes_y, headers_y = await _school(client, "STUY")
    student = (await _add(client, await headers_x("admin"), classes_x["a"], "X-1")).json()
    admin_y = await headers_y("admin")

    assert (await client.get(f"{API}/students/{student['id']}", headers=admin_y)).status_code == 404
    assert (await client.get(f"{API}/students", headers=admin_y)).json() == []
    assert (await _add(client, admin_y, classes_x["a"], "Y-1")).status_code == 400
