"""Encrypting secrets stored in the database (e.g. a school's Cashfree secret key).

Values are stored as "enc:v1:<Fernet token>" using DATA_ENCRYPTION_KEY, a key
kept separate from the JWT secret so either can be rotated on its own. Values
without the prefix are older plain-text rows; they still work and are
encrypted the next time they are saved.
"""

from fastapi import status

from app.core.config import get_settings
from app.core.errors import AppError

PREFIX = "enc:v1:"


def _fernet():
    # Imported here so the API still starts if the package is missing on a server;
    # only saving or reading an encrypted secret needs it.
    from cryptography.fernet import Fernet

    key = get_settings().data_encryption_key
    if not key:
        raise AppError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "encryption_not_configured",
            "Secrets can't be saved until DATA_ENCRYPTION_KEY is set on the server.",
        )
    try:
        return Fernet(key.encode())
    except ValueError as exc:
        raise AppError(status.HTTP_503_SERVICE_UNAVAILABLE, "encryption_not_configured", "DATA_ENCRYPTION_KEY is not a valid key.") from exc


def encrypt_secret(plain: str) -> str:
    return PREFIX + _fernet().encrypt(plain.encode()).decode() if plain else ""


def decrypt_secret(stored: str | None) -> str:
    if not stored or not stored.startswith(PREFIX):
        return stored or ""
    from cryptography.fernet import InvalidToken

    try:
        return _fernet().decrypt(stored[len(PREFIX):].encode()).decode()
    except InvalidToken as exc:
        raise AppError(status.HTTP_503_SERVICE_UNAVAILABLE, "secret_unreadable", "A saved secret can't be read; enter it again.") from exc


def is_encrypted(stored: str | None) -> bool:
    return bool(stored) and stored.startswith(PREFIX)
