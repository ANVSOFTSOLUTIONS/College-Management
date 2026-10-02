from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, require_roles
from app.modules.promotion import service
from app.modules.promotion.service import (
    PromotionPlan,
    PromotionResult,
    RunPromotionRequest,
    SemesterPlan,
    SemesterPromotionRequest,
    SemesterPromotionResult,
)

router = APIRouter(prefix="/promotion", tags=["promotion"])
_admin_only = require_roles("admin")


@router.get("/plan", response_model=PromotionPlan)
async def plan(from_year: str | None = None, current_user: CurrentUser = Depends(_admin_only)) -> PromotionPlan:
    """Classes of an academic year with their students and a suggested next class for each."""
    return await service.plan(current_user, from_year)


@router.get("/semester/plan", response_model=SemesterPlan)
async def semester_plan(
    class_id: str, max_backlogs: int | None = None, min_attendance: float | None = None, current_user: CurrentUser = Depends(_admin_only)
) -> SemesterPlan:
    """A batch's students with backlogs and attendance; `eligible` is false when they break the given rules."""
    return await service.semester_plan(current_user, class_id, max_backlogs, min_attendance)


@router.post("/semester", response_model=SemesterPromotionResult)
async def run_semester(payload: SemesterPromotionRequest, current_user: CurrentUser = Depends(_admin_only)) -> SemesterPromotionResult:
    """Moves a batch to its next semester (or graduates it); detained students go to a junior batch of the same semester."""
    return await service.run_semester(current_user, payload)


@router.post("", response_model=PromotionResult)
async def run(payload: RunPromotionRequest, current_user: CurrentUser = Depends(_admin_only)) -> PromotionResult:
    """Moves every class up for the new year (or graduates it); runs once per academic year."""
    return await service.run(current_user, payload)
