from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUser, require_roles
from app.modules.parents import service as parents
from app.modules.scholarships import service
from app.modules.scholarships.service import SchemeSummary, ScholarshipIn, ScholarshipOut, ScholarshipUpdate

router = APIRouter(prefix="/scholarships", tags=["scholarships"])
portal_router = APIRouter(prefix="/me/parent/children", tags=["parent portal"])

_admin = require_roles("admin")


@router.get("", response_model=list[ScholarshipOut])
async def list_all(
    class_id: str | None = None, status: str | None = None, academic_year: str | None = None, scheme: str | None = None,
    current_user: CurrentUser = Depends(_admin),
) -> list[ScholarshipOut]:
    return await service.list_all(current_user, class_id, status, academic_year, scheme)


@router.get("/summary", response_model=list[SchemeSummary])
async def summary(academic_year: str | None = None, current_user: CurrentUser = Depends(_admin)) -> list[SchemeSummary]:
    return await service.summary(current_user, academic_year)


@router.post("", response_model=ScholarshipOut, status_code=status.HTTP_201_CREATED)
async def create(payload: ScholarshipIn, current_user: CurrentUser = Depends(_admin)) -> ScholarshipOut:
    return await service.create(current_user, payload)


@router.put("/{scholarship_id}", response_model=ScholarshipOut)
async def update(scholarship_id: str, payload: ScholarshipUpdate, current_user: CurrentUser = Depends(_admin)) -> ScholarshipOut:
    return await service.update(current_user, scholarship_id, payload)


@router.delete("/{scholarship_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(scholarship_id: str, current_user: CurrentUser = Depends(_admin)) -> None:
    await service.delete(current_user, scholarship_id)


@portal_router.get("/{student_id}/scholarships", response_model=list[ScholarshipOut])
async def child_scholarships(student_id: str, current_user: CurrentUser = Depends(require_roles("parent", "student"))) -> list[ScholarshipOut]:
    child = await parents.child_row(current_user, student_id)
    return await service.for_student(child["id"])
