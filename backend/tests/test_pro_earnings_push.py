import asyncio
import base64
import json
import os
from datetime import timedelta

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core import webpush
from app.db.helpers import execute, fetch_all
from app.modules.alerts.service import today_ist
from app.modules.push import service as push
from tests.factories import auth_headers, create_school, create_user, login

PASSWORD = "Secret123!"
API = "/api/v1"


async def _super(client, email="root@example.com"):
    await create_user(school_id=None, email=email, password=PASSWORD, role="super_admin")
    return auth_headers((await login(client, email, PASSWORD)).json()["access_token"])


async def _admin(client, code):
    school_id = await create_school(code=code)
    await execute("UPDATE schools SET template = 'classic' WHERE id = %s", (school_id,))
    await create_user(school_id=school_id, email=f"{code}-admin@example.com".lower(), password=PASSWORD, role="admin")
    return school_id, auth_headers((await login(client, f"{code}-admin@example.com".lower(), PASSWORD)).json()["access_token"])


# --- Pro templates ------------------------------------------------------------------------


async def test_pro_templates_need_the_super_admin(db, client):
    school_id, admin = await _admin(client, "PRO1")
    site = (await client.get(f"{API}/school-site", headers=admin)).json()
    assert site["pro_templates"] is False

    assert (await client.put(f"{API}/school-site/template", json={"template": "modern"}, headers=admin)).status_code == 200  # free
    locked = await client.put(f"{API}/school-site/template", json={"template": "neon"}, headers=admin)
    assert locked.status_code == 403 and locked.json()["error"]["code"] == "pro_required"

    root = await _super(client)
    updated = await client.patch(f"{API}/super-admin/schools/{school_id}", json={"pro_templates": True}, headers=root)
    assert updated.json()["pro_templates"] is True
    assert (await client.put(f"{API}/school-site/template", json={"template": "neon"}, headers=admin)).json()["template"] == "neon"

    # Switching Pro off later lets the school keep the Pro template it already uses.
    await client.patch(f"{API}/super-admin/schools/{school_id}", json={"pro_templates": False}, headers=root)
    assert (await client.put(f"{API}/school-site/template", json={"template": "neon"}, headers=admin)).status_code == 200
    assert (await client.put(f"{API}/school-site/template", json={"template": "royal"}, headers=admin)).status_code == 403


async def test_new_schools_get_a_free_template(db, client):
    root = await _super(client)
    for code in ("FREEA", "FREEB", "FREEC", "FREED"):
        body = {"name": code, "code": code, "admin_email": f"{code.lower()}@example.com", "admin_full_name": "A", "admin_password": PASSWORD}
        school = (await client.post(f"{API}/super-admin/schools", json=body, headers=root)).json()["school"]
        assert school["template"] in ("classic", "modern") and school["pro_templates"] is False


# --- Website customisation --------------------------------------------------------------------


async def test_admin_customises_the_template(db, client):
    _, admin = await _admin(client, "CUS1")
    body = {"tagline": "  Learning with joy since 1998  ", "primary_color": "#0f766e", "accent_color": "#F59E0B", "hidden_sections": ["gallery", "notices"]}
    site = (await client.put(f"{API}/school-site/customize", json=body, headers=admin)).json()
    assert (site["tagline"], site["primary_color"], site["accent_color"], site["hidden_sections"]) == (
        "Learning with joy since 1998", "#0f766e", "#F59E0B", ["gallery", "notices"],
    )
    public = (await client.get(f"{API}/public/schools/CUS1/site")).json()
    assert public["primary_color"] == "#0f766e" and public["hidden_sections"] == ["gallery", "notices"]

    assert (await client.put(f"{API}/school-site/customize", json={"primary_color": "red"}, headers=admin)).status_code == 422
    assert (await client.put(f"{API}/school-site/customize", json={"hidden_sections": ["contact"]}, headers=admin)).status_code == 422
    reset = (await client.put(f"{API}/school-site/customize", json={}, headers=admin)).json()
    assert (reset["primary_color"], reset["hidden_sections"]) == (None, [])


# --- Platform analytics and earnings ----------------------------------------------------------


async def test_analytics_and_payments(db, client):
    root = await _super(client)
    school_a, admin_a = await _admin(client, "EAR1")
    school_b, _ = await _admin(client, "EAR2")
    await execute("UPDATE schools SET billing_status = 'active', monthly_fee = 1500 WHERE id = %s", (school_a,))
    await execute("UPDATE schools SET billing_status = 'trial', pro_templates = 1 WHERE id = %s", (school_b,))
    body = {"name": "Grade 1", "section": "A", "academic_year": "2026"}
    teacher = (await client.post(f"{API}/teachers", json={"email": "ear1-t@example.com", "full_name": "T", "password": PASSWORD}, headers=admin_a)).json()
    grade = (await client.post(f"{API}/classes", json={**body, "class_teacher_id": teacher["id"]}, headers=admin_a)).json()
    for n in range(3):
        await client.post(f"{API}/students", json={"admission_number": f"S{n}", "full_name": f"Student {n}", "class_id": grade["id"]}, headers=admin_a)

    today = today_ist()
    pay = lambda **kw: client.post(f"{API}/super-admin/payments", json={"school_id": school_a, "amount": "1500", "paid_on": today.isoformat(), **kw}, headers=root)  # noqa: E731
    first = await pay()
    assert first.status_code == 201 and first.json()["purpose_label"] == "Monthly subscription"
    await pay(amount="5000", purpose="pro_templates", method="upi", note="All templates")
    last_month = (today.replace(day=1) - timedelta(days=1)).isoformat()
    await pay(amount="1500", paid_on=last_month)
    assert (await pay(paid_on=(today + timedelta(days=1)).isoformat())).status_code == 400
    assert (await pay(amount="0")).status_code == 422

    data = (await client.get(f"{API}/super-admin/analytics", headers=root)).json()
    assert (data["schools_total"], data["schools_active"], data["schools_trial"], data["pro_schools"]) == (2, 1, 1, 1)
    assert (data["students_total"], data["teachers_total"], data["monthly_recurring"]) == (3, 1, 1500.0)
    assert (data["earned_total"], data["earned_this_month"]) == (8000.0, 6500.0)
    assert len(data["by_month"]) == 12 and data["by_month"][-1]["amount"] == 6500.0 and data["by_month"][-2]["amount"] == 1500.0
    assert data["by_purpose"]["pro_templates"] == 5000.0
    a = next(s for s in data["schools"] if s["code"] == "EAR1")
    assert (a["students"], a["paid_total"], a["last_paid_on"]) == (3, 8000.0, today.isoformat())

    payments = (await client.get(f"{API}/super-admin/payments", params={"school_id": school_a}, headers=root)).json()
    assert len(payments) == 3
    assert (await client.delete(f"{API}/super-admin/payments/{first.json()['id']}", headers=root)).status_code == 204
    assert (await client.get(f"{API}/super-admin/analytics", headers=root)).json()["earned_total"] == 6500.0
    assert (await client.get(f"{API}/super-admin/analytics", headers=admin_a)).status_code == 403


# --- Web Push -------------------------------------------------------------------------------


def _browser_keys():
    """What a browser holds: a P-256 key pair and a 16-byte auth secret."""
    private = ec.generate_private_key(ec.SECP256R1())
    public = private.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return private, webpush.b64url(public), webpush.b64url(os.urandom(16))


def _browser_decrypt(body: bytes, private: ec.EllipticCurvePrivateKey, p256dh: str, auth: str) -> bytes:
    """RFC 8291 decryption, as a phone would do it."""
    salt, record_size, id_len = body[:16], int.from_bytes(body[16:20], "big"), body[20]
    sender_public = body[21 : 21 + id_len]
    assert record_size == 4096 and id_len == 65
    shared = private.exchange(ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), sender_public))
    ikm = webpush._hkdf(webpush.b64url_decode(auth), shared, b"WebPush: info\x00" + webpush.b64url_decode(p256dh) + sender_public, 32)
    cek = webpush._hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = webpush._hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)
    plain = AESGCM(cek).decrypt(nonce, body[21 + id_len :], None)
    assert plain.endswith(b"\x02")
    return plain[:-1]


def test_webpush_encryption_round_trip():
    private, p256dh, auth = _browser_keys()
    body = webpush.encrypt(b'{"title":"Homework: Maths"}', p256dh, auth)
    assert _browser_decrypt(body, private, p256dh, auth) == b'{"title":"Homework: Maths"}'


def test_vapid_header_is_a_valid_es256_token():
    public, private = webpush.generate_vapid_keys()
    header = webpush.vapid_header("https://fcm.googleapis.com/fcm/send/abc", public, private, "mailto:a@example.com")
    token, key = header.removeprefix("vapid t=").split(", k=")
    assert key == public
    head, claims, signature = token.split(".")
    decoded = json.loads(base64.urlsafe_b64decode(claims + "=="))
    assert decoded["aud"] == "https://fcm.googleapis.com" and decoded["sub"] == "mailto:a@example.com"
    raw = webpush.b64url_decode(signature)
    der = encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big"))
    verifier = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), webpush.b64url_decode(public))
    verifier.verify(der, f"{head}.{claims}".encode(), ec.ECDSA(hashes.SHA256()))  # raises if forged


async def test_notifications_are_pushed_to_subscribed_devices(db, client, monkeypatch):
    push._keys = None  # tests clear platform_settings, so make a fresh key pair
    _, admin = await _admin(client, "PSH1")
    info = (await client.get(f"{API}/push/public-key", headers=admin)).json()
    assert len(webpush.b64url_decode(info["public_key"])) == 65 and info["devices"] == 0

    _, p256dh, auth = _browser_keys()
    sub = {"endpoint": "https://push.example.com/device-1", "keys": {"p256dh": p256dh, "auth": auth}}
    assert (await client.post(f"{API}/push/subscribe", json=sub, headers=admin)).status_code == 204
    assert (await client.post(f"{API}/push/subscribe", json=sub, headers=admin)).status_code == 204  # same device: one row
    gone = {"endpoint": "https://push.example.com/device-2", "keys": {"p256dh": p256dh, "auth": auth}}
    await client.post(f"{API}/push/subscribe", json=gone, headers=admin)
    assert (await client.get(f"{API}/push/public-key", headers=admin)).json()["devices"] == 2
    assert (await client.post(f"{API}/push/subscribe", json={**sub, "endpoint": "http://insecure.example.com/x"}, headers=admin)).status_code == 422

    sent = []

    def fake_send(endpoint, p256dh, auth, message, **_):
        if endpoint.endswith("device-2"):
            raise webpush.SubscriptionGone()
        sent.append((endpoint, message))

    monkeypatch.setattr(webpush, "send", fake_send)
    # Any bell notification also goes to the phone: here, a new admission application.
    teacher_body = {"email": "psh1-t@example.com", "full_name": "T", "password": PASSWORD}
    teacher = (await client.post(f"{API}/teachers", json=teacher_body, headers=admin)).json()
    await client.post(f"{API}/classes", json={"name": "Grade 1", "section": "A", "academic_year": "2026", "class_teacher_id": teacher["id"]}, headers=admin)
    application = {"student_name": "Asha", "class_applied": "Grade 1", "father_name": "Ravi", "father_phone": "9848022338"}
    assert (await client.post(f"{API}/public/schools/PSH1/admissions", json=application)).status_code == 201
    await asyncio.gather(*list(push._background))

    assert sent == [("https://push.example.com/device-1", {"title": "New admission application: Asha", "body": sent[0][1]["body"], "link": "admissions"})]
    remaining = await fetch_all("SELECT endpoint FROM push_subscriptions")
    assert [r["endpoint"] for r in remaining] == ["https://push.example.com/device-1"]  # the gone one was removed

    assert (await client.post(f"{API}/push/unsubscribe", json={"endpoint": sub["endpoint"]}, headers=admin)).status_code == 204
    assert (await client.get(f"{API}/push/public-key", headers=admin)).json()["devices"] == 0
