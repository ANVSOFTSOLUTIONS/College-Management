import asyncio
import json
import uuid

import aiomysql

from app.core.config import get_settings
from app.core.security import hash_password
from app.core.modules import OPTIONAL_MODULES

DEFAULT_MODULES = list(OPTIONAL_MODULES)


async def seed_school(
    conn, *, code, name, subdomain, template, admin_email, teacher_email, teacher_name, class_name, section, students
):
    async with conn.cursor() as cur:
        school_id = str(uuid.uuid4())
        await cur.execute(
            """
            INSERT INTO schools (id, name, code, subdomain, template, enabled_modules, monthly_fee, billing_status, status)
            VALUES (%s, %s, %s, %s, %s, %s, 600, 'active', 'active')
            """,
            (school_id, name, code, subdomain, template, json.dumps(DEFAULT_MODULES)),
        )

        await cur.execute(
            """
            INSERT INTO users (id, school_id, email, password_hash, role, full_name, status)
            VALUES (%s, %s, %s, %s, 'admin', %s, 'active')
            """,
            (str(uuid.uuid4()), school_id, admin_email, hash_password("Admin@12345"), f"{name} Admin"),
        )

        teacher_user_id = str(uuid.uuid4())
        await cur.execute(
            """
            INSERT INTO users (id, school_id, email, password_hash, role, full_name, status)
            VALUES (%s, %s, %s, %s, 'teacher', %s, 'active')
            """,
            (teacher_user_id, school_id, teacher_email, hash_password("Teacher@12345"), teacher_name),
        )

        teacher_id = str(uuid.uuid4())
        await cur.execute(
            "INSERT INTO teachers (id, school_id, user_id, department) VALUES (%s, %s, %s, 'General')",
            (teacher_id, school_id, teacher_user_id),
        )

        class_id = str(uuid.uuid4())
        await cur.execute(
            """
            INSERT INTO classes (id, school_id, teacher_id, name, section, academic_year)
            VALUES (%s, %s, %s, %s, %s, '2026')
            """,
            (class_id, school_id, teacher_id, class_name, section),
        )

        for admission_number, full_name, parent_name in students:
            await cur.execute(
                """
                INSERT INTO students (id, school_id, class_id, admission_number, full_name, parent_name)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (str(uuid.uuid4()), school_id, class_id, admission_number, full_name, parent_name),
            )


async def seed_super_admin(conn, *, email, full_name):
    async with conn.cursor() as cur:
        await cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        if await cur.fetchone() is not None:
            print(f"Super admin {email} already exists, skipping.")
            return

        await cur.execute(
            """
            INSERT INTO users (id, school_id, email, password_hash, role, full_name, status)
            VALUES (%s, NULL, %s, %s, 'super_admin', %s, 'active')
            """,
            (str(uuid.uuid4()), email, hash_password("SuperAdmin@12345"), full_name),
        )
    print(f"Seeded super admin: {email} / SuperAdmin@12345")


async def main():
    settings = get_settings()
    pool = await aiomysql.create_pool(
        host=settings.mysql_host,
        port=settings.mysql_port,
        user=settings.mysql_user,
        password=settings.mysql_password,
        db=settings.mysql_database,
        autocommit=True,
    )

    async with pool.acquire() as conn:
        await seed_super_admin(conn, email="super-admin@example.com", full_name="Platform Super Admin")

        async with conn.cursor() as cur:
            await cur.execute("SELECT COUNT(*) FROM schools")
            (existing,) = await cur.fetchone()
        if existing > 0:
            print(f"{existing} school(s) already present, skipping school seed.")
            pool.close()
            await pool.wait_closed()
            return

        await seed_school(
            conn,
            code="GREENWOOD",
            name="Greenwood High",
            subdomain="greenwood",
            template="classic",
            admin_email="greenwood-admin@example.com",
            teacher_email="greenwood-teacher@example.com",
            teacher_name="Ananya Rao",
            class_name="Grade 5",
            section="A",
            students=[
                ("GW-1001", "Ishaan Kapoor", "Rohit Kapoor"),
                ("GW-1002", "Diya Menon", "Sunita Menon"),
                ("GW-1003", "Aarav Joshi", "Neha Joshi"),
            ],
        )

        await seed_school(
            conn,
            code="RIVERSIDE",
            name="Riverside Academy",
            subdomain="riverside",
            template="modern",
            admin_email="riverside-admin@example.com",
            teacher_email="riverside-teacher@example.com",
            teacher_name="Vikram Shah",
            class_name="Grade 5",
            section="A",
            students=[
                ("RS-1001", "Kavya Pillai", "Suresh Pillai"),
                ("RS-1002", "Advait Nair", "Lakshmi Nair"),
            ],
        )

    print("Seeded Greenwood High and Riverside Academy.")
    print("Logins (dev only): greenwood-admin@example.com / Admin@12345, greenwood-teacher@example.com / Teacher@12345")
    pool.close()
    await pool.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
