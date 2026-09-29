from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import get_settings


def parent_login_id(normalized_mobile: str) -> str:
    """Parents sign in with their mobile number (normalized to 91XXXXXXXXXX)."""
    return f"parent:{normalized_mobile}"


def student_login_id(college_code: str, roll_number: str) -> str:
    """Students sign in with their college code and roll number (case doesn't matter)."""
    return f"student:{college_code.strip().lower()}:{roll_number.strip().lower()}"


def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(*, user_id: str, school_id: str | None, role: str) -> str:
    settings = get_settings()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_token_minutes)
    payload = {
        "sub": user_id,
        "school_id": school_id,
        "role": role,
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
