from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, require_roles
from app.modules.promotion import service
from app.modules.promotion.service import PromotionPlan, PromotionResult, RunPromotionRequest

router = APIRouter(prefix="/promotion", tags=["promotion"])
_admin_only = require_roles("admin")


@router.get("/plan", response_model=PromotionPlan)
async def plan(from_year: str | None = None, current_user: CurrentUser = Depends(_admin_only)) -> PromotionPlan:
    """Classes of an academic year with their students and a suggested next class for each."""
    return await service.plan(current_user, from_year)


@router.post("", response_model=PromotionResult)
async def run(payload: RunPromotionRequest, current_user: CurrentUser = Depends(_admin_only)) -> PromotionResult:
    """Moves every class up for the new year (or graduates it); runs once per academic year."""
    return await service.run(current_user, payload)
