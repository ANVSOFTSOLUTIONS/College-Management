from app.core import rate_limit
from app.modules.super_admin.schemas import FREE_TEMPLATES, TEMPLATE_IDS, auto_template
from tests.factories import auth_headers, create_school, create_user, login

API = "/api/v1"
PASSWORD = "Secret123!"


async def _super(client):
    await create_user(school_id=None, email="sa-mkt@example.com", password=PASSWORD, role="super_admin", full_name="Super")
    return auth_headers((await login(client, "sa-mkt@example.com", PASSWORD)).json()["access_token"])


async def _school_admin(client, code):
    school_id = await create_school(code=code, name=f"{code} School")
    await create_user(school_id=school_id, email=f"{code}-admin@example.com".lower(), password=PASSWORD, role="admin")
    return auth_headers((await login(client, f"{code}-admin@example.com".lower(), PASSWORD)).json()["access_token"])


def test_ten_templates_and_auto_pick_is_stable():
    assert len(TEMPLATE_IDS) == 10 == len(set(TEMPLATE_IDS))
    assert auto_template("sunrise") == auto_template("SUNRISE")
    picked = {auto_template(f"SCHOOL{i}") for i in range(200)}
    assert picked == set(FREE_TEMPLATES)  # new schools get the free ones, both used


async def test_new_school_gets_a_template_automatically(db, client):
    headers = await _super(client)
    body = {"name": "Auto", "code": "AUTOTPL", "admin_email": "auto-admin@example.com", "admin_full_name": "A", "admin_password": PASSWORD}
    school = (await client.post(f"{API}/super-admin/schools", json=body, headers=headers)).json()["school"]
    assert school["template"] == auto_template("AUTOTPL")
    chosen = (await client.post(f"{API}/super-admin/schools", json={**body, "code": "PICKED", "admin_email": "p@example.com", "template": "neon"}, headers=headers)).json()
    assert chosen["school"]["template"] == "neon"


async def test_school_admin_switches_template_and_public_site_follows(db, client):
    admin = await _school_admin(client, "TPL1")
    switched = await client.put(f"{API}/school-site/template", json={"template": "modern"}, headers=admin)
    assert switched.status_code == 200 and switched.json()["template"] == "modern"  # free; Pro ones are in test_pro_earnings_push
    assert (await client.put(f"{API}/school-site/template", json={"template": "nope"}, headers=admin)).status_code == 422
    public = (await client.get(f"{API}/public/schools/TPL1/site")).json()
    assert (public["template"], public["name"]) == ("modern", "TPL1 School")


async def test_notices_on_the_public_site(db, client):
    admin = await _school_admin(client, "TPL2")
    site = (await client.post(f"{API}/school-site/notices", json={"title": "Admissions open for 2027", "date": "2026-10-01"}, headers=admin)).json()
    assert [n["title"] for n in site["notices"]] == ["Admissions open for 2027"]
    public = (await client.get(f"{API}/public/schools/tpl2/site")).json()
    assert public["notices"][0]["date"] == "2026-10-01"
    after = (await client.delete(f"{API}/school-site/notices/{site['notices'][0]['id']}", headers=admin)).json()
    assert after["notices"] == []


async def test_demo_requests_reach_the_super_admin(db, client):
    rate_limit._attempts.clear()
    lead = {"name": "Ramesh", "institution": "Sri Vidya School", "phone": "98480 22338", "city": "Guntur", "students": "500", "message": "Need fees module"}
    assert (await client.post(f"{API}/public/demo-requests", json=lead)).status_code == 202
    assert (await client.post(f"{API}/public/demo-requests", json={**lead, "website": "spam.example"})).status_code == 202  # honeypot
    assert (await client.post(f"{API}/public/demo-requests", json={**lead, "phone": "12"})).status_code == 422

    headers = await _super(client)
    leads = (await client.get(f"{API}/super-admin/leads", headers=headers)).json()
    assert [(l["institution"], l["status"]) for l in leads if l["name"] == "Ramesh"] == [("Sri Vidya School", "new")]
    updated = (await client.patch(f"{API}/super-admin/leads/{leads[0]['id']}", json={"status": "contacted", "notes": "Call on Monday"}, headers=headers)).json()
    assert (updated["status"], updated["notes"]) == ("contacted", "Call on Monday")

    school_admin = await _school_admin(client, "TPL3")
    assert (await client.get(f"{API}/super-admin/leads", headers=school_admin)).status_code == 403


async def test_demo_requests_are_rate_limited(db, client):
    rate_limit._attempts.clear()
    lead = {"name": "Spammer", "institution": "Spam", "phone": "9848022338"}
    codes = [(await client.post(f"{API}/public/demo-requests", json=lead)).status_code for _ in range(6)]
    assert codes == [202] * 5 + [429]
    rate_limit._attempts.clear()


async def test_platform_contact_settings(db, client):
    assert (await client.get(f"{API}/public/platform")).json() == {"whatsapp_number": "", "phone": "", "email": ""}
    headers = await _super(client)
    saved = (await client.put(f"{API}/super-admin/platform-settings", json={"whatsapp_number": "919848022338", "phone": "+91 98480 22338", "email": "Sales@Example.com"}, headers=headers)).json()
    assert saved["email"] == "sales@example.com"
    assert (await client.get(f"{API}/public/platform")).json()["whatsapp_number"] == "919848022338"
