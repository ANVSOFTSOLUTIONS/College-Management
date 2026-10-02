from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUser, require_roles
from app.modules.parents import service as parents
from app.modules.certificates import requests, service
from app.modules.certificates.requests import DecisionIn, RequestIn, RequestOut
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


@router.get("/certificate-requests", response_model=list[RequestOut])
async def list_requests(status: str | None = None, current_user: CurrentUser = Depends(_admin)) -> list[RequestOut]:
    return await requests.list_all(current_user, status)


@router.post("/certificate-requests/{request_id}/approve", response_model=RequestOut)
async def approve_request(request_id: str, payload: DecisionIn, current_user: CurrentUser = Depends(_admin)) -> RequestOut:
    """Issues the certificate (next serial number) and tells the requester to collect it."""
    return await requests.approve(current_user, request_id, payload)


@router.post("/certificate-requests/{request_id}/reject", response_model=RequestOut)
async def reject_request(request_id: str, payload: DecisionIn, current_user: CurrentUser = Depends(_admin)) -> RequestOut:
    return await requests.reject(current_user, request_id, payload)


@router.get("/me/parent/children/{student_id}/certificate-requests", response_model=list[RequestOut])
async def child_requests(student_id: str, current_user: CurrentUser = Depends(require_roles("parent", "student"))) -> list[RequestOut]:
    child = await parents.child_row(current_user, student_id)
    return await requests.for_student(child["id"])


@router.post("/me/parent/children/{student_id}/certificate-requests", response_model=list[RequestOut], status_code=status.HTTP_201_CREATED)
async def request_certificate(student_id: str, payload: RequestIn, current_user: CurrentUser = Depends(require_roles("parent", "student"))) -> list[RequestOut]:
    return await requests.create(current_user, await parents.child_row(current_user, student_id), payload)
