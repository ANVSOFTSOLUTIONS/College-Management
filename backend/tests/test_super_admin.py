from tests.factories import auth_headers, create_school, create_user, login


async def _super_admin_headers(db, client, *, email="super-admin-test@example.com"):
    await create_user(school_id=None, email=email, password="Secret123!", role="super_admin", full_name="Super Admin")
    response = await login(client, email, "Secret123!")
    return auth_headers(response.json()["access_token"])


async def test_super_admin_can_create_school_and_admin_can_log_in(db, client):
    headers = await _super_admin_headers(db, client)

    response = await client.post(
        "/api/v1/super-admin/schools",
        headers=headers,
        json={
            "name": "New School",
            "code": "newschool",
            "admin_email": "newschool-admin@example.com",
            "admin_full_name": "New School Admin",
            "admin_password": "Secret123!",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["school"]["code"] == "NEWSCHOOL"
    assert body["school"]["subdomain"] == "newschool"
    assert body["school"]["billing_status"] == "trial"
    assert body["school"]["monthly_fee"] == 600
    assert set(body["school"]["enabled_modules"]) >= {"dashboard", "fees", "homework", "certificates"}
    assert body["admin_email"] == "newschool-admin@example.com"

    login_response = await login(client, "newschool-admin@example.com", "Secret123!")
    assert login_response.status_code == 200
    assert login_response.json()["user"]["role"] == "admin"


async def test_regular_admin_cannot_access_super_admin_endpoints(db, client):
    school_id = await create_school(code="NOTSUPER")
    await create_user(school_id=school_id, email="regular-admin@example.com", password="Secret123!", role="admin")
    login_response = await login(client, "regular-admin@example.com", "Secret123!")
    headers = auth_headers(login_response.json()["access_token"])

    response = await client.get("/api/v1/super-admin/schools", headers=headers)

    assert response.status_code == 403


async def test_duplicate_school_code_rejected(db, client):
    headers = await _super_admin_headers(db, client, email="super-dup@example.com")

    payload = {
        "name": "Dup School",
        "code": "DUPCODE",
        "admin_email": "dup-admin-1@example.com",
        "admin_full_name": "Dup Admin",
        "admin_password": "Secret123!",
    }
    first = await client.post("/api/v1/super-admin/schools", headers=headers, json=payload)
    assert first.status_code == 200

    payload["admin_email"] = "dup-admin-2@example.com"
    second = await client.post("/api/v1/super-admin/schools", headers=headers, json=payload)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "school_already_exists"


async def test_list_schools_returns_created_schools(db, client):
    headers = await _super_admin_headers(db, client, email="super-list@example.com")
    await client.post(
        "/api/v1/super-admin/schools",
        headers=headers,
        json={
            "name": "Listed School",
            "code": "LISTED",
            "admin_email": "listed-admin@example.com",
            "admin_full_name": "Listed Admin",
            "admin_password": "Secret123!",
        },
    )

    response = await client.get("/api/v1/super-admin/schools", headers=headers)

    assert response.status_code == 200
    codes = [school["code"] for school in response.json()]
    assert "LISTED" in codes


async def test_super_admin_can_update_school(db, client):
    headers = await _super_admin_headers(db, client, email="super-update@example.com")
    create_response = await client.post(
        "/api/v1/super-admin/schools",
        headers=headers,
        json={
            "name": "Update School",
            "code": "UPDATEME",
            "admin_email": "updateme-admin@example.com",
            "admin_full_name": "Update Admin",
            "admin_password": "Secret123!",
        },
    )
    school_id = create_response.json()["school"]["id"]

    response = await client.patch(
        f"/api/v1/super-admin/schools/{school_id}",
        headers=headers,
        json={"template": "vibrant", "billing_status": "active", "enabled_modules": ["dashboard", "attendance"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["template"] == "vibrant"
    assert body["billing_status"] == "active"
    assert body["enabled_modules"] == ["attendance", "dashboard"]


async def test_suspended_school_blocks_login(db, client):
    headers = await _super_admin_headers(db, client, email="super-suspend@example.com")
    create_response = await client.post(
        "/api/v1/super-admin/schools",
        headers=headers,
        json={
            "name": "Suspend School",
            "code": "SUSPENDME",
            "billing_status": "active",
            "admin_email": "suspendme-admin@example.com",
            "admin_full_name": "Suspend Admin",
            "admin_password": "Secret123!",
        },
    )
    school_id = create_response.json()["school"]["id"]

    pre_suspend_login = await login(client, "suspendme-admin@example.com", "Secret123!")
    assert pre_suspend_login.status_code == 200

    await client.patch(
        f"/api/v1/super-admin/schools/{school_id}", headers=headers, json={"billing_status": "suspended"}
    )

    post_suspend_login = await login(client, "suspendme-admin@example.com", "Secret123!")
    assert post_suspend_login.status_code == 403
    assert post_suspend_login.json()["error"]["code"] == "school_suspended"


async def test_invalid_module_name_rejected(db, client):
    headers = await _super_admin_headers(db, client, email="super-badmodule@example.com")

    response = await client.post(
        "/api/v1/super-admin/schools",
        headers=headers,
        json={
            "name": "Bad Module School",
            "code": "BADMODULE",
            "enabled_modules": ["not-a-real-module"],
            "admin_email": "badmodule-admin@example.com",
            "admin_full_name": "Admin",
            "admin_password": "Secret123!",
        },
    )

    assert response.status_code == 422


async def test_public_site_resolves_by_subdomain(db, client):
    headers = await _super_admin_headers(db, client, email="super-subdomain@example.com")
    await client.post(
        "/api/v1/super-admin/schools",
        headers=headers,
        json={
            "name": "Subdomain School",
            "code": "SUBDOMAINSCHOOL",
            "subdomain": "sub-test",
            "admin_email": "subdomain-admin@example.com",
            "admin_full_name": "Admin",
            "admin_password": "Secret123!",
        },
    )

    response = await client.get("/api/v1/public/schools/sub-test/site")

    assert response.status_code == 200
    assert response.json()["name"] == "Subdomain School"
