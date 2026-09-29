import json
import uuid

from app.core.modules import OPTIONAL_MODULES
from app.core.security import hash_password
from app.db.helpers import execute


async def create_school(*, code="TESTSCH", name="Test School", subdomain=None, modules=None):
    school_id = str(uuid.uuid4())
    await execute(
        """
        INSERT INTO schools (id, name, code, subdomain, template, enabled_modules, monthly_fee, billing_status, status)
        VALUES (%s, %s, %s, %s, 'classic', %s, 600, 'active', 'active')
        """,
        (school_id, name, code, subdomain or code.lower(), json.dumps(OPTIONAL_MODULES if modules is None else modules)),
    )
    return school_id


async def create_user(*, school_id, email, password, role, full_name="Test User"):
    user_id = str(uuid.uuid4())
    await execute(
        """
        INSERT INTO users (id, school_id, email, password_hash, role, full_name, status)
        VALUES (%s, %s, %s, %s, %s, %s, 'active')
        """,
        (user_id, school_id, email, hash_password(password), role, full_name),
    )
    return user_id


async def create_teacher(*, school_id, user_id, department="General"):
    teacher_id = str(uuid.uuid4())
    await execute(
        "INSERT INTO teachers (id, school_id, user_id, department) VALUES (%s, %s, %s, %s)",
        (teacher_id, school_id, user_id, department),
    )
    return teacher_id


async def create_class(*, school_id, teacher_id, name="Grade 5", section="A", academic_year="2026"):
    class_id = str(uuid.uuid4())
    await execute(
        """
        INSERT INTO classes (id, school_id, teacher_id, name, section, academic_year)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (class_id, school_id, teacher_id, name, section, academic_year),
    )
    return class_id


async def create_student(*, school_id, class_id, admission_number, full_name):
    student_id = str(uuid.uuid4())
    await execute(
        """
        INSERT INTO students (id, school_id, class_id, admission_number, full_name)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (student_id, school_id, class_id, admission_number, full_name),
    )
    return student_id


async def login(client, email, password):
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return response


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
