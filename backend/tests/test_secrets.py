import pytest

from app.core import secrets
from app.core.config import get_settings
from app.core.errors import AppError
from app.db.helpers import execute, fetch_one
from tests.factories import auth_headers, create_school, create_user, login

API = "/api/v1"


def test_round_trip_and_legacy_plain_text():
    stored = secrets.encrypt_secret("cf_secret_123")
    assert stored.startswith("enc:v1:") and "cf_secret_123" not in stored
    assert secrets.decrypt_secret(stored) == "cf_secret_123"
    assert secrets.decrypt_secret("old-plain") == "old-plain"  # rows saved before encryption
    assert secrets.encrypt_secret("") == ""


def test_missing_key_refuses_to_save(monkeypatch):
    monkeypatch.setattr(get_settings(), "data_encryption_key", "")
    with pytest.raises(AppError) as error:
        secrets.encrypt_secret("x")
    assert error.value.code == "encryption_not_configured"


async def test_cashfree_secret_is_stored_encrypted(db, client):
    school_id = await create_school(code="SEC1")
    await create_user(school_id=school_id, email="sec1-admin@example.com", password="Secret123!", role="admin")
    admin = auth_headers((await login(client, "sec1-admin@example.com", "Secret123!")).json()["access_token"])

    saved = await client.put(f"{API}/fees/payment-settings", json={"key_id": "CF_APP_1", "key_secret": "shh-secret", "enabled": False}, headers=admin)
    assert saved.json()["has_secret"] is True and "shh-secret" not in saved.text
    row = await fetch_one("SELECT key_secret FROM school_payment_settings WHERE school_id = %s", (school_id,))
    assert row["key_secret"].startswith("enc:v1:") and "shh-secret" not in row["key_secret"]

    # A secret saved in plain text before this change is encrypted on the next save.
    await execute("UPDATE school_payment_settings SET key_secret = 'legacy-plain' WHERE school_id = %s", (school_id,))
    await client.put(f"{API}/fees/payment-settings", json={"key_id": "CF_APP_1", "enabled": False}, headers=admin)
    row = await fetch_one("SELECT key_secret FROM school_payment_settings WHERE school_id = %s", (school_id,))
    assert secrets.is_encrypted(row["key_secret"]) and secrets.decrypt_secret(row["key_secret"]) == "legacy-plain"
