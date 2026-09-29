"""Campus modules: library, hostel, transport, placements."""

from datetime import timedelta

from app.db.helpers import execute
from app.modules.alerts.service import today_ist
from tests.factories import auth_headers, create_school, create_user, login

PASSWORD = "Secret123!"
API = "/api/v1"


async def _college(client, code, modules=None):
    school_id = await create_school(code=code, modules=modules)
    await create_user(school_id=school_id, email=f"{code}-admin@example.com".lower(), password=PASSWORD, role="admin")
    admin = auth_headers((await login(client, f"{code}-admin@example.com".lower(), PASSWORD)).json()["access_token"])
    body = {"email": f"{code}-f@example.com".lower(), "full_name": "Anil", "password": PASSWORD}
    faculty = (await client.post(f"{API}/teachers", json=body, headers=admin)).json()
    batch = (await client.post(f"{API}/classes", json={"name": "B.Tech CSE", "section": "A", "academic_year": "2026", "class_teacher_id": faculty["id"]},
                               headers=admin)).json()
    return admin, faculty, batch


async def _student(client, admin, batch, roll, name, login_password=None):
    student = (await client.post(f"{API}/students", json={"admission_number": roll, "full_name": name, "class_id": batch["id"]}, headers=admin)).json()
    headers = None
    if login_password:
        await client.post(f"{API}/students/{student['id']}/login", json={"password": login_password}, headers=admin)
        code = (await client.get(f"{API}/students/{student['id']}", headers=admin)).json()["school_code"]
        token = (await client.post(f"{API}/auth/login", json={"college_code": code, "roll_number": roll, "password": login_password})).json()["access_token"]
        headers = auth_headers(token)
    return student, headers


async def test_library_loans_limits_and_fines(db, client):
    admin, faculty, batch = await _college(client, "LIB1")
    asha, asha_headers = await _student(client, admin, batch, "L1", "Asha", "AshaPass1")
    await client.put(f"{API}/library/settings", json={"loan_days": 7, "fine_per_day": 5, "max_books": 2}, headers=admin)
    book = (await client.post(f"{API}/library/books", json={"title": "Let Us C", "author": "Kanetkar", "total_copies": 1}, headers=admin)).json()
    other = (await client.post(f"{API}/library/books", json={"title": "DBMS", "total_copies": 3}, headers=admin)).json()
    third = (await client.post(f"{API}/library/books", json={"title": "Networks", "total_copies": 3}, headers=admin)).json()

    loan = await client.post(f"{API}/library/loans", json={"book_id": book["id"], "student_id": asha["id"]}, headers=admin)
    assert loan.status_code == 201
    loan = loan.json()
    assert loan["due_on"] == (today_ist() + timedelta(days=7)).isoformat()
    # The only copy is out; faculty can't borrow it.
    busy = await client.post(f"{API}/library/loans", json={"book_id": book["id"], "teacher_id": faculty["id"]}, headers=admin)
    assert busy.json()["error"]["code"] == "no_copies"
    await client.post(f"{API}/library/loans", json={"book_id": other["id"], "student_id": asha["id"]}, headers=admin)
    limit = await client.post(f"{API}/library/loans", json={"book_id": third["id"], "student_id": asha["id"]}, headers=admin)
    assert limit.json()["error"]["code"] == "loan_limit"

    # Three days late: 3 x 5 = 15.
    await execute("UPDATE library_loans SET due_on = %s WHERE id = %s", (today_ist() - timedelta(days=3), loan["id"]))
    overdue = (await client.get(f"{API}/library/loans?view=overdue", headers=admin)).json()
    assert [(l["book_title"], l["overdue_days"], l["fine"]) for l in overdue] == [("Let Us C", 3, 15.0)]
    assert (await client.post(f"{API}/library/loans/{loan['id']}/renew", headers=admin)).status_code == 409
    returned = (await client.post(f"{API}/library/loans/{loan['id']}/return", headers=admin)).json()
    assert (returned["fine"], returned["fine_paid"]) == (15.0, False)
    assert (await client.get(f"{API}/library/summary", headers=admin)).json()["unpaid_fines"] == 15.0
    assert (await client.post(f"{API}/library/loans/{loan['id']}/fine-paid", headers=admin)).json()["fine_paid"] is True

    # The student sees their own loans and can search the catalogue.
    mine = (await client.get(f"{API}/me/parent/children/{asha['id']}/library", headers=asha_headers)).json()
    assert sorted(l["book_title"] for l in mine) == ["DBMS", "Let Us C"]
    assert [b["title"] for b in (await client.get(f"{API}/library/books?q=kanet", headers=asha_headers)).json()] == ["Let Us C"]
    assert (await client.get(f"{API}/library/loans", headers=asha_headers)).status_code == 403


async def test_hostel_capacity_moves_and_portal(db, client):
    admin, _, batch = await _college(client, "HOS1")
    asha, asha_headers = await _student(client, admin, batch, "H1", "Asha", "AshaPass1")
    bala, _ = await _student(client, admin, batch, "H2", "Bala")
    chitra, _ = await _student(client, admin, batch, "H3", "Chitra")
    assert (await client.post(f"{API}/hostels", json={"name": "Girls Hostel", "gender": "girls", "warden_name": "Mrs. Rao"}, headers=admin)).status_code == 204
    hostel = (await client.get(f"{API}/hostels", headers=admin)).json()[0]
    await client.post(f"{API}/hostels/{hostel['id']}/rooms", json={"room_number": "101", "capacity": 2}, headers=admin)
    await client.post(f"{API}/hostels/{hostel['id']}/rooms", json={"room_number": "102", "capacity": 1}, headers=admin)
    rooms = {r["room_number"]: r for r in (await client.get(f"{API}/hostels", headers=admin)).json()[0]["rooms"]}

    for student in (asha, bala):
        assert (await client.post(f"{API}/hostels/allocations", json={"student_id": student["id"], "room_id": rooms["101"]["id"]}, headers=admin)).status_code == 204
    full = await client.post(f"{API}/hostels/allocations", json={"student_id": chitra["id"], "room_id": rooms["101"]["id"]}, headers=admin)
    assert full.json()["error"]["code"] == "room_full"

    stay = (await client.get(f"{API}/me/parent/children/{asha['id']}/hostel", headers=asha_headers)).json()
    assert (stay["hostel_name"], stay["room_number"], stay["roommates"]) == ("Girls Hostel", "101", ["Bala"])

    # Moving Bala frees a bed in 101.
    await client.post(f"{API}/hostels/allocations", json={"student_id": bala["id"], "room_id": rooms["102"]["id"]}, headers=admin)
    listed = (await client.get(f"{API}/hostels", headers=admin)).json()[0]
    assert (listed["capacity"], listed["occupied"]) == (3, 2)
    assert (await client.delete(f"{API}/hostels/rooms/{rooms['102']['id']}", headers=admin)).status_code == 409
    allocation = next(o for r in listed["rooms"] for o in r["occupants"] if o["full_name"] == "Bala")
    assert (await client.delete(f"{API}/hostels/allocations/{allocation['allocation_id']}", headers=admin)).status_code == 204
    assert (await client.delete(f"{API}/hostels/rooms/{rooms['102']['id']}", headers=admin)).status_code == 204


async def test_transport_routes_seats_and_stops(db, client):
    admin, _, batch = await _college(client, "TRN1")
    asha, asha_headers = await _student(client, admin, batch, "T1", "Asha", "AshaPass1")
    bala, _ = await _student(client, admin, batch, "T2", "Bala")
    body = {"name": "Route 1 - Kavali Town", "vehicle_number": "AP39 TA 1234", "seats": 1, "annual_fare": 18000,
            "stops": [{"name": "Bus stand", "pickup_time": "07:45"}, {"name": "Trunk Road", "pickup_time": "07:55"}]}
    assert (await client.post(f"{API}/transport/routes", json=body, headers=admin)).status_code == 204
    route = (await client.get(f"{API}/transport/routes", headers=admin)).json()[0]
    assert [s["name"] for s in route["stops"]] == ["Bus stand", "Trunk Road"]

    stop = route["stops"][1]
    assert (await client.post(f"{API}/transport/assignments", json={"student_id": asha["id"], "route_id": route["id"], "stop_id": stop["id"]}, headers=admin)).status_code == 204
    full = await client.post(f"{API}/transport/assignments", json={"student_id": bala["id"], "route_id": route["id"]}, headers=admin)
    assert full.json()["error"]["code"] == "route_full"

    ride = (await client.get(f"{API}/me/parent/children/{asha['id']}/transport", headers=asha_headers)).json()
    assert (ride["route_name"], ride["stop_name"], ride["pickup_time"]) == ("Route 1 - Kavali Town", "Trunk Road", "07:55")

    # Editing the stops keeps a stop whose name stays, so Asha's stop survives a re-order.
    body["stops"] = [{"name": "Trunk Road", "pickup_time": "07:40"}, {"name": "College", "pickup_time": "08:15"}]
    body["seats"] = 40
    await client.put(f"{API}/transport/routes/{route['id']}", json=body, headers=admin)
    ride = (await client.get(f"{API}/me/parent/children/{asha['id']}/transport", headers=asha_headers)).json()
    assert (ride["stop_name"], ride["pickup_time"]) == ("Trunk Road", "07:40")
    assert (await client.delete(f"{API}/transport/routes/{route['id']}", headers=admin)).status_code == 409


async def test_placements_eligibility_and_selection(db, client):
    admin, faculty, batch = await _college(client, "PLC1")
    cse = (await client.post(f"{API}/departments", json={"name": "Computer Science", "code": "CSE"}, headers=admin)).json()
    ece = (await client.post(f"{API}/departments", json={"name": "Electronics", "code": "ECE"}, headers=admin)).json()
    await client.patch(f"{API}/classes/{batch['id']}", json={"department_id": cse["id"]}, headers=admin)
    asha, asha_headers = await _student(client, admin, batch, "P1", "Asha", "AshaPass1")

    # Asha's CGPA: one published semester exam, 85% in a 4-credit subject -> A+ (9).
    subject = (await client.post(f"{API}/subjects", json={"name": "Maths", "credits": 4}, headers=admin)).json()
    await client.put(f"{API}/classes/{batch['id']}/subjects/{subject['id']}", json={"teacher_id": faculty["id"]}, headers=admin)
    exam = (await client.post(f"{API}/exams", json={"name": "Sem 1", "academic_year": "2026", "class_ids": [batch["id"]], "max_marks": "100", "pass_marks": "40"},
                              headers=admin)).json()
    await client.put(f"{API}/exam-papers/{exam['papers'][0]['id']}/marks", json={"entries": [{"student_id": asha["id"], "marks": "85"}]}, headers=admin)
    await client.post(f"{API}/exams/{exam['id']}/publish", headers=admin)

    await client.post(f"{API}/placements/companies", json={"name": "Infosys", "industry": "IT"}, headers=admin)
    company = (await client.get(f"{API}/placements/companies", headers=admin)).json()[0]

    async def drive(**extra):
        body = {"company_id": company["id"], "role_title": "Systems Engineer", "package_lpa": 3.6, **extra}
        response = await client.post(f"{API}/placements/drives", json=body, headers=admin)
        assert response.status_code == 201, response.text
        return response.json()

    open_drive = await drive(min_cgpa=8.5, eligible_department_ids=[cse["id"]])
    high_bar = await drive(role_title="Specialist Programmer", min_cgpa=9.5)
    ece_only = await drive(role_title="VLSI Trainee", eligible_department_ids=[ece["id"]])
    past = await drive(role_title="Old drive", last_date=(today_ist() - timedelta(days=1)).isoformat())

    mine = {d["role_title"]: d for d in (await client.get(f"{API}/placements/my-drives", headers=asha_headers)).json()}
    assert mine["Systems Engineer"]["eligible"] is True
    assert mine["Specialist Programmer"]["reason"] == "Needs CGPA 9.5 or more (yours is 9.0)."
    assert mine["VLSI Trainee"]["reason"] == "Only for ECE."
    assert mine["Old drive"]["reason"] == "The last date to apply has passed."
    for blocked in (high_bar, ece_only, past):
        assert (await client.post(f"{API}/placements/drives/{blocked['id']}/apply", headers=asha_headers)).json()["error"]["code"] == "not_eligible"

    assert (await client.post(f"{API}/placements/drives/{open_drive['id']}/apply", headers=asha_headers)).status_code == 204
    again = await client.post(f"{API}/placements/drives/{open_drive['id']}/apply", headers=asha_headers)
    assert again.json()["error"]["code"] == "already_applied"

    applications = (await client.get(f"{API}/placements/drives/{open_drive['id']}/applications", headers=admin)).json()
    assert [(a["full_name"], a["department"], a["cgpa"]) for a in applications] == [("Asha", "CSE", 9.0)]
    await client.put(f"{API}/placements/applications/{applications[0]['id']}/status", json={"status": "selected"}, headers=admin)
    # Once acted on, the student can't withdraw.
    assert (await client.delete(f"{API}/placements/drives/{open_drive['id']}/apply", headers=asha_headers)).status_code == 409
    stats = (await client.get(f"{API}/placements/stats", headers=admin)).json()
    assert (stats["students_placed"], stats["highest_package"], stats["open_drives"]) == (1, 3.6, 4)
    mine = {d["role_title"]: d for d in (await client.get(f"{API}/placements/my-drives", headers=asha_headers)).json()}
    assert mine["Systems Engineer"]["my_status"] == "selected"


async def test_campus_modules_can_be_switched_off(db, client):
    admin, _, _ = await _college(client, "OFF1", modules=["dashboard"])
    for path in ("/library/books", "/hostels", "/transport/routes", "/placements/drives"):
        response = await client.get(f"{API}{path}", headers=admin)
        assert response.status_code == 403 and response.json()["error"]["code"] == "module_disabled", path
