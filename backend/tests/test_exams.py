import pytest

from app.modules.exams.service import grade_for
from tests.factories import auth_headers, create_school, create_user, login

PASSWORD = "Secret123!"
API = "/api/v1"


async def _setup(client, code):
    """Grade 5-A: Ravi is class teacher and teaches Maths; Priya teaches English; Kiran teaches nothing here.
    Three students; Asha's mother has a mobile."""
    school_id = await create_school(code=code)
    await create_user(school_id=school_id, email=f"{code}-admin@example.com".lower(), password=PASSWORD, role="admin")
    admin = auth_headers((await login(client, f"{code}-admin@example.com".lower(), PASSWORD)).json()["access_token"])

    async def teacher(key):
        body = {"email": f"{code}-{key}@example.com".lower(), "full_name": key.title(), "password": PASSWORD}
        tid = (await client.post(f"{API}/teachers", json=body, headers=admin)).json()["id"]
        return tid, auth_headers((await login(client, body["email"], PASSWORD)).json()["access_token"])

    ravi_id, ravi = await teacher("ravi")
    priya_id, priya = await teacher("priya")
    _, kiran = await teacher("kiran")
    grade = (await client.post(f"{API}/classes", json={"name": "Grade 5", "section": "A", "academic_year": "2026", "class_teacher_id": ravi_id}, headers=admin)).json()
    maths = (await client.post(f"{API}/subjects", json={"name": "Maths"}, headers=admin)).json()
    english = (await client.post(f"{API}/subjects", json={"name": "English"}, headers=admin)).json()
    await client.put(f"{API}/classes/{grade['id']}/subjects/{maths['id']}", json={"teacher_id": ravi_id}, headers=admin)
    await client.put(f"{API}/classes/{grade['id']}/subjects/{english['id']}", json={"teacher_id": priya_id}, headers=admin)

    students = {}
    for number, name in (("A-1", "Asha"), ("A-2", "Bala"), ("A-3", "Chitra")):
        body = {"admission_number": number, "full_name": name, "class_id": grade["id"]}
        if name == "Asha":
            body["mother"] = {"full_name": "Padma", "phone": "9848022338"}
        students[name] = (await client.post(f"{API}/students", json=body, headers=admin)).json()

    exam = (
        await client.post(
            f"{API}/exams",
            json={"name": "Unit Test 1", "term_label": "Term 1", "academic_year": "2026", "class_ids": [grade["id"]], "max_marks": "50", "pass_marks": "18"},
            headers=admin,
        )
    ).json()
    papers = {p["subject_name"]: p for p in exam["papers"]}
    return {"admin": admin, "ravi": ravi, "priya": priya, "kiran": kiran, "grade": grade, "exam": exam, "papers": papers, "students": students}


async def _save(client, headers, paper, entries):
    return await client.put(f"{API}/exam-papers/{paper['id']}/marks", json={"entries": entries}, headers=headers)


def _entry(ctx, name, marks=None, absent=False):
    return {"student_id": ctx["students"][name]["id"], "marks": marks, "is_absent": absent}


@pytest.mark.parametrize(("pct", "grade"), [(100, "O"), (90, "O"), (89.99, "A+"), (80, "A+"), (72, "A"), (61, "B+"), (55, "B"), (41, "C"), (39.9, "F"), (None, None)])
def test_grade_scale(pct, grade):
    assert grade_for(pct) == grade


async def test_exam_creates_papers_for_class_subjects(db, client):
    ctx = await _setup(client, "EXM1")
    assert sorted(ctx["papers"]) == ["English", "Maths"]
    assert (ctx["papers"]["Maths"]["max_marks"], ctx["papers"]["Maths"]["pass_marks"], ctx["papers"]["Maths"]["teacher_name"]) == (50.0, 18.0, "Ravi")
    assert ctx["exam"]["published"] is False


async def test_who_can_enter_marks(db, client):
    ctx = await _setup(client, "EXM2")
    priya_papers = (await client.get(f"{API}/exam-papers/mine", headers=ctx["priya"])).json()
    assert [p["subject_name"] for p in priya_papers] == ["English"]
    ravi_papers = (await client.get(f"{API}/exam-papers/mine", headers=ctx["ravi"])).json()
    assert sorted(p["subject_name"] for p in ravi_papers) == ["English", "Maths"]  # class teacher: every paper of the class
    assert (await client.get(f"{API}/exam-papers/mine", headers=ctx["kiran"])).json() == []

    assert (await _save(client, ctx["priya"], ctx["papers"]["Maths"], [_entry(ctx, "Asha", "40")])).status_code == 404
    assert (await _save(client, ctx["priya"], ctx["papers"]["English"], [_entry(ctx, "Asha", "40")])).status_code == 200
    too_high = await _save(client, ctx["priya"], ctx["papers"]["English"], [_entry(ctx, "Asha", "51")])
    assert too_high.status_code == 400


async def test_results_grades_pass_fail_and_rank(db, client):
    ctx = await _setup(client, "EXM3")
    await _save(client, ctx["ravi"], ctx["papers"]["Maths"], [_entry(ctx, "Asha", "45"), _entry(ctx, "Bala", "40"), _entry(ctx, "Chitra", "10")])
    await _save(client, ctx["priya"], ctx["papers"]["English"], [_entry(ctx, "Asha", "40"), _entry(ctx, "Bala", "45"), _entry(ctx, "Chitra", None, absent=True)])

    results = (await client.get(f"{API}/exams/{ctx['exam']['id']}/classes/{ctx['grade']['id']}/results", headers=ctx["ravi"])).json()
    by_name = {r["full_name"]: r for r in results["students"]}
    assert (by_name["Asha"]["total"], by_name["Asha"]["percentage"], by_name["Asha"]["grade"]) == (85.0, 85.0, "A+")
    assert (by_name["Asha"]["rank"], by_name["Bala"]["rank"]) == (1, 1)  # tie shares the rank
    assert (by_name["Chitra"]["rank"], by_name["Chitra"]["passed"]) == (3, False)
    chitra_english = next(p for p in by_name["Chitra"]["papers"] if p["subject_name"] == "English")
    assert (chitra_english["is_absent"], chitra_english["grade"], chitra_english["marks"]) == (True, "AB", None)
    maths = next(s for s in results["subject_stats"] if s["subject_name"] == "Maths")
    assert (maths["average"], maths["highest"], maths["passed"], maths["appeared"]) == (31.67, 45.0, 2, 3)

    card = (await client.get(f"{API}/exams/{ctx['exam']['id']}/students/{ctx['students']['Asha']['id']}/report-card", headers=ctx["admin"])).json()
    assert (card["class_teacher_name"], card["class_size"], card["result"]["passed"]) == ("Ravi", 3, True)

    # Subject teachers don't see the whole class's results.
    assert (await client.get(f"{API}/exams/{ctx['exam']['id']}/classes/{ctx['grade']['id']}/results", headers=ctx["priya"])).status_code == 403


async def test_incomplete_results_have_no_rank(db, client):
    ctx = await _setup(client, "EXM4")
    await _save(client, ctx["ravi"], ctx["papers"]["Maths"], [_entry(ctx, "Asha", "45")])
    results = (await client.get(f"{API}/exams/{ctx['exam']['id']}/classes/{ctx['grade']['id']}/results", headers=ctx["admin"])).json()
    asha = next(r for r in results["students"] if r["full_name"] == "Asha")
    assert (asha["complete"], asha["rank"], asha["grade"], asha["passed"]) == (False, None, None, None)


async def test_exam_absence_alerts_parent_once(db, client):
    ctx = await _setup(client, "EXM5")
    await _save(client, ctx["priya"], ctx["papers"]["English"], [_entry(ctx, "Asha", None, absent=True)])
    await _save(client, ctx["priya"], ctx["papers"]["English"], [_entry(ctx, "Asha", None, absent=True)])
    alert_list = (await client.get(f"{API}/parent-alerts", headers=ctx["admin"])).json()
    assert len(alert_list) == 1
    assert "absent for the English exam (Unit Test 1)" in alert_list[0]["message"]


async def test_publish_locks_marks_and_shows_results_to_parents(db, client):
    ctx = await _setup(client, "EXM6")
    asha = ctx["students"]["Asha"]
    await _save(client, ctx["ravi"], ctx["papers"]["Maths"], [_entry(ctx, "Asha", "45")])
    await _save(client, ctx["ravi"], ctx["papers"]["English"], [_entry(ctx, "Asha", "30")])

    parent_pw = (await client.post(f"{API}/students/{asha['id']}/parent-login", json={}, headers=ctx["admin"])).json()["password"]
    parent = auth_headers((await client.post(f"{API}/auth/login", json={"phone": "9848022338", "password": parent_pw})).json()["access_token"])
    results = f"{API}/me/parent/children/{asha['id']}/results"
    assert (await client.get(results, headers=parent)).json() == []  # not published yet

    published = (await client.post(f"{API}/exams/{ctx['exam']['id']}/publish", headers=ctx["admin"])).json()
    assert published["published"] is True
    assert (await _save(client, ctx["ravi"], ctx["papers"]["Maths"], [_entry(ctx, "Asha", "50")])).status_code == 409
    assert (await client.get(f"{API}/exam-papers/mine", headers=ctx["ravi"])).json() == []

    child = (await client.get(results, headers=parent)).json()
    assert (child[0]["report_card"]["result"]["total"], child[0]["report_card"]["result"]["percentage"]) == (75.0, 75.0)

    await client.post(f"{API}/exams/{ctx['exam']['id']}/unpublish", headers=ctx["admin"])
    assert (await _save(client, ctx["ravi"], ctx["papers"]["Maths"], [_entry(ctx, "Asha", "50")])).status_code == 200


async def test_paper_changes_and_exam_deletion(db, client):
    ctx = await _setup(client, "EXM7")
    maths = ctx["papers"]["Maths"]
    changed = await client.patch(f"{API}/exam-papers/{maths['id']}", json={"max_marks": "100", "pass_marks": "35"}, headers=ctx["admin"])
    assert changed.json()["max_marks"] == 100.0
    assert (await client.patch(f"{API}/exam-papers/{maths['id']}", json={"pass_marks": "150"}, headers=ctx["admin"])).status_code == 400
    await _save(client, ctx["ravi"], maths, [_entry(ctx, "Asha", "90")])
    assert (await client.patch(f"{API}/exam-papers/{maths['id']}", json={"max_marks": "50"}, headers=ctx["admin"])).status_code == 409
    assert (await client.delete(f"{API}/exams/{ctx['exam']['id']}", headers=ctx["admin"])).status_code == 409
    assert (await client.post(f"{API}/exams", json={"name": "X", "academic_year": "2026", "class_ids": [ctx["grade"]["id"]]}, headers=ctx["ravi"])).status_code == 403


async def test_clearing_a_mark(db, client):
    ctx = await _setup(client, "EXM8")
    maths = ctx["papers"]["Maths"]
    await _save(client, ctx["ravi"], maths, [_entry(ctx, "Asha", "20")])
    sheet = (await _save(client, ctx["ravi"], maths, [_entry(ctx, "Asha", None)])).json()
    asha = next(r for r in sheet["rows"] if r["full_name"] == "Asha")
    assert (asha["marks"], asha["is_absent"]) == (None, False)
    assert sheet["paper"]["entered"] == 0
