"""Per-school feature modules, switched on and off by the super admin.

Core features (students, teachers, classes, attendance, leave, punch in/out)
are always on. The optional modules below are enforced here on the API and
hidden in the app's navigation when a school doesn't have them.
"""

import json

from fastapi import Depends, status

from app.api.deps import CurrentUser, get_current_user
from app.core.errors import AppError
from app.db.helpers import fetch_one

OPTIONAL_MODULES = [
    "dashboard",
    "admissions",
    "exams",
    "homework",
    "notices",
    "timetable",  # timetable and holiday calendar
    "fees",
    "reports",
    "performance",
    "certificates",  # ID cards, TC and bonafide
    "payroll",  # staff salaries and payslips
    "school-site",
    "library",  # books, loans and fines
    "hostel",  # hostels, rooms and allocations
    "transport",  # bus routes, stops and riders
    "placements",  # companies, drives and applications
]
# Ids saved on older schools; still accepted, but they no longer switch anything off.
LEGACY_MODULES = {"students", "attendance", "staff-biometric"}


async def school_modules(school_id: str) -> set[str]:
    row = await fetch_one("SELECT enabled_modules FROM schools WHERE id = %s", (school_id,))
    if row is None:
        return set()
    modules = row["enabled_modules"]
    return set(json.loads(modules) if isinstance(modules, str) else modules or [])


def require_module(module: str):
    """Route dependency: 403 when the signed-in user's school has the module switched off.

    Parents have no school of their own and the super admin has none, so the check is skipped for them.
    """

    async def _check(current_user: CurrentUser = Depends(get_current_user)) -> None:
        if current_user.school_id and module not in await school_modules(current_user.school_id):
            raise AppError(status.HTTP_403_FORBIDDEN, "module_disabled", "This feature isn't enabled for your school.")

    return _check
