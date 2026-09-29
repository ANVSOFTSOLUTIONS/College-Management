import uuid

import aiomysql
from fastapi import status

from app.core.errors import AppError
from app.core.modules import school_modules
from app.db.helpers import execute, fetch_all, fetch_one
from app.modules.admissions import service as admissions
from app.modules.super_admin.schemas import FREE_TEMPLATES
from app.modules.school_site.schemas import (
    ActivityItem,
    BannerItem,
    ContactInfo,
    CustomizeRequest,
    GalleryItem,
    NoticeItem,
    SchoolSiteResponse,
)
from app.modules.school_site.storage import delete_uploaded_file


async def _to_response(school: dict, site: dict) -> SchoolSiteResponse:
    site_id = site["id"]
    banners = await fetch_all(
        "SELECT id, url, caption FROM school_site_banners WHERE school_site_id = %s ORDER BY sort_order, created_at",
        (site_id,),
    )
    gallery = await fetch_all(
        "SELECT id, url, caption FROM school_site_gallery WHERE school_site_id = %s ORDER BY created_at",
        (site_id,),
    )
    activities = await fetch_all(
        "SELECT id, title, activity_date, description FROM school_site_activities WHERE school_site_id = %s ORDER BY activity_date DESC",
        (site_id,),
    )
    notices = await fetch_all(
        "SELECT id, title, notice_date FROM school_site_notices WHERE school_site_id = %s ORDER BY notice_date DESC",
        (site_id,),
    )

    return SchoolSiteResponse(
        school_id=school["id"],
        name=school["name"],
        code=school["code"],
        subdomain=school["subdomain"],
        template=school["template"],
        logo_url=site["logo_url"],
        banners=[BannerItem(id=b["id"], url=b["url"], caption=b["caption"]) for b in banners],
        about=site["about"],
        contact=ContactInfo(
            address=site["contact_address"],
            phone=site["contact_phone"],
            email=site["contact_email"],
            map_url=site["contact_map_url"],
        ),
        gallery=[GalleryItem(id=g["id"], url=g["url"], caption=g["caption"]) for g in gallery],
        activities=[
            ActivityItem(id=a["id"], title=a["title"], date=a["activity_date"].isoformat(), description=a["description"])
            for a in activities
        ],
        notices=[NoticeItem(id=n["id"], title=n["title"], date=n["notice_date"].isoformat()) for n in notices],
        tagline=site["tagline"],
        primary_color=site["primary_color"],
        accent_color=site["accent_color"],
        hidden_sections=[x for x in site["hidden_sections"].split(",") if x],
        pro_templates=bool(school["pro_templates"]),
    )


async def get_school(school_id: str) -> dict:
    school = await fetch_one("SELECT * FROM schools WHERE id = %s", (school_id,))
    if school is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "school_not_found", "School not found.")
    return school


async def get_or_create_site(school_id: str) -> dict:
    site = await fetch_one("SELECT * FROM school_sites WHERE school_id = %s", (school_id,))
    if site is not None:
        return site

    try:
        await execute(
            """
            INSERT INTO school_sites (id, school_id, logo_url, about, contact_address, contact_phone, contact_email, contact_map_url)
            VALUES (%s, %s, NULL, '', '', '', '', '')
            """,
            (str(uuid.uuid4()), school_id),
        )
    except aiomysql.IntegrityError:
        pass

    return await fetch_one("SELECT * FROM school_sites WHERE school_id = %s", (school_id,))


async def get_site_for_school(school_id: str) -> SchoolSiteResponse:
    school = await get_school(school_id)
    site = await get_or_create_site(school_id)
    return await _to_response(school, site)


async def get_public_site(identifier: str) -> SchoolSiteResponse:
    school = await fetch_one(
        "SELECT * FROM schools WHERE status = 'active' AND (code = %s OR subdomain = %s)",
        (identifier.upper(), identifier.lower()),
    )
    if school is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "school_not_found", "School not found.")
    site = await get_or_create_site(school["id"])
    response = await _to_response(school, site)
    response.admissions_open = "admissions" in await school_modules(school["id"]) and await admissions.is_open(school["id"])
    return response


async def update_about_contact(school_id: str, *, about: str, contact: ContactInfo) -> SchoolSiteResponse:
    await get_or_create_site(school_id)
    await execute(
        """
        UPDATE school_sites
        SET about = %s, contact_address = %s, contact_phone = %s, contact_email = %s, contact_map_url = %s
        WHERE school_id = %s
        """,
        (about, contact.address, contact.phone, contact.email, contact.map_url, school_id),
    )
    return await get_site_for_school(school_id)


async def set_template(school_id: str, template: str) -> SchoolSiteResponse:
    school = await fetch_one("SELECT template, pro_templates FROM schools WHERE id = %s", (school_id,))
    # A school keeps the template it already has, but switching to a Pro one needs Pro.
    if template not in FREE_TEMPLATES and template != school["template"] and not school["pro_templates"]:
        raise AppError(
            status.HTTP_403_FORBIDDEN, "pro_required", "This is a Pro template. Contact ANV Soft Solutions to unlock all templates."
        )
    await execute("UPDATE schools SET template = %s WHERE id = %s", (template, school_id))
    return await get_site_for_school(school_id)


async def customize(school_id: str, payload: CustomizeRequest) -> SchoolSiteResponse:
    await get_or_create_site(school_id)
    await execute(
        "UPDATE school_sites SET tagline = %s, primary_color = %s, accent_color = %s, hidden_sections = %s WHERE school_id = %s",
        (payload.tagline, payload.primary_color, payload.accent_color, ",".join(sorted(set(payload.hidden_sections))), school_id),
    )
    return await get_site_for_school(school_id)


async def add_notice(school_id: str, *, title: str, iso_date: str) -> SchoolSiteResponse:
    site = await get_or_create_site(school_id)
    await execute(
        "INSERT INTO school_site_notices (id, school_site_id, title, notice_date) VALUES (%s, %s, %s, %s)",
        (str(uuid.uuid4()), site["id"], title, iso_date),
    )
    return await get_site_for_school(school_id)


async def remove_notice(school_id: str, notice_id: str) -> SchoolSiteResponse:
    site = await get_or_create_site(school_id)
    await execute("DELETE FROM school_site_notices WHERE id = %s AND school_site_id = %s", (notice_id, site["id"]))
    return await get_site_for_school(school_id)


async def set_logo(school_id: str, logo_url: str) -> SchoolSiteResponse:
    await get_or_create_site(school_id)
    await execute("UPDATE school_sites SET logo_url = %s WHERE school_id = %s", (logo_url, school_id))
    return await get_site_for_school(school_id)


async def add_banner(school_id: str, *, url: str, caption: str) -> SchoolSiteResponse:
    site = await get_or_create_site(school_id)
    await execute(
        "INSERT INTO school_site_banners (id, school_site_id, url, caption) VALUES (%s, %s, %s, %s)",
        (str(uuid.uuid4()), site["id"], url, caption),
    )
    return await get_site_for_school(school_id)


async def remove_banner(school_id: str, banner_id: str) -> SchoolSiteResponse:
    site = await get_or_create_site(school_id)
    banner = await fetch_one(
        "SELECT * FROM school_site_banners WHERE id = %s AND school_site_id = %s", (banner_id, site["id"])
    )
    await execute("DELETE FROM school_site_banners WHERE id = %s AND school_site_id = %s", (banner_id, site["id"]))
    if banner:
        delete_uploaded_file(banner["url"])
    return await get_site_for_school(school_id)


async def add_gallery_image(school_id: str, *, url: str, caption: str) -> SchoolSiteResponse:
    site = await get_or_create_site(school_id)
    await execute(
        "INSERT INTO school_site_gallery (id, school_site_id, url, caption) VALUES (%s, %s, %s, %s)",
        (str(uuid.uuid4()), site["id"], url, caption),
    )
    return await get_site_for_school(school_id)


async def remove_gallery_image(school_id: str, image_id: str) -> SchoolSiteResponse:
    site = await get_or_create_site(school_id)
    image = await fetch_one(
        "SELECT * FROM school_site_gallery WHERE id = %s AND school_site_id = %s", (image_id, site["id"])
    )
    await execute("DELETE FROM school_site_gallery WHERE id = %s AND school_site_id = %s", (image_id, site["id"]))
    if image:
        delete_uploaded_file(image["url"])
    return await get_site_for_school(school_id)


async def add_activity(school_id: str, *, title: str, iso_date: str, description: str) -> SchoolSiteResponse:
    site = await get_or_create_site(school_id)
    await execute(
        "INSERT INTO school_site_activities (id, school_site_id, title, activity_date, description) VALUES (%s, %s, %s, %s, %s)",
        (str(uuid.uuid4()), site["id"], title, iso_date, description),
    )
    return await get_site_for_school(school_id)


async def remove_activity(school_id: str, activity_id: str) -> SchoolSiteResponse:
    site = await get_or_create_site(school_id)
    await execute(
        "DELETE FROM school_site_activities WHERE id = %s AND school_site_id = %s", (activity_id, site["id"])
    )
    return await get_site_for_school(school_id)
