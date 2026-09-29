from tests.factories import auth_headers, create_school, create_user, login

_TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108020000009077"
    "53de0000000c4944415478da6360646000000006000158d47f900000000049454e44ae426082"
)


async def _admin_headers(db, client, *, code="SITECODE", school_name="Site School"):
    email = f"admin-{code.lower()}@example.com"
    school_id = await create_school(code=code, name=school_name)
    await create_user(school_id=school_id, email=email, password="Secret123!", role="admin")
    response = await login(client, email, "Secret123!")
    return school_id, auth_headers(response.json()["access_token"])


async def test_admin_get_creates_default_site(db, client):
    school_id, headers = await _admin_headers(db, client, code="SITEDEFAULT")

    response = await client.get("/api/v1/school-site", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["school_id"] == str(school_id)
    assert body["about"] == ""
    assert body["banners"] == []


async def test_admin_can_update_about_contact(db, client):
    _, headers = await _admin_headers(db, client, code="SITEABOUT")

    response = await client.put(
        "/api/v1/school-site/about-contact",
        headers=headers,
        json={
            "about": "A great school.",
            "contact": {"address": "1 Main St", "phone": "555-1234", "email": "hi@example.com", "map_url": ""},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["about"] == "A great school."
    assert body["contact"]["phone"] == "555-1234"


async def test_admin_can_upload_and_remove_logo_and_banner(db, client):
    _, headers = await _admin_headers(db, client, code="SITEBANNER")

    logo_response = await client.post(
        "/api/v1/school-site/logo",
        headers=headers,
        files={"file": ("logo.png", _TINY_PNG, "image/png")},
    )
    assert logo_response.status_code == 200
    assert logo_response.json()["logo_url"].startswith("/uploads/")

    banner_response = await client.post(
        "/api/v1/school-site/banners",
        headers=headers,
        files={"file": ("banner.png", _TINY_PNG, "image/png")},
        data={"caption": "Welcome"},
    )
    assert banner_response.status_code == 200
    banners = banner_response.json()["banners"]
    assert len(banners) == 1
    assert banners[0]["caption"] == "Welcome"

    banner_id = banners[0]["id"]
    delete_response = await client.delete(f"/api/v1/school-site/banners/{banner_id}", headers=headers)
    assert delete_response.status_code == 200
    assert delete_response.json()["banners"] == []


async def test_upload_rejects_non_image_file(db, client):
    _, headers = await _admin_headers(db, client, code="SITEBADFILE")

    response = await client.post(
        "/api/v1/school-site/logo",
        headers=headers,
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_file_type"


async def test_admin_can_add_and_remove_gallery_image(db, client):
    _, headers = await _admin_headers(db, client, code="SITEGALLERY")

    add_response = await client.post(
        "/api/v1/school-site/gallery",
        headers=headers,
        files={"file": ("photo.png", _TINY_PNG, "image/png")},
        data={"caption": "Sports day"},
    )
    assert add_response.status_code == 200
    gallery = add_response.json()["gallery"]
    assert len(gallery) == 1

    image_id = gallery[0]["id"]
    remove_response = await client.delete(f"/api/v1/school-site/gallery/{image_id}", headers=headers)
    assert remove_response.status_code == 200
    assert remove_response.json()["gallery"] == []


async def test_admin_can_add_and_remove_activity(db, client):
    _, headers = await _admin_headers(db, client, code="SITEACTIVITY")

    add_response = await client.post(
        "/api/v1/school-site/activities",
        headers=headers,
        json={"title": "Sports Day", "date": "2026-10-14", "description": "Track and field."},
    )
    assert add_response.status_code == 200
    activities = add_response.json()["activities"]
    assert len(activities) == 1
    assert activities[0]["title"] == "Sports Day"

    activity_id = activities[0]["id"]
    remove_response = await client.delete(f"/api/v1/school-site/activities/{activity_id}", headers=headers)
    assert remove_response.status_code == 200
    assert remove_response.json()["activities"] == []


async def test_teacher_cannot_manage_school_site(db, client):
    school_id = await create_school(code="TEACHERSITE")
    await create_user(school_id=school_id, email="site-teacher@example.com", password="Secret123!", role="teacher")
    login_response = await login(client, "site-teacher@example.com", "Secret123!")
    headers = auth_headers(login_response.json()["access_token"])

    response = await client.get("/api/v1/school-site", headers=headers)

    assert response.status_code == 403


async def test_public_site_returns_school_content_without_auth(db, client):
    school_id, headers = await _admin_headers(db, client, code="PUBLICSITE", school_name="Public Test School")
    await client.put(
        "/api/v1/school-site/about-contact",
        headers=headers,
        json={"about": "Public about text.", "contact": {"address": "", "phone": "", "email": "", "map_url": ""}},
    )

    response = await client.get("/api/v1/public/schools/publicsite/site")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Public Test School"
    assert body["about"] == "Public about text."


async def test_public_site_unknown_code_returns_404(client):
    response = await client.get("/api/v1/public/schools/does-not-exist/site")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "school_not_found"


async def test_public_site_isolated_per_school(db, client):
    _, headers_a = await _admin_headers(db, client, code="ISOA", school_name="School A")
    _, headers_b = await _admin_headers(db, client, code="ISOB", school_name="School B")

    await client.post(
        "/api/v1/school-site/activities",
        headers=headers_a,
        json={"title": "Only in A", "date": "2026-10-01", "description": ""},
    )

    response_b = await client.get("/api/v1/public/schools/isob/site")

    assert response_b.status_code == 200
    assert response_b.json()["activities"] == []
