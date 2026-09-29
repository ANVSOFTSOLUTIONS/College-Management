from tests.factories import auth_headers, create_school, create_user, login

PASSWORD = "Secret123!"
API = "/api/v1"


async def _admin(client, code, modules):
    school_id = await create_school(code=code, modules=modules)
    await create_user(school_id=school_id, email=f"{code}-admin@example.com".lower(), password=PASSWORD, role="admin")
    response = await login(client, f"{code}-admin@example.com".lower(), PASSWORD)
    return auth_headers(response.json()["access_token"]), response.json()["user"]


async def test_switched_off_modules_are_refused(db, client):
    headers, user = await _admin(client, "MOD1", ["dashboard", "reports"])
    assert user["enabled_modules"] == ["dashboard", "reports"]
    assert (await client.get(f"{API}/auth/me", headers=headers)).json()["user"]["enabled_modules"] == ["dashboard", "reports"]

    assert (await client.get(f"{API}/dashboard/admin", headers=headers)).status_code == 200
    for path in ("/fees/report", "/exams", "/notices", "/homework", "/timetable/periods", "/certificates", "/school-site"):
        response = await client.get(f"{API}{path}", headers=headers)
        assert response.status_code == 403, path
        assert response.json()["error"]["code"] == "module_disabled", path
    # Reports and performance are separate switches on the same router.
    assert (await client.get(f"{API}/reports/staff-attendance", params={"month": "2026-09-01"}, headers=headers)).status_code == 200
    assert (await client.get(f"{API}/reports/exam-performance/x", headers=headers)).json()["error"]["code"] == "module_disabled"
    # Core features are always on.
    assert (await client.get(f"{API}/students", headers=headers)).status_code == 200
    assert (await client.get(f"{API}/teachers", headers=headers)).status_code == 200


async def test_legacy_module_ids_are_still_accepted(db, client):
    headers, _ = await _admin(client, "MOD2", ["students", "attendance", "staff-biometric", "fees"])
    assert (await client.get(f"{API}/fees/report", headers=headers)).status_code == 200
    assert (await client.get(f"{API}/dashboard/admin", headers=headers)).status_code == 403
