from fastapi import APIRouter, Depends, Response, status

from app.api.deps import CurrentUser, require_roles
from app.modules.placements import service
from app.modules.placements.service import (
    ApplicationOut,
    CompanyIn,
    CompanyOut,
    DriveIn,
    DriveOut,
    PlacementStats,
    StatusIn,
    StudentDriveOut,
)

router = APIRouter(prefix="/placements", tags=["placements"])

_admin_only = require_roles("admin")
_student_only = require_roles("student")


def _done() -> Response:
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/stats", response_model=PlacementStats)
async def stats(current_user: CurrentUser = Depends(require_roles("admin", "teacher"))) -> PlacementStats:
    return await service.stats(current_user.school_id)


@router.get("/companies", response_model=list[CompanyOut])
async def list_companies(current_user: CurrentUser = Depends(_admin_only)) -> list[CompanyOut]:
    return await service.list_companies(current_user.school_id)


@router.post("/companies", status_code=status.HTTP_204_NO_CONTENT)
async def create_company(payload: CompanyIn, current_user: CurrentUser = Depends(_admin_only)) -> Response:
    await service.create_company(current_user.school_id, payload)
    return _done()


@router.put("/companies/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_company(company_id: str, payload: CompanyIn, current_user: CurrentUser = Depends(_admin_only)) -> Response:
    await service.update_company(current_user.school_id, company_id, payload)
    return _done()


@router.delete("/companies/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company(company_id: str, current_user: CurrentUser = Depends(_admin_only)) -> Response:
    await service.delete_company(current_user.school_id, company_id)
    return _done()


@router.get("/drives", response_model=list[DriveOut])
async def list_drives(current_user: CurrentUser = Depends(require_roles("admin", "teacher"))) -> list[DriveOut]:
    return await service.list_drives(current_user.school_id)


@router.post("/drives", response_model=DriveOut, status_code=status.HTTP_201_CREATED)
async def create_drive(payload: DriveIn, current_user: CurrentUser = Depends(_admin_only)) -> DriveOut:
    return await service.create_drive(current_user.school_id, payload)


@router.put("/drives/{drive_id}", response_model=DriveOut)
async def update_drive(drive_id: str, payload: DriveIn, current_user: CurrentUser = Depends(_admin_only)) -> DriveOut:
    return await service.update_drive(current_user.school_id, drive_id, payload)


@router.delete("/drives/{drive_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_drive(drive_id: str, current_user: CurrentUser = Depends(_admin_only)) -> Response:
    await service.delete_drive(current_user.school_id, drive_id)
    return _done()


@router.get("/drives/{drive_id}/applications", response_model=list[ApplicationOut])
async def applications(drive_id: str, current_user: CurrentUser = Depends(_admin_only)) -> list[ApplicationOut]:
    return await service.applications(current_user.school_id, drive_id)


@router.put("/applications/{application_id}/status", status_code=status.HTTP_204_NO_CONTENT)
async def set_status(application_id: str, payload: StatusIn, current_user: CurrentUser = Depends(_admin_only)) -> Response:
    await service.set_status(current_user.school_id, application_id, payload.status)
    return _done()


# --- Students ---------------------------------------------------------------------


@router.get("/my-drives", response_model=list[StudentDriveOut])
async def my_drives(current_user: CurrentUser = Depends(_student_only)) -> list[StudentDriveOut]:
    return await service.student_drives(current_user)


@router.post("/drives/{drive_id}/apply", status_code=status.HTTP_204_NO_CONTENT)
async def apply(drive_id: str, current_user: CurrentUser = Depends(_student_only)) -> Response:
    await service.apply(current_user, drive_id)
    return _done()


@router.delete("/drives/{drive_id}/apply", status_code=status.HTTP_204_NO_CONTENT)
async def withdraw(drive_id: str, current_user: CurrentUser = Depends(_student_only)) -> Response:
    await service.withdraw(current_user, drive_id)
    return _done()
