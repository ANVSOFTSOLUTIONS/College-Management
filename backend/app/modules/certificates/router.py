from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUser, require_roles
from app.modules.certificates import service
from app.modules.certificates.service import CancelCertificateRequest, CertificateOut, IdCardSheet, IssueCertificateRequest

router = APIRouter(tags=["certificates"])

_admin = require_roles("admin")


@router.post("/students/{student_id}/certificates", response_model=CertificateOut, status_code=status.HTTP_201_CREATED)
async def issue_certificate(student_id: str, payload: IssueCertificateRequest, current_user: CurrentUser = Depends(_admin)) -> CertificateOut:
    """Issues a TC (which also marks the student as left) or a bonafide certificate, with the next serial number."""
    return await service.issue(current_user, student_id, payload)


@router.get("/students/{student_id}/certificates", response_model=list[CertificateOut])
async def student_certificates(student_id: str, current_user: CurrentUser = Depends(_admin)) -> list[CertificateOut]:
    return await service.list_for_student(current_user, student_id)


@router.get("/certificates", response_model=list[CertificateOut])
async def recent_certificates(current_user: CurrentUser = Depends(_admin)) -> list[CertificateOut]:
    """The 50 most recently issued certificates."""
    return await service.recent(current_user)


@router.get("/certificates/{certificate_id}", response_model=CertificateOut)
async def get_certificate(certificate_id: str, current_user: CurrentUser = Depends(_admin)) -> CertificateOut:
    return await service.get(current_user, certificate_id)


@router.post("/certificates/{certificate_id}/cancel", response_model=CertificateOut)
async def cancel_certificate(certificate_id: str, payload: CancelCertificateRequest, current_user: CurrentUser = Depends(_admin)) -> CertificateOut:
    """Marks a certificate issued by mistake as cancelled; its serial number is never reused."""
    return await service.cancel(current_user, certificate_id, payload)


@router.get("/id-cards", response_model=IdCardSheet)
async def id_cards(class_id: str, current_user: CurrentUser = Depends(_admin)) -> IdCardSheet:
    """Data for printing ID cards for a class's current students. Photos come from /students/{id}/photo."""
    return await service.id_cards(current_user, class_id)
