"""Create a platform super admin — the first login on a fresh database.

Safe for production: nothing is hard-coded, the password is read without
echoing and never printed. Uses the same MYSQL_* / JWT_* environment
variables as the app. Run from backend/:

    python -m scripts.create_super_admin
"""

import asyncio
import getpass
import uuid

import aiomysql
from pydantic import BaseModel, EmailStr, Field, ValidationError

from app.core.config import get_settings
from app.core.security import hash_password


class SuperAdminInput(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=8, max_length=72)


async def create_super_admin(conn, data: SuperAdminInput) -> bool:
    """Insert the super admin; returns False if the email is already taken."""
    email = data.email.lower()
    async with conn.cursor() as cur:
        await cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        if await cur.fetchone() is not None:
            return False
        await cur.execute(
            """
            INSERT INTO users (id, school_id, email, password_hash, role, full_name, status)
            VALUES (%s, NULL, %s, %s, 'super_admin', %s, 'active')
            """,
            (str(uuid.uuid4()), email, hash_password(data.password), data.full_name.strip()),
        )
    return True


def _prompt() -> SuperAdminInput:
    email = input("Email: ").strip()
    full_name = input("Full name: ").strip()
    password = getpass.getpass("Password (8-72 characters): ")
    if getpass.getpass("Repeat password: ") != password:
        raise SystemExit("Passwords do not match.")
    try:
        return SuperAdminInput(email=email, full_name=full_name, password=password)
    except ValidationError as exc:
        messages = "; ".join(f"{e['loc'][0]}: {e['msg']}" for e in exc.errors())
        raise SystemExit(f"Invalid input — {messages}") from None


async def main() -> None:
    data = _prompt()
    settings = get_settings()
    conn = await aiomysql.connect(
        host=settings.mysql_host,
        port=settings.mysql_port,
        user=settings.mysql_user,
        password=settings.mysql_password,
        db=settings.mysql_database,
        autocommit=True,
    )
    try:
        created = await create_super_admin(conn, data)
    finally:
        conn.close()
    if not created:
        raise SystemExit(f"A user with email {data.email.lower()} already exists; nothing changed.")
    print(f"Super admin created: {data.email.lower()}")


if __name__ == "__main__":
    asyncio.run(main())
