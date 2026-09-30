from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, require_roles
from app.modules.hod import service
from app.modules.hod.service import HodOverview

router = APIRouter(prefix="/hod", tags=["hod"])


@router.get("/overview", response_model=HodOverview)
async def overview(current_user: CurrentUser = Depends(require_roles("teacher"))) -> HodOverview:
    """Today in the department(s) the signed-in faculty member heads."""
    return await service.overview(current_user)
