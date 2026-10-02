from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.modules import require_module
from app.db.database import close_mysql_connection, connect_to_mysql
from app.modules.academics.router import classes_admin_router, departments_router, subjects_router, teachers_router
from app.modules.admissions.router import public_router as admissions_public_router, router as admissions_router
from app.modules.alerts.router import router as parent_alerts_router
from app.modules.attendance.router import classes_router, router as attendance_router
from app.modules.audit.router import router as audit_router
from app.modules.backups.router import internal_router as backups_internal_router, router as backups_router
from app.modules.board.router import homework_router, notices_router
from app.modules.certificates.router import router as certificates_router
from app.modules.dashboard.router import router as dashboard_router
from app.modules.exams.router import papers_router as exam_papers_router, parent_results_router, router as exams_router
from app.modules.fees.router import router as fees_router
from app.modules.hod.router import router as hod_router
from app.modules.hostel.router import portal_router as hostel_portal_router, router as hostel_router
from app.modules.leave.router import router as leave_router
from app.modules.library.router import portal_router as library_portal_router, router as library_router
from app.modules.placements.router import router as placements_router
from app.modules.transport.router import portal_router as transport_portal_router, router as transport_router
from app.modules.marketing.router import admin_router as marketing_admin_router, public_router as marketing_public_router
from app.modules.notifications.router import router as notifications_router
from app.modules.promotion.router import router as promotion_router
from app.modules.push.router import router as push_router
from app.modules.reports.router import router as reports_router
from app.modules.payroll.router import router as payroll_router
from app.modules.parents.router import (
    portal_router as parent_portal_router,
    settings_router as payment_settings_router,
    staff_router as parent_logins_router,
    webhook_router as payment_webhook_router,
)
from app.modules.school_site.router import public_router as school_site_public_router, router as school_site_router
from app.modules.school_site.storage import UPLOAD_ROOT
from app.modules.staff_attendance.router import punch_router, router as staff_attendance_router, settings_router as school_settings_router
from app.modules.students.router import router as students_router
from app.modules.electives.router import portal_router as electives_portal_router, router as electives_router
from app.modules.feedback.router import portal_router as feedback_portal_router, router as feedback_router
from app.modules.subject_attendance.router import portal_router as subject_attendance_portal_router, router as subject_attendance_router
from app.modules.teaching.router import remarks_router, teaching_router
from app.modules.timetable.router import calendar_router, timetable_router
from app.modules.super_admin.router import platform_router as super_admin_platform_router, router as super_admin_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    await connect_to_mysql()
    yield
    await close_mysql_connection()


settings = get_settings()
app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_ROOT), name="uploads")

app.include_router(health_router, prefix=settings.api_prefix)
app.include_router(auth_router, prefix=settings.api_prefix)
app.include_router(classes_router, prefix=settings.api_prefix)
app.include_router(classes_admin_router, prefix=settings.api_prefix)
app.include_router(teachers_router, prefix=settings.api_prefix)
app.include_router(subjects_router, prefix=settings.api_prefix)
app.include_router(departments_router, prefix=settings.api_prefix)
app.include_router(hod_router, prefix=settings.api_prefix)
app.include_router(subject_attendance_router, prefix=settings.api_prefix)
app.include_router(subject_attendance_portal_router, prefix=settings.api_prefix)
app.include_router(electives_router, prefix=settings.api_prefix)
app.include_router(electives_portal_router, prefix=settings.api_prefix)
app.include_router(feedback_router, prefix=settings.api_prefix)
app.include_router(feedback_portal_router, prefix=settings.api_prefix)
app.include_router(parent_logins_router, prefix=settings.api_prefix)
app.include_router(students_router, prefix=settings.api_prefix)
app.include_router(teaching_router, prefix=settings.api_prefix)
app.include_router(remarks_router, prefix=settings.api_prefix)
app.include_router(parent_alerts_router, prefix=settings.api_prefix)
app.include_router(payment_settings_router, prefix=settings.api_prefix, dependencies=[Depends(require_module("fees"))])
app.include_router(fees_router, prefix=settings.api_prefix, dependencies=[Depends(require_module("fees"))])
app.include_router(parent_portal_router, prefix=settings.api_prefix)
app.include_router(payment_webhook_router, prefix=settings.api_prefix)
app.include_router(exams_router, prefix=settings.api_prefix, dependencies=[Depends(require_module("exams"))])
app.include_router(exam_papers_router, prefix=settings.api_prefix, dependencies=[Depends(require_module("exams"))])
app.include_router(parent_results_router, prefix=settings.api_prefix, dependencies=[Depends(require_module("exams"))])
app.include_router(attendance_router, prefix=settings.api_prefix)
app.include_router(staff_attendance_router, prefix=settings.api_prefix)
app.include_router(punch_router, prefix=settings.api_prefix)
app.include_router(school_settings_router, prefix=settings.api_prefix)
app.include_router(leave_router, prefix=settings.api_prefix)
app.include_router(promotion_router, prefix=settings.api_prefix)
app.include_router(dashboard_router, prefix=settings.api_prefix, dependencies=[Depends(require_module("dashboard"))])
app.include_router(notices_router, prefix=settings.api_prefix, dependencies=[Depends(require_module("notices"))])
app.include_router(homework_router, prefix=settings.api_prefix, dependencies=[Depends(require_module("homework"))])
app.include_router(timetable_router, prefix=settings.api_prefix, dependencies=[Depends(require_module("timetable"))])
app.include_router(calendar_router, prefix=settings.api_prefix, dependencies=[Depends(require_module("timetable"))])
app.include_router(reports_router, prefix=settings.api_prefix)
app.include_router(certificates_router, prefix=settings.api_prefix, dependencies=[Depends(require_module("certificates"))])
app.include_router(payroll_router, prefix=settings.api_prefix, dependencies=[Depends(require_module("payroll"))])
app.include_router(admissions_router, prefix=settings.api_prefix, dependencies=[Depends(require_module("admissions"))])
app.include_router(admissions_public_router, prefix=settings.api_prefix)
app.include_router(notifications_router, prefix=settings.api_prefix)
app.include_router(push_router, prefix=settings.api_prefix)
app.include_router(school_site_router, prefix=settings.api_prefix, dependencies=[Depends(require_module("school-site"))])
app.include_router(school_site_public_router, prefix=settings.api_prefix)
app.include_router(super_admin_router, prefix=settings.api_prefix)
for _module, _routers in (
    ("library", (library_router, library_portal_router)),
    ("hostel", (hostel_router, hostel_portal_router)),
    ("transport", (transport_router, transport_portal_router)),
    ("placements", (placements_router,)),
):
    for _router in _routers:
        app.include_router(_router, prefix=settings.api_prefix, dependencies=[Depends(require_module(_module))])
app.include_router(super_admin_platform_router, prefix=settings.api_prefix)
app.include_router(backups_router, prefix=settings.api_prefix)
app.include_router(backups_internal_router, prefix=settings.api_prefix)
app.include_router(audit_router, prefix=settings.api_prefix)
app.include_router(marketing_admin_router, prefix=settings.api_prefix)
app.include_router(marketing_public_router, prefix=settings.api_prefix)
