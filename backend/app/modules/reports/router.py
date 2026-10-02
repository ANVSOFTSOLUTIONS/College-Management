from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, require_roles
from app.core.modules import require_module
from app.modules.reports import naac, performance, service
from app.modules.reports.naac import NaacReport
from app.modules.reports.performance import ExamPerformance
from app.modules.reports.service import StaffAttendanceReport, StudentAttendanceReport

router = APIRouter(prefix="/reports", tags=["reports"])

_staff = require_roles("admin", "teacher")
_admin = require_roles("admin")

_reports_on = [Depends(require_module("reports"))]
_REPORT_RESPONSES = {200: {"content": {service.XLSX: {}}, "description": "JSON, or an Excel file with format=xlsx."}}


@router.get("/student-attendance", dependencies=_reports_on, response_model=StudentAttendanceReport, responses=_REPORT_RESPONSES)
async def student_attendance(
    start: date,
    end: date,
    class_id: str | None = None,
    format: Literal["json", "xlsx"] = "json",
    current_user: CurrentUser = Depends(_staff),
):
    """Per student: days present, late and absent, and attendance %. Class teachers see their own class."""
    report = await service.student_attendance(current_user, class_id=class_id, start=start, end=end)
    return service.student_attendance_xlsx(report) if format == "xlsx" else report


@router.get("/staff-attendance", dependencies=_reports_on, response_model=StaffAttendanceReport, responses=_REPORT_RESPONSES)
async def staff_attendance(month: date, format: Literal["json", "xlsx"] = "json", current_user: CurrentUser = Depends(_admin)):
    """Per teacher for the month containing `month`: days present, late, on leave and absent."""
    report = await service.staff_attendance(current_user, month)
    return service.staff_attendance_xlsx(report) if format == "xlsx" else report


@router.get("/fee-dues.xlsx", dependencies=_reports_on, responses=_REPORT_RESPONSES)
async def fee_dues(class_id: str | None = None, only_with_dues: bool = True, current_user: CurrentUser = Depends(_admin)):
    """The fee report as an Excel file (the on-screen version is /fees/report)."""
    return await service.fee_dues_xlsx(current_user, class_id, only_with_dues)


@router.get("/exam-performance/{exam_id}", response_model=ExamPerformance, dependencies=[Depends(require_module("performance"))])
async def exam_performance(exam_id: str, current_user: CurrentUser = Depends(_staff)) -> ExamPerformance:
    """Class and subject averages, grade spread, toppers and students who failed or missed a paper."""
    return await performance.exam_performance(current_user, exam_id)


@router.get("/naac", dependencies=_reports_on, response_model=NaacReport)
async def naac_report(current_user: CurrentUser = Depends(_admin)) -> NaacReport:
    """Students, faculty, results, attendance, placements, feedback and grievances, tagged with NAAC criteria."""
    return await naac.report(current_user)


@router.get("/naac.xlsx", dependencies=_reports_on)
async def naac_xlsx(current_user: CurrentUser = Depends(_admin)):
    """The NAAC / AISHE data as an Excel workbook, one sheet per table."""
    return naac.to_xlsx(await naac.report(current_user))
