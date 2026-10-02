"""Lesson plans and syllabus progress, the question bank, and alumni."""

from app.db.helpers import execute
from tests.factories import auth_headers, create_school, create_user, login

PASSWORD = "Secret123!"
API = "/api/v1"
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


async def _college(client, code):
    school_id = await create_school(code=code)
    await create_user(school_id=school_id, email=f"{code}-admin@example.com".lower(), password=PASSWORD, role="admin")
    admin = auth_headers((await login(client, f"{code}-admin@example.com".lower(), PASSWORD)).json()["access_token"])
    ravi = (await client.post(f"{API}/teachers", json={"email": f"{code}-r@example.com".lower(), "full_name": "Ravi", "password": PASSWORD}, headers=admin)).json()
    anil = (await client.post(f"{API}/teachers", json={"email": f"{code}-a@example.com".lower(), "full_name": "Anil", "password": PASSWORD}, headers=admin)).json()
    batch = (await client.post(f"{API}/classes", json={"name": "B.Tech CSE", "section": "A", "academic_year": "2026", "class_teacher_id": anil["id"],
                                                        "program": "B.Tech"}, headers=admin)).json()
    dbms = (await client.post(f"{API}/subjects", json={"name": "DBMS"}, headers=admin)).json()
    await client.put(f"{API}/classes/{batch['id']}/subjects/{dbms['id']}", json={"teacher_id": ravi["id"]}, headers=admin)
    student = (await client.post(f"{API}/students", json={"admission_number": "S1", "full_name": "Asha", "class_id": batch["id"]}, headers=admin)).json()
    await client.post(f"{API}/students/{student['id']}/login", json={"password": "StudentPass1"}, headers=admin)
    token = (await client.post(f"{API}/auth/login", json={"college_code": code, "roll_number": "S1", "password": "StudentPass1"})).json()["access_token"]
    ravi_h = auth_headers((await login(client, f"{code}-r@example.com".lower(), PASSWORD)).json()["access_token"])
    return admin, ravi_h, batch, dbms, student, auth_headers(token)


async def test_lesson_plan_progress(db, client):
    admin, ravi_h, batch, dbms, asha, asha_h = await _college(client, "LSN1")
    body = {"class_id": batch["id"], "subject_id": dbms["id"],
            "topics": [{"unit": 1, "title": "ER model", "planned_date": "2020-01-10"}, {"unit": 1, "title": "Relational algebra"}, {"unit": 2, "title": "SQL"}]}
    plan = await client.post(f"{API}/lesson-plans", json=body, headers=ravi_h)
    assert plan.status_code == 200, plan.text
    plan = plan.json()
    assert ([t["title"] for t in plan["topics"]], plan["topics"][0]["overdue"], plan["percent"]) == (["ER model", "Relational algebra", "SQL"], True, 0.0)

    done = (await client.put(f"{API}/lesson-plans/topics/{plan['topics'][0]['id']}", json={"completed": True}, headers=ravi_h)).json()
    assert (done["done"], done["percent"], done["topics"][0]["overdue"]) == (1, 33.3, False)

    progress = (await client.get(f"{API}/lesson-plans/progress", headers=admin)).json()
    assert [(p["subject_name"], p["teacher_name"], p["done"], p["total"]) for p in progress] == [("DBMS", "Ravi", 1, 3)]
    assert len((await client.get(f"{API}/lesson-plans/progress", headers=ravi_h)).json()) == 1

    # Another faculty member can't edit Ravi's plan.
    other = auth_headers((await login(client, "lsn1-a@example.com", PASSWORD)).json()["access_token"])  # class teacher: allowed
    assert (await client.get(f"{API}/lesson-plans", params={"class_id": batch["id"], "subject_id": dbms["id"]}, headers=other)).status_code == 200
    syllabus = (await client.get(f"{API}/me/parent/children/{asha['id']}/syllabus", headers=asha_h)).json()
    assert [(s["subject_name"], s["percent"]) for s in syllabus] == [("DBMS", 33.3)]


async def test_question_bank(db, client):
    admin, ravi_h, batch, dbms, asha, asha_h = await _college(client, "QBK1")
    up = await client.post(f"{API}/question-papers", data={"subject_id": dbms["id"], "title": "DBMS Nov 2025", "exam_year": "2025", "regulation": "R20"},
                           files={"file": ("dbms.pdf", PDF, "application/pdf")}, headers=ravi_h)
    assert up.status_code == 201, up.text
    paper = up.json()
    assert (paper["subject_name"], paper["uploaded_by_name"], paper["attachment_name"]) == ("DBMS", "Ravi", "dbms.pdf")

    mine = (await client.get(f"{API}/me/parent/children/{asha['id']}/question-papers", headers=asha_h)).json()
    assert [p["title"] for p in mine] == ["DBMS Nov 2025"]
    got = await client.get(f"{API}/me/parent/children/{asha['id']}/question-papers/{paper['id']}/file", headers=asha_h)
    assert got.status_code == 200 and got.content.startswith(b"%PDF")
    link = (await client.post(f"{API}/me/parent/children/{asha['id']}/question-papers/{paper['id']}/link", headers=asha_h)).json()
    assert (await client.get(f"{API}{link['path']}")).content.startswith(b"%PDF")
    assert (await client.get(f"{API}{link['path'].replace('sig=', 'sig=0')}")).status_code == 403
    bad = await client.post(f"{API}/question-papers", data={"subject_id": dbms["id"], "title": "x.exe"}, files={"file": ("x.exe", b"MZ", "application/x-msdownload")},
                            headers=ravi_h)
    assert bad.status_code in (400, 415, 422)
    assert (await client.delete(f"{API}/question-papers/{paper['id']}", headers=admin)).status_code == 204
    assert (await client.get(f"{API}/me/parent/children/{asha['id']}/question-papers", headers=asha_h)).json() == []


async def test_alumni(db, client):
    admin, ravi_h, batch, dbms, asha, asha_h = await _college(client, "ALM1")
    await execute("UPDATE students SET status = 'graduated', email = 'asha@example.com' WHERE id = %s", (asha["id"],))
    assert (await client.post(f"{API}/alumni/import-graduated", headers=admin)).json() == {"added": 1}
    assert (await client.post(f"{API}/alumni/import-graduated", headers=admin)).json() == {"added": 0}
    listed = (await client.get(f"{API}/alumni", headers=admin)).json()
    asha_alumni = listed[0]
    assert (asha_alumni["full_name"], asha_alumni["passing_year"], asha_alumni["program"], asha_alumni["email"]) == ("Asha", "2026", "B.Tech CSE", "asha@example.com")

    updated = (await client.put(f"{API}/alumni/{asha_alumni['id']}", json={**{k: asha_alumni[k] for k in ("full_name", "admission_number", "passing_year", "program", "email", "phone")},
                                                                        "status": "employed", "organisation": "Infosys", "designation": "Engineer"}, headers=admin)).json()
    assert (updated["status_label"], updated["organisation"]) == ("Employed", "Infosys")
    await client.post(f"{API}/alumni", json={"full_name": "Old Grad", "passing_year": "2019", "status": "higher_studies"}, headers=admin)
    summary = (await client.get(f"{API}/alumni/summary", headers=admin)).json()
    assert [(s["passing_year"], s["total"], s["employed"], s["higher_studies"]) for s in summary] == [("2026", 1, 1, 0), ("2019", 1, 0, 1)]
    assert [a["full_name"] for a in (await client.get(f"{API}/alumni", params={"q": "infosys"}, headers=admin)).json()] == ["Asha"]
    naac = {t["key"]: t for t in (await client.get(f"{API}/reports/naac", headers=admin)).json()["tables"]}
    assert naac["alumni"]["rows"][0] == ["2026", 1, 1, 0, 0]
