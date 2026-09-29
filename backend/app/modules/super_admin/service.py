import json
import uuid

import aiomysql
from fastapi import status

from app.core.errors import AppError
from app.core.security import hash_password
from app.db.database import db
from app.db.helpers import execute, fetch_all, fetch_one
from app.modules.super_admin.schemas import CreateSchoolRequest, SchoolSummary, UpdateSchoolRequest, auto_template


def _to_summary(school: dict) -> SchoolSummary:
    enabled_modules = school["enabled_modules"]
    if isinstance(enabled_modules, str):
        enabled_modules = json.loads(enabled_modules)

    return SchoolSummary(
        id=school["id"],
        name=school["name"],
        code=school["code"],
        subdomain=school["subdomain"],
        template=school["template"],
        enabled_modules=enabled_modules,
        monthly_fee=float(school["monthly_fee"]),
        billing_status=school["billing_status"],
        status=school["status"],
        pro_templates=bool(school["pro_templates"]),
        payment_gateways=_json_list(school.get("payment_gateways")),
    )


def _json_list(value) -> list[str]:
    try:
        return json.loads(value) if isinstance(value, str) else list(value or [])
    except ValueError:
        return []


async def list_schools() -> list[SchoolSummary]:
    schools = await fetch_all("SELECT * FROM schools ORDER BY name")
    return [_to_summary(s) for s in schools]


async def create_school(payload: CreateSchoolRequest) -> tuple[SchoolSummary, str]:
    subdomain = payload.subdomain or payload.code.lower()
    admin_email = payload.admin_email.lower()
    school_id = str(uuid.uuid4())

    async with db.pool.acquire() as conn:
        await conn.begin()
        async with conn.cursor() as cur:
            try:
                await cur.execute(
                    """
                    INSERT INTO schools (id, name, code, subdomain, template, enabled_modules, monthly_fee, billing_status, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'active')
                    """,
                    (
                        school_id,
                        payload.name,
                        payload.code,
                        subdomain,
                        payload.template or auto_template(payload.code),
                        json.dumps(payload.enabled_modules),
                        payload.monthly_fee,
                        payload.billing_status,
                    ),
                )
            except aiomysql.IntegrityError as exc:
                await conn.rollback()
                raise AppError(
                    status.HTTP_409_CONFLICT,
                    "school_already_exists",
                    "A school with this code or subdomain already exists.",
                ) from exc

            try:
                await cur.execute(
                    """
                    INSERT INTO users (id, school_id, email, password_hash, role, full_name, status)
                    VALUES (%s, %s, %s, %s, 'admin', %s, 'active')
                    """,
                    (
                        str(uuid.uuid4()),
                        school_id,
                        admin_email,
                        hash_password(payload.admin_password),
                        payload.admin_full_name,
                    ),
                )
            except aiomysql.IntegrityError as exc:
                await conn.rollback()
                raise AppError(
                    status.HTTP_409_CONFLICT, "admin_email_taken", "That admin email is already in use."
                ) from exc

        await conn.commit()

    school = await fetch_one("SELECT * FROM schools WHERE id = %s", (school_id,))
    return _to_summary(school), admin_email


async def update_school(school_id: str, payload: UpdateSchoolRequest) -> SchoolSummary:
    updates = payload.model_dump(exclude_unset=True, exclude_none=True)
    if not updates:
        school = await fetch_one("SELECT * FROM schools WHERE id = %s", (school_id,))
        if school is None:
            raise AppError(status.HTTP_404_NOT_FOUND, "school_not_found", "School not found.")
        return _to_summary(school)

    set_clauses = []
    params: list = []
    for field, value in updates.items():
        set_clauses.append(f"{field} = %s")
        params.append(json.dumps(value) if field in ("enabled_modules", "payment_gateways") else value)
    params.append(school_id)

    try:
        await execute(f"UPDATE schools SET {', '.join(set_clauses)} WHERE id = %s", tuple(params))
    except aiomysql.IntegrityError as exc:
        raise AppError(status.HTTP_409_CONFLICT, "subdomain_taken", "That subdomain is already in use.") from exc

    school = await fetch_one("SELECT * FROM schools WHERE id = %s", (school_id,))
    if school is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "school_not_found", "School not found.")
    return _to_summary(school)
