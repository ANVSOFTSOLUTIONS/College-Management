from datetime import date

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, require_roles
from app.modules.audit import service
from app.modules.audit.service import AuditEntry

router = APIRouter(prefix="/audit-log", tags=["audit log"])


@router.get("", response_model=list[AuditEntry])
async def list_entries(
    area: str | None = Query(default=None, pattern="^(marks|fees|attendance|students|staff|admissions|settings)$"),
    start: date | None = None,
    end: date | None = None,
    q: str | None = Query(default=None, max_length=100),
    school_id: str | None = None,
    current_user: CurrentUser = Depends(require_roles("admin", "super_admin")),
) -> list[AuditEntry]:
    """Newest first (at most 300). Admins see their school; the super admin any school, or all."""
    scope = current_user.school_id if current_user.role == "admin" else school_id
    return await service.list_entries(scope, area=area, start=start, end=end, query=q)
