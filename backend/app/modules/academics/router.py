from fastapi import APIRouter, Depends, Response, status

from app.api.deps import CurrentUser, require_roles
from app.modules.academics import service
from app.modules.academics.schemas import (
    AssignSubjectTeacherRequest,
    ClassDetail,
    CreateClassRequest,
    CreateTeacherRequest,
    DepartmentOut,
    DepartmentRequest,
    SubjectOut,
    SubjectRequest,
    TeacherOut,
    UpdateClassRequest,
    UpdateTeacherRequest,
)
from app.modules.audit import service as audit

teachers_router = APIRouter(prefix="/teachers", tags=["teachers"])
subjects_router = APIRouter(prefix="/subjects", tags=["subjects"])
classes_admin_router = APIRouter(prefix="/classes", tags=["classes"])
departments_router = APIRouter(prefix="/departments", tags=["departments"])

_admin_only = require_roles("admin")


# --- Teachers -----------------------------------------------------------------


@teachers_router.get("", response_model=list[TeacherOut])
async def list_teachers(current_user: CurrentUser = Depends(_admin_only)) -> list[TeacherOut]:
    return await service.list_teachers(current_user.school_id)


@teachers_router.post("", response_model=TeacherOut, status_code=status.HTTP_201_CREATED)
async def create_teacher(payload: CreateTeacherRequest, current_user: CurrentUser = Depends(_admin_only)) -> TeacherOut:
    return await service.create_teacher(current_user.school_id, payload)


@teachers_router.get("/{teacher_id}", response_model=TeacherOut)
async def get_teacher(teacher_id: str, current_user: CurrentUser = Depends(_admin_only)) -> TeacherOut:
    return await service.get_teacher(current_user.school_id, teacher_id)


@teachers_router.patch("/{teacher_id}", response_model=TeacherOut)
async def update_teacher(
    teacher_id: str, payload: UpdateTeacherRequest, current_user: CurrentUser = Depends(_admin_only)
) -> TeacherOut:
    teacher = await service.update_teacher(current_user.school_id, teacher_id, payload)
    changes = [c for c, on in (("password reset", payload.password), (f"status → {payload.status}", payload.status)) if on]
    if changes:
        await audit.record(current_user, "staff.changed", f"{teacher.full_name}: {', '.join(changes)}", entity_type="teacher", entity_id=teacher_id)
    return teacher


@teachers_router.delete("/{teacher_id}", response_model=TeacherOut)
async def remove_teacher(teacher_id: str, current_user: CurrentUser = Depends(_admin_only)) -> TeacherOut:
    """Deactivates the teacher (blocks login); their attendance history is kept."""
    teacher = await service.update_teacher(current_user.school_id, teacher_id, UpdateTeacherRequest(status="inactive"))
    await audit.record(current_user, "staff.changed", f"Deactivated {teacher.full_name}", entity_type="teacher", entity_id=teacher_id)
    return teacher


# --- Subjects -----------------------------------------------------------------


@subjects_router.get("", response_model=list[SubjectOut])
async def list_subjects(current_user: CurrentUser = Depends(_admin_only)) -> list[SubjectOut]:
    return await service.list_subjects(current_user.school_id)


@subjects_router.post("", response_model=SubjectOut, status_code=status.HTTP_201_CREATED)
async def create_subject(payload: SubjectRequest, current_user: CurrentUser = Depends(_admin_only)) -> SubjectOut:
    return await service.create_subject(current_user.school_id, payload)


@subjects_router.put("/{subject_id}", response_model=SubjectOut)
async def update_subject(
    subject_id: str, payload: SubjectRequest, current_user: CurrentUser = Depends(_admin_only)
) -> SubjectOut:
    return await service.update_subject(current_user.school_id, subject_id, payload)


@subjects_router.delete("/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subject(subject_id: str, current_user: CurrentUser = Depends(_admin_only)) -> Response:
    await service.delete_subject(current_user.school_id, subject_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Classes (admin management; the class list itself lives in the attendance module) ---


@classes_admin_router.post("", response_model=ClassDetail, status_code=status.HTTP_201_CREATED)
async def create_class(payload: CreateClassRequest, current_user: CurrentUser = Depends(_admin_only)) -> ClassDetail:
    return await service.create_class(current_user.school_id, payload)


@classes_admin_router.get("/{class_id}", response_model=ClassDetail)
async def get_class(class_id: str, current_user: CurrentUser = Depends(_admin_only)) -> ClassDetail:
    return await service.get_class(current_user.school_id, class_id)


@classes_admin_router.patch("/{class_id}", response_model=ClassDetail)
async def update_class(
    class_id: str, payload: UpdateClassRequest, current_user: CurrentUser = Depends(_admin_only)
) -> ClassDetail:
    return await service.update_class(current_user.school_id, class_id, payload)


@classes_admin_router.delete("/{class_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_class(class_id: str, current_user: CurrentUser = Depends(_admin_only)) -> Response:
    await service.delete_class(current_user.school_id, class_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@classes_admin_router.put("/{class_id}/subjects/{subject_id}", response_model=ClassDetail)
async def assign_subject_teacher(
    class_id: str,
    subject_id: str,
    payload: AssignSubjectTeacherRequest,
    current_user: CurrentUser = Depends(_admin_only),
) -> ClassDetail:
    return await service.assign_subject_teacher(current_user.school_id, class_id, subject_id, payload)


@classes_admin_router.delete("/{class_id}/subjects/{subject_id}", response_model=ClassDetail)
async def unassign_subject(
    class_id: str, subject_id: str, current_user: CurrentUser = Depends(_admin_only)
) -> ClassDetail:
    return await service.unassign_subject(current_user.school_id, class_id, subject_id)


# --- Departments --------------------------------------------------------------


@departments_router.get("", response_model=list[DepartmentOut])
async def list_departments(current_user: CurrentUser = Depends(require_roles("admin", "teacher"))) -> list[DepartmentOut]:
    return await service.list_departments(current_user.school_id)


@departments_router.post("", response_model=DepartmentOut, status_code=status.HTTP_201_CREATED)
async def create_department(payload: DepartmentRequest, current_user: CurrentUser = Depends(_admin_only)) -> DepartmentOut:
    department = await service.create_department(current_user.school_id, payload)
    await audit.record(current_user, "department.created", department.name, entity_type="department", entity_id=department.id)
    return department


@departments_router.put("/{department_id}", response_model=DepartmentOut)
async def update_department(
    department_id: str, payload: DepartmentRequest, current_user: CurrentUser = Depends(_admin_only)
) -> DepartmentOut:
    return await service.update_department(current_user.school_id, department_id, payload)


@departments_router.delete("/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_department(department_id: str, current_user: CurrentUser = Depends(_admin_only)) -> Response:
    await service.delete_department(current_user.school_id, department_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
