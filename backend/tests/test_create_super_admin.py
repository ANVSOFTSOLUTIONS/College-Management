import pytest
from pydantic import ValidationError

from scripts.create_super_admin import SuperAdminInput, create_super_admin


async def test_created_super_admin_can_log_in(db, client):
    data = SuperAdminInput(email="Owner@Example.com", full_name="Owner", password="Str0ngPass!")
    async with db.pool.acquire() as conn:
        assert await create_super_admin(conn, data) is True

    response = await client.post("/api/v1/auth/login", json={"email": "owner@example.com", "password": "Str0ngPass!"})
    assert response.status_code == 200
    assert response.json()["user"]["role"] == "super_admin"


async def test_existing_email_is_not_overwritten(db):
    first = SuperAdminInput(email="owner@example.com", full_name="Owner", password="Str0ngPass!")
    second = SuperAdminInput(email="OWNER@example.com", full_name="Someone", password="OtherPass!")
    async with db.pool.acquire() as conn:
        assert await create_super_admin(conn, first) is True
        assert await create_super_admin(conn, second) is False


def test_short_password_is_rejected():
    with pytest.raises(ValidationError):
        SuperAdminInput(email="owner@example.com", full_name="Owner", password="short")
