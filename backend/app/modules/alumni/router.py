from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUser, require_roles
from app.modules.alumni import service
from app.modules.alumni.service import AlumniSummary, AlumnusIn, AlumnusOut, ImportResult

router = APIRouter(prefix="/alumni", tags=["alumni"])
_admin = require_roles("admin")


@router.get("", response_model=list[AlumnusOut])
async def list_alumni(
    passing_year: str | None = None, status: str | None = None, q: str | None = None, current_user: CurrentUser = Depends(_admin)
) -> list[AlumnusOut]:
    return await service.list_alumni(current_user, passing_year, status, q)


@router.get("/summary", response_model=list[AlumniSummary])
async def summary(current_user: CurrentUser = Depends(_admin)) -> list[AlumniSummary]:
    return await service.summary(current_user)


@router.post("/import-graduated", response_model=ImportResult)
async def import_graduated(current_user: CurrentUser = Depends(_admin)) -> ImportResult:
    """Adds graduated students who aren't alumni yet."""
    return await service.import_graduated(current_user)


@router.post("", response_model=AlumnusOut, status_code=status.HTTP_201_CREATED)
async def create(payload: AlumnusIn, current_user: CurrentUser = Depends(_admin)) -> AlumnusOut:
    return await service.create(current_user, payload)


@router.put("/{alumnus_id}", response_model=AlumnusOut)
async def update(alumnus_id: str, payload: AlumnusIn, current_user: CurrentUser = Depends(_admin)) -> AlumnusOut:
    return await service.update(current_user, alumnus_id, payload)


@router.delete("/{alumnus_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(alumnus_id: str, current_user: CurrentUser = Depends(_admin)) -> None:
    await service.delete(current_user, alumnus_id)
