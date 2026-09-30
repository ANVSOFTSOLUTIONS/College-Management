from datetime import date as date_type

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, require_roles
from app.db.helpers import fetch_all
from app.modules.alerts import service as alerts
from app.modules.attendance import service
from app.modules.attendance.schemas import (
    AttendanceEntry,
    AttendanceResponse,
    ClassSummary,
    MarkAttendanceRequest,
    MarkAttendanceResponse,
    RosterResponse,
    StudentSummary,
)
from app.modules.audit import service as audit
from app.modules.leave.service import students_on_leave

router = APIRouter(prefix="/classes/{class_id}", tags=["attendance"])
classes_router = APIRouter(prefix="/classes", tags=["attendance"])

_can_manage_attendance = require_roles("admin", "teacher")


@classes_router.get("", response_model=list[ClassSummary])
async def list_classes(current_user: CurrentUser = Depends(_can_manage_attendance)) -> list[ClassSummary]:
    classes = await service.list_classes_for_user(current_user)
    return [
        ClassSummary(
            id=c["id"],
            name=c["name"],
            section=c["section"],
            academic_year=c["academic_year"],
            class_teacher_id=c["teacher_id"],
            class_teacher_name=c["class_teacher_name"],
            student_count=c["student_count"],
            department_id=c["department_id"],
            department_name=c["department_name"],
            program=c["program"],
            semester=c["semester"],
            regulation=c["regulation"],
        )
        for c in classes
    ]


@router.get("/students", response_model=RosterResponse)
async def get_roster(
    class_id: str,
    current_user: CurrentUser = Depends(_can_manage_attendance),
) -> RosterResponse:
    class_doc = await service.get_class_for_school(class_id, current_user.school_id)
    await service.ensure_class_access(current_user, class_doc)
    students = await service.list_roster(class_id)

    return RosterResponse(
        class_id=class_id,
        class_name=class_doc["name"],
        section=class_doc["section"],
        students=[
            StudentSummary(id=s["id"], full_name=s["full_name"], admission_number=s["admission_number"])
            for s in students
        ],
    )


@router.get("/attendance", response_model=AttendanceResponse)
async def get_attendance(
    class_id: str,
    date: date_type,
    current_user: CurrentUser = Depends(_can_manage_attendance),
) -> AttendanceResponse:
    class_doc = await service.get_class_for_school(class_id, current_user.school_id)
    await service.ensure_class_access(current_user, class_doc)

    iso_date = date.isoformat()
    students = await service.list_roster(class_id)
    status_by_student = await service.get_attendance_map(class_id, iso_date)
    on_leave = await students_on_leave(class_id, date)

    entries = [
        AttendanceEntry(
            student_id=s["id"],
            full_name=s["full_name"],
            admission_number=s["admission_number"],
            status=status_by_student.get(s["id"]),
            on_leave=s["id"] in on_leave,
        )
        for s in students
    ]

    return AttendanceResponse(class_id=class_id, date=date, entries=entries)


@router.post("/attendance", response_model=MarkAttendanceResponse)
async def mark_attendance(
    class_id: str,
    payload: MarkAttendanceRequest,
    current_user: CurrentUser = Depends(_can_manage_attendance),
) -> MarkAttendanceResponse:
    class_doc = await service.get_class_for_school(class_id, current_user.school_id)
    await service.ensure_class_access(current_user, class_doc)

    previous = {
        r["student_id"]: r["status"]
        for r in await fetch_all("SELECT student_id, status FROM attendance WHERE class_id = %s AND attendance_date = %s", (class_id, payload.date))
    }
    marked_count = await service.mark_attendance(
        school_id=current_user.school_id,
        class_id=class_id,
        iso_date=payload.date.isoformat(),
        records=payload.records,
        marked_by_user_id=current_user.id,
    )
    # Students on approved leave are marked absent without alerting their parents.
    on_leave = await students_on_leave(class_id, payload.date)
    await alerts.alert_absences(
        [r.student_id for r in payload.records if r.status == "absent" and r.student_id not in on_leave],
        payload.date,
        current_user.id,
    )

    changed = [
        {"student_id": r.student_id, "from": previous[r.student_id], "to": r.status}
        for r in payload.records
        if r.student_id in previous and previous[r.student_id] != r.status
    ]
    if changed:
        names = {
            s["id"]: s["full_name"]
            for s in await fetch_all(
                "SELECT id, full_name FROM students WHERE id IN ({})".format(", ".join(["%s"] * len(changed))), tuple(c["student_id"] for c in changed)
            )
        }
        for c in changed:
            c["student"] = names.get(c["student_id"], "")
        listed = ", ".join(f"{c['student']} {c['from']}→{c['to']}" for c in changed[:5]) + (" …" if len(changed) > 5 else "")
        await audit.record(
            current_user, "attendance.changed",
            f"Changed attendance of {class_doc['name']} - {class_doc['section']} for {payload.date:%d %b %Y}: {listed}",
            entity_type="class", entity_id=class_id, details=changed,
        )

    return MarkAttendanceResponse(class_id=class_id, date=payload.date, marked_count=marked_count)
