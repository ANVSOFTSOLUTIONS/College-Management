import os

os.environ.setdefault("MYSQL_DATABASE", "school_management_test")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("DATA_ENCRYPTION_KEY", "q3r0Tz5c8Qm1bGf0yY2x3Jw4Vv5Uu6Tt7Ss8Rr9Qq0o=")  # test-only Fernet key

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core import rate_limit
from app.db.database import close_mysql_connection, connect_to_mysql, db as mysql_db
from app.main import app

# Deletion order matters: children before parents (classes.teacher_id is
# ON DELETE RESTRICT, so classes must go before teachers, etc.)
_TABLES_CHILD_TO_PARENT = [
    "audit_log",
    "subject_attendance",
    "grievance_replies",
    "grievances",
    "semester_promotions",
    "feedback_responses",
    "feedback_rounds",
    "elective_choices",
    "elective_options",
    "elective_groups",
    "placement_applications",
    "placement_drives",
    "placement_companies",
    "transport_assignments",
    "transport_stops",
    "transport_routes",
    "hostel_allocations",
    "hostel_rooms",
    "hostels",
    "library_loans",
    "library_books",
    "library_settings",
    "push_subscriptions",
    "platform_payments",
    "admission_documents",
    "admission_applications",
    "admission_counters",
    "salary_slips",
    "teacher_salaries",
    "certificate_counters",
    "student_certificates",
    "school_holidays",
    "timetable_entries",
    "school_periods",
    "homework",
    "notice_classes",
    "notices",
    "promotion_runs",
    "demo_requests",
    "platform_settings",
    "notifications",
    "leave_requests",
    "staff_punches",
    "school_settings",
    "exam_marks",
    "exam_subjects",
    "exams",
    "school_payment_settings",
    "parent_students",
    "fee_payments",
    "fee_receipt_counters",
    "student_fees",
    "fee_items",
    "parent_alerts",
    "student_remarks",
    "attendance",
    "staff_attendance",
    "school_site_notices",
    "school_site_activities",
    "school_site_gallery",
    "school_site_banners",
    "school_sites",
    "student_documents",
    "student_guardians",
    "students",
    "class_subjects",
    "subjects",
    "classes",
    "departments",
    "teachers",
    "users",
    "schools",
]


@pytest_asyncio.fixture(autouse=True)
def _isolate_uploads(tmp_path, monkeypatch):
    from app.modules.school_site import storage

    monkeypatch.setattr(storage, "UPLOAD_ROOT", tmp_path / "uploads")

    from app.modules.students import files

    monkeypatch.setattr(files, "PRIVATE_ROOT", tmp_path / "private_uploads")


@pytest_asyncio.fixture
async def db():
    await connect_to_mysql()
    yield mysql_db
    async with mysql_db.pool.acquire() as conn:
        async with conn.cursor() as cur:
            for table in _TABLES_CHILD_TO_PARENT:
                await cur.execute(f"DELETE FROM {table}")
    await close_mysql_connection()


@pytest_asyncio.fixture
async def client(db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
def _fresh_rate_limits():
    """Every test starts with no recorded attempts (all tests share one client address)."""
    rate_limit._attempts.clear()
    yield
