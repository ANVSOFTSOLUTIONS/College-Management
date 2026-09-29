from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.api.deps import CurrentUser, require_roles
from app.modules.school_site import service
from app.modules.school_site.schemas import (
    AboutContactRequest,
    ActivityRequest,
    CustomizeRequest,
    NoticeRequest,
    SchoolSiteResponse,
    TemplateRequest,
)
from app.modules.school_site.storage import save_image_upload

router = APIRouter(prefix="/school-site", tags=["school-site"])
public_router = APIRouter(prefix="/public/schools/{code}", tags=["public-school-site"])

_admin_only = require_roles("admin")


@router.get("", response_model=SchoolSiteResponse)
async def get_my_school_site(current_user: CurrentUser = Depends(_admin_only)) -> SchoolSiteResponse:
    return await service.get_site_for_school(current_user.school_id)


@router.put("/about-contact", response_model=SchoolSiteResponse)
async def save_about_contact(
    payload: AboutContactRequest,
    current_user: CurrentUser = Depends(_admin_only),
) -> SchoolSiteResponse:
    return await service.update_about_contact(
        current_user.school_id, about=payload.about, contact=payload.contact
    )


@router.put("/template", response_model=SchoolSiteResponse)
async def choose_template(payload: TemplateRequest, current_user: CurrentUser = Depends(_admin_only)) -> SchoolSiteResponse:
    """Switches the public site to another template; the content stays the same."""
    return await service.set_template(current_user.school_id, payload.template)


@router.put("/customize", response_model=SchoolSiteResponse)
async def customize(payload: CustomizeRequest, current_user: CurrentUser = Depends(_admin_only)) -> SchoolSiteResponse:
    """Tagline, own colours on top of the template, and sections to hide."""
    return await service.customize(current_user.school_id, payload)


@router.post("/notices", response_model=SchoolSiteResponse)
async def add_notice(payload: NoticeRequest, current_user: CurrentUser = Depends(_admin_only)) -> SchoolSiteResponse:
    return await service.add_notice(current_user.school_id, title=payload.title, iso_date=payload.date.isoformat())


@router.delete("/notices/{notice_id}", response_model=SchoolSiteResponse)
async def delete_notice(notice_id: str, current_user: CurrentUser = Depends(_admin_only)) -> SchoolSiteResponse:
    return await service.remove_notice(current_user.school_id, notice_id)


@router.post("/logo", response_model=SchoolSiteResponse)
async def upload_logo(
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(_admin_only),
) -> SchoolSiteResponse:
    logo_url = await save_image_upload(current_user.school_id, file)
    return await service.set_logo(current_user.school_id, logo_url)


@router.post("/banners", response_model=SchoolSiteResponse)
async def upload_banner(
    file: UploadFile = File(...),
    caption: str = Form(""),
    current_user: CurrentUser = Depends(_admin_only),
) -> SchoolSiteResponse:
    url = await save_image_upload(current_user.school_id, file)
    return await service.add_banner(current_user.school_id, url=url, caption=caption or file.filename)


@router.delete("/banners/{banner_id}", response_model=SchoolSiteResponse)
async def delete_banner(banner_id: str, current_user: CurrentUser = Depends(_admin_only)) -> SchoolSiteResponse:
    return await service.remove_banner(current_user.school_id, banner_id)


@router.post("/gallery", response_model=SchoolSiteResponse)
async def upload_gallery_image(
    file: UploadFile = File(...),
    caption: str = Form(""),
    current_user: CurrentUser = Depends(_admin_only),
) -> SchoolSiteResponse:
    url = await save_image_upload(current_user.school_id, file)
    return await service.add_gallery_image(current_user.school_id, url=url, caption=caption or file.filename)


@router.delete("/gallery/{image_id}", response_model=SchoolSiteResponse)
async def delete_gallery_image(image_id: str, current_user: CurrentUser = Depends(_admin_only)) -> SchoolSiteResponse:
    return await service.remove_gallery_image(current_user.school_id, image_id)


@router.post("/activities", response_model=SchoolSiteResponse)
async def create_activity(
    payload: ActivityRequest,
    current_user: CurrentUser = Depends(_admin_only),
) -> SchoolSiteResponse:
    return await service.add_activity(
        current_user.school_id,
        title=payload.title,
        iso_date=payload.date.isoformat(),
        description=payload.description,
    )


@router.delete("/activities/{activity_id}", response_model=SchoolSiteResponse)
async def delete_activity(activity_id: str, current_user: CurrentUser = Depends(_admin_only)) -> SchoolSiteResponse:
    return await service.remove_activity(current_user.school_id, activity_id)


@public_router.get("/site", response_model=SchoolSiteResponse)
async def get_public_school_site(code: str) -> SchoolSiteResponse:
    return await service.get_public_site(code)
