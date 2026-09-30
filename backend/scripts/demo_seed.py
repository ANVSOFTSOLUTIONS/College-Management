"""Seed one realistic demo school for showing the product.

Creates "ANV Demo School" with 6 classes, a teacher per class, 20 students
per class, a subject teacher for each of 6 subjects in every class, the last
30 school days of student and teacher attendance, and public-site content
(about, contact, activities, notices). Needs database/mysql/002-004
applied first (the backend applies them on start). Every demo login shares one password,
typed at the prompt — nothing is hard-coded. Safe to run twice: it stops if
the demo school already exists. Run from backend/:

    python -m scripts.demo_seed
"""

import asyncio
import getpass
import json
import random
import uuid
from datetime import date, timedelta

import aiomysql

from app.core.config import get_settings
from app.core.security import hash_password
from app.core.modules import OPTIONAL_MODULES

DEMO_SCHOOL_CODE = "ANVDEMO"
ADMIN_EMAIL = "demo-admin@example.com"
ACADEMIC_YEAR = "2026"
STUDENTS_PER_CLASS = 20
ATTENDANCE_SCHOOL_DAYS = 30

# (name, subject taught / department, class they are class teacher of, qualification)
TEACHERS = [
    ("Lakshmi Narayana", "Mathematics", "Grade 1", "M.Sc Mathematics, B.Ed"),
    ("Priya Sharma", "English", "Grade 2", "M.A English, B.Ed"),
    ("Ravi Kumar", "Science", "Grade 3", "M.Sc Physics, B.Ed"),
    ("Anitha Reddy", "Social Studies", "Grade 4", "M.A History, B.Ed"),
    ("Suresh Babu", "Telugu", "Grade 5", "M.A Telugu, B.Ed"),
    ("Meena Iyer", "Computer Science", "Grade 6", "MCA"),
]
SUBJECT_CODES = {
    "Mathematics": "MAT", "English": "ENG", "Science": "SCI",
    "Social Studies": "SOC", "Telugu": "TEL", "Computer Science": "CSC",
}
FIRST_NAMES = [
    "Aarav", "Vihaan", "Aditya", "Sai", "Arjun", "Krishna", "Rohan", "Karthik", "Varun", "Nikhil",
    "Ananya", "Diya", "Sneha", "Harini", "Keerthi", "Pooja", "Divya", "Meghana", "Sahithi", "Lasya",
]
LAST_NAMES = [
    "Reddy", "Rao", "Sharma", "Naidu", "Varma", "Chowdary", "Goud", "Iyer", "Pillai", "Gupta",
]
FATHER_FIRST_NAMES = ["Srinivas", "Ramesh", "Venkat", "Prasad", "Mahesh"]
MOTHER_FIRST_NAMES = ["Lakshmi", "Padma", "Sunitha", "Kavitha", "Radha"]
OCCUPATIONS = ["Engineer", "Teacher", "Business", "Doctor", "Farmer", "Government employee"]
AREAS = ["Madhapur", "Kukatpally", "Ameerpet", "Gachibowli", "Dilsukhnagar", "Miyapur"]


def _school_days(today: date, count: int) -> list[date]:
    days, current = [], today
    while len(days) < count:
        if current.weekday() < 5:
            days.append(current)
        current -= timedelta(days=1)
    return sorted(days)


def _attendance_status(rng: random.Random, reliability: float, other: str = "absent") -> str:
    roll = rng.random()
    if roll < reliability:
        return "present"
    if roll < reliability + (1 - reliability) / 3:
        return "late"
    return other


async def seed_demo_school(conn, password: str, today: date) -> bool:
    """Create the demo school; returns False if it already exists."""
    rng = random.Random(2026)
    password_hash = hash_password(password)

    async with conn.cursor() as cur:
        await cur.execute("SELECT id FROM schools WHERE code = %s", (DEMO_SCHOOL_CODE,))
        if await cur.fetchone() is not None:
            return False

        school_id = str(uuid.uuid4())
        await cur.execute(
            """
            INSERT INTO schools (id, name, code, subdomain, template, enabled_modules, monthly_fee, billing_status, status)
            VALUES (%s, 'ANV Demo School', %s, 'demo', 'modern', %s, 600, 'active', 'active')
            """,
            (school_id, DEMO_SCHOOL_CODE, json.dumps(OPTIONAL_MODULES)),
        )
        admin_user_id = str(uuid.uuid4())
        await cur.execute(
            """
            INSERT INTO users (id, school_id, email, password_hash, role, full_name, status)
            VALUES (%s, %s, %s, %s, 'admin', 'Demo School Admin', 'active')
            """,
            (admin_user_id, school_id, ADMIN_EMAIL, password_hash),
        )

        subject_ids = {name: str(uuid.uuid4()) for name in SUBJECT_CODES}
        await cur.executemany(
            "INSERT INTO subjects (id, school_id, name, code) VALUES (%s, %s, %s, %s)",
            [(subject_id, school_id, name, SUBJECT_CODES[name]) for name, subject_id in subject_ids.items()],
        )

        school_days = _school_days(today, ATTENDANCE_SCHOOL_DAYS)
        staff_attendance = []
        teacher_by_subject, class_ids = {}, []
        admission_number = 1001
        for index, (teacher_name, department, class_name, qualification) in enumerate(TEACHERS, start=1):
            teacher_user_id, teacher_id, class_id = (str(uuid.uuid4()) for _ in range(3))
            await cur.execute(
                """
                INSERT INTO users (id, school_id, email, password_hash, role, full_name, status)
                VALUES (%s, %s, %s, %s, 'teacher', %s, 'active')
                """,
                (teacher_user_id, school_id, f"demo-teacher{index}@example.com", password_hash, teacher_name),
            )
            await cur.execute(
                """
                INSERT INTO teachers (id, school_id, user_id, department, employee_code, phone, qualification, joined_on)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    teacher_id,
                    school_id,
                    teacher_user_id,
                    department,
                    f"EMP-{100 + index}",
                    f"90000000{index:02d}",
                    qualification,
                    date(2020 + index % 5, 6, 1).isoformat(),
                ),
            )
            teacher_by_subject[department] = teacher_id
            class_ids.append(class_id)
            await cur.execute(
                """
                INSERT INTO classes (id, school_id, teacher_id, name, section, academic_year)
                VALUES (%s, %s, %s, %s, 'A', %s)
                """,
                (class_id, school_id, teacher_id, class_name, ACADEMIC_YEAR),
            )
            teacher_reliability = rng.uniform(0.88, 0.97)
            staff_attendance.extend(
                (
                    str(uuid.uuid4()),
                    school_id,
                    teacher_id,
                    day.isoformat(),
                    _attendance_status(rng, teacher_reliability, other="leave"),
                    admin_user_id,
                )
                for day in school_days
            )

            students, guardians, attendance = [], [], []
            birth_year = today.year - 5 - index  # Grade 1 students are about 6
            for _ in range(STUDENTS_PER_CLASS):
                student_id = str(uuid.uuid4())
                last_name = rng.choice(LAST_NAMES)
                first_index = rng.randrange(len(FIRST_NAMES))
                father = f"{rng.choice(FATHER_FIRST_NAMES)} {last_name}"
                mother = f"{rng.choice(MOTHER_FIRST_NAMES)} {last_name}"
                phone_base = 9800000000 + admission_number * 10
                students.append(
                    (
                        student_id,
                        school_id,
                        class_id,
                        f"DEMO-{admission_number}",
                        f"{FIRST_NAMES[first_index]} {last_name}",
                        date(birth_year, rng.randint(1, 12), rng.randint(1, 28)).isoformat(),
                        "male" if first_index < len(FIRST_NAMES) // 2 else "female",
                        rng.choice(["A+", "B+", "O+", "AB+", "O-"]),
                        date(today.year - index + 1, 6, 1).isoformat(),
                        f"{rng.randint(1, 99)}-{rng.randint(1, 500)}, {rng.choice(AREAS)}, Hyderabad",
                        father,
                        "father",
                    )
                )
                for relation, name, phone_offset in (("father", father, 1), ("mother", mother, 2)):
                    guardians.append(
                        (
                            str(uuid.uuid4()),
                            school_id,
                            student_id,
                            relation,
                            name,
                            str(phone_base + phone_offset),
                            rng.choice(OCCUPATIONS),
                        )
                    )
                admission_number += 1
                reliability = rng.uniform(0.75, 0.98)
                for day in school_days:
                    attendance.append(
                        (
                            str(uuid.uuid4()),
                            school_id,
                            class_id,
                            student_id,
                            day.isoformat(),
                            _attendance_status(rng, reliability),
                            teacher_user_id,
                        )
                    )
            await cur.executemany(
                """
                INSERT INTO students (id, school_id, class_id, admission_number, full_name, date_of_birth, gender,
                                      blood_group, admission_date, address, parent_name, primary_contact)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                students,
            )
            await cur.executemany(
                """
                INSERT INTO student_guardians (id, school_id, student_id, relation, full_name, phone, occupation)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                guardians,
            )
            await cur.executemany(
                """
                INSERT INTO attendance (id, school_id, class_id, student_id, attendance_date, status, marked_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                attendance,
            )

        await cur.executemany(
            "INSERT INTO class_subjects (id, school_id, class_id, subject_id, teacher_id) VALUES (%s, %s, %s, %s, %s)",
            [
                (str(uuid.uuid4()), school_id, class_id, subject_ids[subject], teacher_id)
                for class_id in class_ids
                for subject, teacher_id in teacher_by_subject.items()
            ],
        )

        await cur.executemany(
            """
            INSERT INTO staff_attendance (id, school_id, teacher_id, attendance_date, status, marked_by)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            staff_attendance,
        )

        site_id = str(uuid.uuid4())
        await cur.execute(
            """
            INSERT INTO school_sites (id, school_id, about, contact_address, contact_phone, contact_email)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                site_id,
                school_id,
                "ANV Demo School is a co-educational school offering classes from Grade 1 to Grade 6, "
                "focused on strong fundamentals, creativity, and all-round development.",
                "Plot 12, Madhapur, Hyderabad, Telangana 500081",
                "+91 90000 00000",
                "info@example.com",
            ),
        )
        await cur.executemany(
            """
            INSERT INTO school_site_activities (id, school_site_id, title, activity_date, description)
            VALUES (%s, %s, %s, %s, %s)
            """,
            [
                (str(uuid.uuid4()), site_id, "Annual Sports Day", (today - timedelta(days=20)).isoformat(),
                 "Track events, relays, and team games for all grades."),
                (str(uuid.uuid4()), site_id, "Science Exhibition", (today - timedelta(days=9)).isoformat(),
                 "Students presented working models on energy and the environment."),
                (str(uuid.uuid4()), site_id, "Independence Day Celebrations", (today - timedelta(days=42)).isoformat(),
                 "Flag hoisting, cultural programmes, and a patriotic song competition."),
            ],
        )
        await cur.executemany(
            "INSERT INTO school_site_notices (id, school_site_id, title, notice_date) VALUES (%s, %s, %s, %s)",
            [
                (str(uuid.uuid4()), site_id, "Parent-teacher meeting this Saturday at 10 AM", today.isoformat()),
                (str(uuid.uuid4()), site_id, "Unit tests begin next Monday", (today - timedelta(days=3)).isoformat()),
                (str(uuid.uuid4()), site_id, "School closed for Dussehra holidays", (today - timedelta(days=7)).isoformat()),
            ],
        )
    return True


async def main() -> None:
    password = getpass.getpass("Password for all demo logins (8-72 characters): ")
    if not 8 <= len(password) <= 72:
        raise SystemExit("Password must be 8-72 characters.")

    settings = get_settings()
    conn = await aiomysql.connect(
        host=settings.mysql_host,
        port=settings.mysql_port,
        user=settings.mysql_user,
        password=settings.mysql_password,
        db=settings.mysql_database,
        autocommit=False,
    )
    try:
        created = await seed_demo_school(conn, password, date.today())
        await conn.commit()
    except Exception:
        await conn.rollback()
        raise
    finally:
        conn.close()

    if not created:
        raise SystemExit("Demo school already exists; nothing changed.")
    print("Created ANV Demo School: 6 classes, 6 teachers, 6 subjects, 120 students, 30 days of student and teacher attendance.")
    print(f"Logins: {ADMIN_EMAIL} (admin), demo-teacher1@example.com ... demo-teacher6@example.com (teachers)")


if __name__ == "__main__":
    asyncio.run(main())
