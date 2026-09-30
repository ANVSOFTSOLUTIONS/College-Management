from app.db.helpers import execute
from tests.factories import create_school, create_user, login


async def test_login_success(db, client):
    school_id = await create_school(code="SCH1")
    await create_user(school_id=school_id, email="teacher1@example.com", password="Secret123!", role="teacher")

    response = await login(client, "teacher1@example.com", "Secret123!")

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["role"] == "teacher"
    assert body["user"]["school_id"] == str(school_id)
    assert body["access_token"]


async def test_login_wrong_password(db, client):
    school_id = await create_school(code="SCH2")
    await create_user(school_id=school_id, email="teacher2@example.com", password="Secret123!", role="teacher")

    response = await login(client, "teacher2@example.com", "wrong-password")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


async def test_login_unknown_email(client):
    response = await login(client, "nobody@example.com", "whatever")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


async def test_login_inactive_user_rejected(db, client):
    school_id = await create_school(code="SCH3")
    user_id = await create_user(
        school_id=school_id, email="disabled@example.com", password="Secret123!", role="teacher"
    )
    await execute("UPDATE users SET status = 'inactive' WHERE id = %s", (user_id,))

    response = await login(client, "disabled@example.com", "Secret123!")

    assert response.status_code == 401


async def test_login_rate_limited_after_repeated_failures(db, client):
    school_id = await create_school(code="SCH4")
    await create_user(school_id=school_id, email="ratelimit@example.com", password="Secret123!", role="teacher")

    responses = [await login(client, "ratelimit@example.com", "wrong") for _ in range(6)]

    assert responses[-1].status_code == 429
    assert responses[-1].json()["error"]["code"] == "too_many_attempts"


async def test_me_returns_user_and_school(db, client):
    from tests.factories import auth_headers, create_school, create_user, login

    school_id = await create_school(code="MEAPI", name="Me School")
    await create_user(school_id=school_id, email="me-admin@example.com", password="Secret123!", role="admin", full_name="Me Admin")
    token = (await login(client, "me-admin@example.com", "Secret123!")).json()["access_token"]
    body = (await client.get("/api/v1/auth/me", headers=auth_headers(token))).json()
    assert body["user"]["full_name"] == "Me Admin"
    assert body["school"] == {"name": "Me School", "code": "MEAPI"}
    assert (await client.get("/api/v1/auth/me")).status_code == 401
