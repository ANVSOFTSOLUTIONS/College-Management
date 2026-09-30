from tests.factories import create_school, create_user

API = "/api/v1"
PASSWORD = "Secret123!"


async def _login(client, email, portal=None):
    body = {"email": email, "password": PASSWORD}
    if portal:
        body["portal"] = portal
    return await client.post(f"{API}/auth/login", json=body)


async def test_super_admin_signs_in_only_on_the_platform_page(db, client):
    await create_user(school_id=None, email="root-portal@example.com", password=PASSWORD, role="super_admin")
    school_id = await create_school(code="PRT1")
    await create_user(school_id=school_id, email="prt1-admin@example.com", password=PASSWORD, role="admin")

    # The school page answers exactly like a wrong password.
    refused = await _login(client, "root-portal@example.com", "school")
    assert refused.status_code == 401 and refused.json()["error"]["code"] == "invalid_credentials"
    assert (await _login(client, "root-portal@example.com", "platform")).json()["user"]["role"] == "super_admin"

    # School staff can't use the platform page.
    assert (await _login(client, "prt1-admin@example.com", "platform")).status_code == 401
    assert (await _login(client, "prt1-admin@example.com", "school")).status_code == 200

    # Older clients that don't say which page still work.
    assert (await _login(client, "root-portal@example.com")).status_code == 200
    assert (await _login(client, "prt1-admin@example.com", "elsewhere")).status_code == 422
