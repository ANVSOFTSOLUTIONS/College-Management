from fastapi import APIRouter, Depends, Response

from app.api.deps import CurrentUser, require_roles
from app.modules.audit import service as audit
from app.modules.super_admin import earnings, service
from app.modules.super_admin.schemas import (
    CreateSchoolRequest,
    CreateSchoolResponse,
    SchoolSummary,
    UpdateSchoolRequest,
)

router = APIRouter(prefix="/super-admin/schools", tags=["super-admin"])

_super_admin_only = require_roles("super_admin")


@router.get("", response_model=list[SchoolSummary])
async def list_schools(current_user: CurrentUser = Depends(_super_admin_only)) -> list[SchoolSummary]:
    return await service.list_schools()


@router.post("", response_model=CreateSchoolResponse)
async def create_school(
    payload: CreateSchoolRequest,
    current_user: CurrentUser = Depends(_super_admin_only),
) -> CreateSchoolResponse:
    school, admin_email = await service.create_school(payload)
    return CreateSchoolResponse(school=school, admin_email=admin_email)


@router.patch("/{school_id}", response_model=SchoolSummary)
async def update_school(
    school_id: str,
    payload: UpdateSchoolRequest,
    current_user: CurrentUser = Depends(_super_admin_only),
) -> SchoolSummary:
    school = await service.update_school(school_id, payload)
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    if changes:
        await audit.record(
            current_user, "settings.school", f"Super admin changed {school.name}: "
            + ", ".join(f"{k.replace('_', ' ')} → {', '.join(v) if isinstance(v, list) else v}" for k, v in changes.items()),
            school_id=school_id, entity_type="school", entity_id=school_id, details=changes,
        )
    return school


# --- Platform analytics and earnings ---------------------------------------------------------

platform_router = APIRouter(prefix="/super-admin", tags=["super-admin"])


@platform_router.get("/analytics", response_model=earnings.Analytics)
async def analytics(current_user: CurrentUser = Depends(_super_admin_only)) -> earnings.Analytics:
    """Schools, students, recurring revenue and money received, with the last 12 months."""
    return await earnings.analytics()


@platform_router.get("/payments", response_model=list[earnings.PlatformPaymentOut])
async def list_payments(school_id: str | None = None, current_user: CurrentUser = Depends(_super_admin_only)) -> list[earnings.PlatformPaymentOut]:
    return await earnings.list_payments(school_id)


@platform_router.post("/payments", response_model=earnings.PlatformPaymentOut, status_code=201)
async def record_payment(payload: earnings.RecordPaymentIn, current_user: CurrentUser = Depends(_super_admin_only)) -> earnings.PlatformPaymentOut:
    """Money a school paid the platform (subscription, Pro templates, setup)."""
    payment = await earnings.record_payment(current_user, payload)
    await audit.record(
        current_user, "settings.platform_payment", f"Recorded ₹{payment.amount:g} from {payment.school_name} ({payment.purpose_label})",
        school_id=payment.school_id, entity_type="platform_payment", entity_id=payment.id,
    )
    return payment


@platform_router.delete("/payments/{payment_id}", status_code=204)
async def delete_payment(payment_id: str, current_user: CurrentUser = Depends(_super_admin_only)) -> Response:
    """Removes a payment recorded by mistake."""
    await earnings.delete_payment(payment_id)
    return Response(status_code=204)
