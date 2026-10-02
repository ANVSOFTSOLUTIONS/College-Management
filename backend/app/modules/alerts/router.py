from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, require_roles
from app.modules.alerts import service
from app.modules.alerts.service import AlertOut, AlertSettingsOut

router = APIRouter(prefix="/parent-alerts", tags=["parent alerts"])

_staff = require_roles("admin", "teacher")


@router.get("", response_model=list[AlertOut])
async def list_alerts(
    class_id: str | None = None,
    student_id: str | None = None,
    limit: int = Query(default=200, ge=1, le=500),
    current_user: CurrentUser = Depends(_staff),
) -> list[AlertOut]:
    return await service.list_alerts(current_user, class_id=class_id, student_id=student_id, limit=limit)


@router.get("/settings", response_model=AlertSettingsOut)
async def alert_settings(current_user: CurrentUser = Depends(_staff)) -> AlertSettingsOut:
    return service.alert_settings()

