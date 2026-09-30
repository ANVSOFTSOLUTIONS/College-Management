import pytest

from app.modules.promotion.service import next_year, suggest_target
from tests.factories import auth_headers, create_school, create_user, login

API = "/api/v1"
PASSWORD = "Secret123!"


@pytest.mark.parametrize(("year", "expected"), [("2026", "2027"), ("2026-27", "2027-28"), ("2026-2027", "2027-2028"), ("x", "")])
def test_next_year(year, expected):
    assert next_year(year) == expected


def test_suggest_target():
    names = {"LKG", "UKG", "Grade 1", "Grade 2", "Grade 10"}
    assert suggest_target("LKG", names) == "UKG"
    assert suggest_target("UKG", names) == "Grade 1"
    assert suggest_target("Grade 1", names) == "Grade 2"
    assert suggest_target("Grade 2", names) is None  # no Grade 3: looks like the last class
    assert suggest_target("Grade 10", names) is None


async def _school(client, code="PRO1"):
    school_id = await create_school(code=code)
    await create_user(school_id=school_id, email=f"{code}-admin@example.com".lower(), password=PASSWORD, role="admin")
    admin = auth_headers((await login(client, f"{code}-admin@example.com".lower(), PASSWORD)).json()["access_token"])
    ravi = (await client.post(f"{API}/teachers", json={"email": f"{code}-ravi@example.com".lower(), "full_name": "Ravi", "password": PASSWORD}, headers=admin)).json()
    priya = (await client.post(f"{API}/teachers", json={"email": f"{code}-priya@example.com".lower(), "full_name": "Priya", "password": PASSWORD}, headers=admin)).json()
    grade1 = (await client.post(f"{API}/classes", json={"name": "Grade 1", "section": "A", "academic_year": "2026", "class_teacher_id": ravi["id"]}, headers=admin)).json()
    grade2 = (await client.post(f"{API}/classes", json={"name": "Grade 2", "section": "A", "academic_year": "2026", "class_teacher_id": priya["id"]}, headers=admin)).json()
    maths = (await client.post(f"{API}/subjects", json={"name": "Maths"}, headers=admin)).json()
    await client.put(f"{API}/classes/{grade2['id']}/subjects/{maths['id']}", json={"teacher_id": priya["id"]}, headers=admin)

    async def student(class_id, number, name):
        return (await client.post(f"{API}/students", json={"admission_number": number, "full_name": name, "class_id": class_id}, headers=admin)).json()

    students = {
        "asha": await student(grade1["id"], "1", "Asha"),
        "bala": await student(grade1["id"], "2", "Bala"),
        "chitra": await student(grade2["id"], "3", "Chitra"),
    }
    return admin, grade1, grade2, students


async def test_plan_suggests_next_class_and_graduation(db, client):
    admin, grade1, grade2, _ = await _school(client)
    plan = (await client.get(f"{API}/promotion/plan", headers=admin)).json()
    assert (plan["from_year"], plan["suggested_to_year"], plan["already_promoted_to"]) == ("2026", "2027", None)
    by_name = {c["name"]: c for c in plan["classes"]}
    assert (by_name["Grade 1"]["suggested_action"], by_name["Grade 1"]["suggested_target_name"]) == ("promote", "Grade 2")
    assert by_name["Grade 2"]["suggested_action"] == "graduate"
    assert len(by_name["Grade 1"]["students"]) == 2


async def test_promotion_moves_keeps_back_and_graduates(db, client):
    admin, grade1, grade2, students = await _school(client)
    # Chitra has Grade 2 results from this year.
    exam = (await client.post(f"{API}/exams", json={"name": "Final", "academic_year": "2026", "class_ids": [grade2["id"]]}, headers=admin)).json()
    await client.put(f"{API}/exam-papers/{exam['papers'][0]['id']}/marks", json={"entries": [{"student_id": students["chitra"]["id"], "marks": "80"}]}, headers=admin)
    await client.post(f"{API}/exams/{exam['id']}/publish", headers=admin)

    body = {
        "from_year": "2026",
        "to_year": "2027",
        "classes": [
            {"class_id": grade1["id"], "action": "promote", "target_name": "Grade 2", "keep_back": [students["bala"]["id"]]},
            {"class_id": grade2["id"], "action": "graduate"},
        ],
    }
    result = (await client.post(f"{API}/promotion", json=body, headers=admin)).json()
    assert result == {"promoted": 1, "kept_back": 1, "graduated": 1, "classes_created": 2}

    classes = {(c["name"], c["academic_year"]): c for c in (await client.get(f"{API}/classes", headers=admin)).json()}
    assert set(classes) == {("Grade 1", "2027"), ("Grade 2", "2027")}  # 2026 classes archived
    new_grade2 = classes[("Grade 2", "2027")]
    assert new_grade2["class_teacher_name"] == "Priya"  # copied from last year's Grade 2
    detail = (await client.get(f"{API}/classes/{new_grade2['id']}", headers=admin)).json()
    assert [s["subject_name"] for s in detail["subjects"]] == ["Maths"]

    active = {s["full_name"]: s["class"]["name"] for s in (await client.get(f"{API}/students", headers=admin)).json()}
    assert active == {"Asha": "Grade 2", "Bala": "Grade 1"}
    everyone = {s["full_name"]: s["status"] for s in (await client.get(f"{API}/students", params={"include_left": "true"}, headers=admin)).json()}
    assert everyone["Chitra"] == "graduated"

    # Last year's results survive the move.
    results = (await client.get(f"{API}/exams/{exam['id']}/classes/{grade2['id']}/results", headers=admin)).json()
    assert [s["full_name"] for s in results["students"]] == ["Chitra"]
    card = (await client.get(f"{API}/exams/{exam['id']}/students/{students['chitra']['id']}/report-card", headers=admin)).json()
    assert card["result"]["total"] == 80.0

    again = await client.post(f"{API}/promotion", json=body, headers=admin)
    assert again.status_code == 409


async def test_promotion_must_cover_every_class(db, client):
    admin, grade1, _, _ = await _school(client, "PRO2")
    partial = {"from_year": "2026", "to_year": "2027", "classes": [{"class_id": grade1["id"], "action": "promote", "target_name": "Grade 2"}]}
    response = await client.post(f"{API}/promotion", json=partial, headers=admin)
    assert response.status_code == 400 and response.json()["error"]["code"] == "classes_missing"
    same_year = {**partial, "to_year": "2026"}
    assert (await client.post(f"{API}/promotion", json=same_year, headers=admin)).status_code == 422


async def test_parent_still_sees_last_years_report_card_after_promotion(db, client):
    admin, grade1, grade2, students = await _school(client, "PRO3")
    await client.patch(f"{API}/students/{students['asha']['id']}", json={"mother": {"full_name": "Padma", "phone": "9848022370"}, "primary_contact": "mother"}, headers=admin)
    parent_pw = (await client.post(f"{API}/students/{students['asha']['id']}/parent-login", json={}, headers=admin)).json()["password"]
    maths = (await client.get(f"{API}/subjects", headers=admin)).json()[0]
    await client.put(f"{API}/classes/{grade1['id']}/subjects/{maths['id']}", json={"teacher_id": (await client.get(f"{API}/teachers", headers=admin)).json()[0]["id"]}, headers=admin)
    exam = (await client.post(f"{API}/exams", json={"name": "Annual", "academic_year": "2026", "class_ids": [grade1["id"]]}, headers=admin)).json()
    await client.put(f"{API}/exam-papers/{exam['papers'][0]['id']}/marks", json={"entries": [{"student_id": students["asha"]["id"], "marks": "91"}]}, headers=admin)
    await client.post(f"{API}/exams/{exam['id']}/publish", headers=admin)
    body = {"from_year": "2026", "to_year": "2027", "classes": [
        {"class_id": grade1["id"], "action": "promote", "target_name": "Grade 2"},
        {"class_id": grade2["id"], "action": "graduate"},
    ]}
    await client.post(f"{API}/promotion", json=body, headers=admin)

    token = (await client.post(f"{API}/auth/login", json={"phone": "9848022370", "password": parent_pw})).json()["access_token"]
    mine = (await client.get(f"{API}/me/parent/children/{students['asha']['id']}/results", headers=auth_headers(token))).json()
    assert [(r["report_card"]["exam_name"], r["report_card"]["class_name"], r["report_card"]["result"]["grade"]) for r in mine] == [("Annual", "Grade 1", "O")]
