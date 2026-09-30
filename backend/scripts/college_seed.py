"""Sample college for local use and demos: python -m scripts.college_seed

Creates a super admin and "ANV College of Engineering, Kavali" (code ANVCOL) with
departments, faculty, batches, credit-based subjects, students with their own
logins and parent logins, a published semester-end exam, and fees. Everything
after the college and its admin goes through the API, so the same rules apply
as in the app. Safe to re-run: it stops if the college already exists.

Prints every login it creates.
"""

import asyncio
import json
import uuid

from httpx import ASGITransport, AsyncClient

from app.core.modules import OPTIONAL_MODULES
from app.core.security import hash_password
from app.db.database import close_mysql_connection, connect_to_mysql
from app.db.helpers import execute, fetch_one
from app.main import app

CODE = "ANVCOL"
NAME = "ANV College of Engineering, Kavali"
SUPER_ADMIN = ("superadmin@anvcollege.in", "Super@12345")
ADMIN = ("admin@anvcollege.in", "Admin@12345")
FACULTY_PASSWORD = "Faculty@12345"
PARENT_PASSWORD = "Parent@123"
YEAR = "2026-27"

DEPARTMENTS = [
    ("Computer Science & Engineering", "CSE", "Dr. K. Srinivasa Rao"),
    ("Electronics & Communication Engineering", "ECE", "Dr. P. Lakshmi"),
    ("Master of Business Administration", "MBA", "Dr. M. Venkatesh"),
]
FACULTY = [  # name, department code, designation, subjects they teach
    ("Mr. R. Anil Kumar", "CSE", "Assistant Professor", ["Data Structures", "Data Structures Lab"]),
    ("Mrs. S. Padmaja", "CSE", "Associate Professor", ["Database Management Systems", "Discrete Mathematics"]),
    ("Mr. T. Ravi Teja", "ECE", "Assistant Professor", ["Signals & Systems", "Electronic Devices Lab"]),
    ("Mrs. G. Swathi", "MBA", "Assistant Professor", ["Management & Organisational Behaviour", "Financial Accounting"]),
]
SUBJECTS = [  # name, code, credits, type, department code, semester
    ("Data Structures", "CS301", 3, "theory", "CSE", 3),
    ("Database Management Systems", "CS302", 3, "theory", "CSE", 3),
    ("Discrete Mathematics", "MA301", 3, "theory", "CSE", 3),
    ("Data Structures Lab", "CS351", 1.5, "lab", "CSE", 3),
    ("Signals & Systems", "EC301", 3, "theory", "ECE", 3),
    ("Electronic Devices Lab", "EC351", 1.5, "lab", "ECE", 3),
    ("Management & Organisational Behaviour", "MB101", 4, "theory", "MBA", 1),
    ("Financial Accounting", "MB102", 4, "theory", "MBA", 1),
]
BATCHES = [  # batch name, department code, program, semester, mentor, students
    ("B.Tech CSE", "CSE", "B.Tech", 3, "Mr. R. Anil Kumar", [
        ("24A91A0501", "Aarav Kumar", "9000000101", "Suresh Kumar", "9848000101"),
        ("24A91A0502", "Meghana Reddy", "9000000102", "Ramana Reddy", "9848000102"),
        ("24A91A0503", "Sai Charan", "9000000103", "Venkata Rao", "9848000103"),
    ]),
    ("B.Tech ECE", "ECE", "B.Tech", 3, "Mr. T. Ravi Teja", [
        ("24A91A0401", "Divya Sree", "9000000201", "Srinivas", "9848000201"),
        ("24A91A0402", "Harsha Vardhan", "9000000202", "Nageswara Rao", "9848000202"),
    ]),
    ("MBA", "MBA", "MBA", 1, "Mrs. G. Swathi", [
        ("26MBA001", "Kavya Priya", "9000000301", "Prasad", "9848000301"),
    ]),
]
# Semester-end marks out of 100 per student, by subject order within the batch.
MARKS = {"24A91A0501": [92, 81, 74, 95], "24A91A0502": [85, 88, 90, 92], "24A91A0503": [58, 45, 38, 70]}


async def _create_college() -> str:
    college_id = str(uuid.uuid4())
    await execute(
        """
        INSERT INTO schools (id, name, code, subdomain, template, enabled_modules, monthly_fee, billing_status, status, payment_gateways)
        VALUES (%s, %s, %s, %s, 'classic', %s, 1500, 'active', 'active', %s)
        """,
        (college_id, NAME, CODE, CODE.lower(), json.dumps(OPTIONAL_MODULES), json.dumps(["cashfree", "razorpay", "phonepe", "demo"])),
    )
    await execute(
        "INSERT INTO users (id, school_id, email, password_hash, role, full_name, status) VALUES (%s, %s, %s, %s, 'admin', %s, 'active')",
        (str(uuid.uuid4()), college_id, ADMIN[0], hash_password(ADMIN[1]), "College Admin"),
    )
    if await fetch_one("SELECT id FROM users WHERE role = 'super_admin' LIMIT 1") is None:
        await execute(
            "INSERT INTO users (id, school_id, email, password_hash, role, full_name, status) VALUES (%s, NULL, %s, %s, 'super_admin', %s, 'active')",
            (str(uuid.uuid4()), SUPER_ADMIN[0], hash_password(SUPER_ADMIN[1]), "Platform Owner"),
        )
    return college_id


async def _seed(api: AsyncClient) -> list[tuple[str, str, str]]:
    logins = []

    async def call(method, path, body=None, expect=(200, 201, 204)):
        response = await api.request(method, f"/api/v1{path}", json=body, headers=headers)
        if response.status_code not in expect:
            raise RuntimeError(f"{method} {path} -> {response.status_code}: {response.text}")
        return response.json() if response.content else None

    token = (await api.post("/api/v1/auth/login", json={"email": ADMIN[0], "password": ADMIN[1]})).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    departments, faculty = {}, {}
    for name, code, hod in DEPARTMENTS:
        departments[code] = await call("POST", "/departments", {"name": name, "code": code})
        email = f"hod.{code.lower()}@anvcollege.in"
        faculty[hod] = await call("POST", "/teachers", {"email": email, "full_name": hod, "password": FACULTY_PASSWORD,
                                                       "department_id": departments[code]["id"], "designation": "Professor & HOD"})
        await call("PUT", f"/departments/{departments[code]['id']}", {"name": name, "code": code, "hod_teacher_id": faculty[hod]["id"]})
        logins.append(("HOD " + code, email, FACULTY_PASSWORD))
    for index, (name, dept, designation, _) in enumerate(FACULTY, start=1):
        email = f"faculty{index}@anvcollege.in"
        faculty[name] = await call("POST", "/teachers", {"email": email, "full_name": name, "password": FACULTY_PASSWORD,
                                                        "department_id": departments[dept]["id"], "designation": designation})
        logins.append((f"Faculty ({dept})", email, FACULTY_PASSWORD))

    subjects = {}
    for name, code, credits, kind, dept, semester in SUBJECTS:
        subjects[name] = await call("POST", "/subjects", {"name": name, "code": code, "credits": credits, "subject_type": kind,
                                                         "department_id": departments[dept]["id"], "semester": semester})
    teaches = {subject: name for name, _, _, taught in FACULTY for subject in taught}

    batch_ids, student_ids = [], {}
    for batch_name, dept, program, semester, mentor, students in BATCHES:
        batch = await call("POST", "/classes", {"name": batch_name, "section": "A", "academic_year": YEAR, "class_teacher_id": faculty[mentor]["id"],
                                                "department_id": departments[dept]["id"], "program": program, "semester": semester, "regulation": "R23"})
        batch_ids.append(batch["id"])
        for name, _, _, _, subject_dept, subject_sem in SUBJECTS:
            if subject_dept == dept and subject_sem == semester:
                await call("PUT", f"/classes/{batch['id']}/subjects/{subjects[name]['id']}", {"teacher_id": faculty[teaches[name]]["id"]})
        for roll, name, phone, father, father_phone in students:
            student = await call("POST", "/students", {"admission_number": roll, "full_name": name, "class_id": batch["id"],
                                                        "email": f"{roll.lower()}@anvcollege.in", "phone": phone, "quota": "Convener",
                                                        "father": {"full_name": father, "phone": father_phone}, "primary_contact": "father"})
            student_ids[roll] = student["id"]
            credentials = await call("POST", f"/students/{student['id']}/login", {"password": "Student@123"})
            logins.append((f"Student {name}", f"college code {credentials['school_code']} + roll {roll}", "Student@123"))
            parent = await call("POST", f"/students/{student['id']}/parent-login", {})
            if parent["password"]:
                # A known demo password instead of the generated one (still changed at first sign-in).
                await execute("UPDATE users SET password_hash = %s WHERE login_id = %s", (hash_password(PARENT_PASSWORD), f"parent:91{parent['phone']}"))
                logins.append((f"Parent of {name}", f"mobile {parent['phone']}", PARENT_PASSWORD))

    # Semester-end exam for the CSE batch, published so students see SGPA / CGPA.
    exam = await call("POST", "/exams", {"name": "Semester 3 End Examinations", "exam_type": "semester", "term_label": "Sem 3", "academic_year": YEAR,
                                         "class_ids": [batch_ids[0]], "max_marks": "100", "pass_marks": "40"})
    papers = sorted(exam["papers"], key=lambda p: [s[0] for s in SUBJECTS].index(p["subject_name"]))
    for index, paper in enumerate(papers):
        entries = [{"student_id": student_ids[roll], "marks": str(marks[index])} for roll, marks in MARKS.items()]
        await call("PUT", f"/exam-papers/{paper['id']}/marks", {"entries": entries})
    await call("POST", f"/exams/{exam['id']}/publish")

    await call("POST", "/fees/items", {"name": "Tuition fee 2026-27", "category": "tuition", "academic_year": YEAR, "amount": "45000",
                                       "due_date": "2026-10-31", "class_ids": batch_ids})
    await call("POST", "/fees/items", {"name": "Semester exam fee", "category": "exam", "academic_year": YEAR, "amount": "1200",
                                       "due_date": "2026-10-15", "class_ids": batch_ids})
    await call("POST", "/notices", {"title": "Campus placement drive", "body": "12 companies visit campus this month. Final-year students register with the T&P cell.",
                                    "for_staff": True, "for_students": True, "for_parents": True, "is_pinned": True})
    await _seed_campus(call, student_ids, departments)
    await seed_website(call)
    return logins


async def seed_website(call) -> None:
    """The public website: about, contact, college details, and the University template."""
    await call("PUT", "/school-site/about-contact", {
        "about": "ANV College of Engineering, Kavali is an autonomous institution offering engineering, management and computer "
                 "applications programs on a 40-acre green campus.\nOur students learn by doing: in modern laboratories, on industry "
                 "projects and through internships from their first year.",
        "contact": {"address": "NH-16, Musunuru, Kavali, SPSR Nellore District, Andhra Pradesh 524201", "phone": "+91 86262 40000",
                    "email": "info@anvcollege.in", "map_url": ""},
    })
    await call("PUT", "/school-site/college-info", {
        "established": "1998",
        "accreditation": "NAAC A+ | AICTE approved | Affiliated to JNTUA",
        "highlights": [{"value": "27+", "label": "Years of excellence"}, {"value": "4,200+", "label": "Students"},
                       {"value": "92%", "label": "Placement record"}, {"value": "180+", "label": "Faculty members"}],
        "programs": [
            {"name": "B.Tech Computer Science & Engineering", "level": "UG", "duration": "4 years", "seats": "240",
             "description": "AI, data science and full-stack development with industry projects."},
            {"name": "B.Tech Electronics & Communication", "level": "UG", "duration": "4 years", "seats": "120",
             "description": "VLSI, embedded systems and IoT laboratories."},
            {"name": "MBA", "level": "PG", "duration": "2 years", "seats": "120", "description": "Finance, marketing, HR and business analytics."},
        ],
        "principal_name": "Dr. K. Srinivasa Rao",
        "principal_title": "Principal",
        "principal_message": "Welcome to ANV College of Engineering. For over two decades we have prepared young people for careers "
                             "and lives of purpose.\nI invite you to visit our campus and see our students at work.",
    })
    await call("PUT", "/school-site/template", {"template": "university"})


async def _seed_campus(call, student_ids: dict, departments: dict) -> None:
    """Library books and loans, a hostel, a bus route and a placement drive."""
    books = [("Data Structures Using C", "Reema Thareja", "Computer Science", 5), ("Database System Concepts", "Silberschatz", "Computer Science", 4),
             ("Signals and Systems", "Oppenheim", "Electronics", 3), ("Principles of Management", "Koontz", "Management", 3)]
    book_ids = []
    for title, author, category, copies in books:
        book_ids.append((await call("POST", "/library/books", {"title": title, "author": author, "category": category, "total_copies": copies}))["id"])
    await call("POST", "/library/loans", {"book_id": book_ids[0], "student_id": student_ids["24A91A0501"]})
    await call("POST", "/library/loans", {"book_id": book_ids[2], "student_id": student_ids["24A91A0401"]})

    await call("POST", "/hostels", {"name": "Boys Hostel", "gender": "boys", "warden_name": "Mr. K. Ramesh", "warden_phone": "9848011111"})
    await call("POST", "/hostels", {"name": "Girls Hostel", "gender": "girls", "warden_name": "Mrs. V. Sujatha", "warden_phone": "9848022222"})
    hostels = {h["name"]: h for h in await call("GET", "/hostels")}
    for name in hostels:
        for number in ("101", "102", "201"):
            await call("POST", f"/hostels/{hostels[name]['id']}/rooms", {"room_number": number, "capacity": 3})
    hostels = {h["name"]: h for h in await call("GET", "/hostels")}
    await call("POST", "/hostels/allocations", {"student_id": student_ids["24A91A0501"], "room_id": hostels["Boys Hostel"]["rooms"][0]["id"]})
    await call("POST", "/hostels/allocations", {"student_id": student_ids["24A91A0503"], "room_id": hostels["Boys Hostel"]["rooms"][0]["id"]})
    await call("POST", "/hostels/allocations", {"student_id": student_ids["24A91A0502"], "room_id": hostels["Girls Hostel"]["rooms"][0]["id"]})

    await call("POST", "/transport/routes", {"name": "Route 1 - Kavali Town", "vehicle_number": "AP39 TA 1234", "driver_name": "Subba Rao",
                                             "driver_phone": "9848033333", "seats": 45, "annual_fare": 18000,
                                             "stops": [{"name": "RTC Bus Stand", "pickup_time": "07:40"}, {"name": "Trunk Road", "pickup_time": "07:50"},
                                                       {"name": "Musunuru", "pickup_time": "08:05"}]})
    route = (await call("GET", "/transport/routes"))[0]
    for roll in ("24A91A0401", "24A91A0402"):
        await call("POST", "/transport/assignments", {"student_id": student_ids[roll], "route_id": route["id"], "stop_id": route["stops"][1]["id"]})

    for name, industry in (("Infosys", "IT services"), ("TCS", "IT services"), ("Amara Raja", "Core / manufacturing")):
        await call("POST", "/placements/companies", {"name": name, "industry": industry})
    companies = {c["name"]: c for c in await call("GET", "/placements/companies")}
    await call("POST", "/placements/drives", {"company_id": companies["Infosys"]["id"], "role_title": "Systems Engineer", "package_lpa": 3.6,
                                              "location": "Hyderabad", "min_cgpa": 7.0, "eligible_department_ids": [departments["CSE"]["id"], departments["ECE"]["id"]],
                                              "description": "Online test, technical interview and HR round. Bring 2 copies of your resume."})
    await call("POST", "/placements/drives", {"company_id": companies["Amara Raja"]["id"], "role_title": "Graduate Engineer Trainee", "package_lpa": 4.2,
                                              "location": "Tirupati", "eligible_department_ids": [departments["ECE"]["id"]]})


async def main() -> None:
    await connect_to_mysql()
    try:
        if await fetch_one("SELECT id FROM schools WHERE code = %s", (CODE,)):
            print(f"{NAME} ({CODE}) already exists; nothing to do.")
            return
        await _create_college()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://seed") as api:
            logins = await _seed(api)
    finally:
        await close_mysql_connection()

    print(f"\nCreated {NAME} (college code {CODE}).\n")
    print(f"  {'Super admin':34} {SUPER_ADMIN[0]:42} {SUPER_ADMIN[1]}   (sign in at /superadmin)")
    print(f"  {'College admin':34} {ADMIN[0]:42} {ADMIN[1]}")
    for who, login, password in logins:
        print(f"  {who:34} {login:42} {password}")


if __name__ == "__main__":
    asyncio.run(main())
