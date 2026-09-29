"""Web Push: phone and browser notifications that arrive even when the app is closed.

Implements the two standards every browser uses, with the `cryptography` package:
- RFC 8291 (aes128gcm) to encrypt the message for one subscription, and
- RFC 8292 (VAPID) to sign the request so push services know it's from us.
"""

import base64
import json
import os
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from cryptography.hazmat.primitives import hashes, hmac, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

RECORD_SIZE = 4096
TTL_SECONDS = 24 * 3600


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def b64url_decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _hmac_sha256(key: bytes, data: bytes) -> bytes:
    h = hmac.HMAC(key, hashes.SHA256())
    h.update(data)
    return h.finalize()


def _hkdf(salt: bytes, ikm: bytes, info: bytes, length: int) -> bytes:
    """HKDF-SHA256 with a single expand block (all lengths here are <= 32)."""
    prk = _hmac_sha256(salt, ikm)
    return _hmac_sha256(prk, info + b"\x01")[:length]


def _public_bytes(key: ec.EllipticCurvePublicKey) -> bytes:
    return key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)


def generate_vapid_keys() -> tuple[str, str]:
    """(public key for browsers, private key to keep) as base64url strings."""
    private = ec.generate_private_key(ec.SECP256R1())
    raw_private = private.private_numbers().private_value.to_bytes(32, "big")
    return b64url(_public_bytes(private.public_key())), b64url(raw_private)


def _vapid_private(private_key: str) -> ec.EllipticCurvePrivateKey:
    return ec.derive_private_key(int.from_bytes(b64url_decode(private_key), "big"), ec.SECP256R1())


def encrypt(payload: bytes, p256dh: str, auth: str, *, salt: bytes | None = None, sender: ec.EllipticCurvePrivateKey | None = None) -> bytes:
    """The request body for one subscription (RFC 8291, a single aes128gcm record)."""
    ua_public = b64url_decode(p256dh)
    auth_secret = b64url_decode(auth)
    sender = sender or ec.generate_private_key(ec.SECP256R1())
    as_public = _public_bytes(sender.public_key())
    shared = sender.exchange(ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_public))

    ikm = _hkdf(auth_secret, shared, b"WebPush: info\x00" + ua_public + as_public, 32)
    salt = salt or os.urandom(16)
    cek = _hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = _hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)
    ciphertext = AESGCM(cek).encrypt(nonce, payload + b"\x02", None)  # \x02: the last (only) record
    header = salt + RECORD_SIZE.to_bytes(4, "big") + bytes([len(as_public)]) + as_public
    return header + ciphertext


def vapid_header(endpoint: str, public_key: str, private_key: str, subject: str) -> str:
    """The Authorization header: a short-lived ES256 JWT for the push service's origin."""
    parts = urlsplit(endpoint)
    claims = {"aud": f"{parts.scheme}://{parts.netloc}", "exp": int(time.time()) + 12 * 3600, "sub": subject}
    signing_input = f"{b64url(json.dumps({'typ': 'JWT', 'alg': 'ES256'}).encode())}.{b64url(json.dumps(claims).encode())}"
    der = _vapid_private(private_key).sign(signing_input.encode(), ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    signature = r.to_bytes(32, "big") + s.to_bytes(32, "big")
    return f"vapid t={signing_input}.{b64url(signature)}, k={public_key}"


class SubscriptionGone(Exception):
    """The browser unsubscribed or the subscription expired: delete it."""


def send(endpoint: str, p256dh: str, auth: str, message: dict, *, public_key: str, private_key: str, subject: str) -> None:
    """Delivers one message (blocking; call from a thread)."""
    body = encrypt(json.dumps(message).encode(), p256dh, auth)
    request = urllib.request.Request(
        endpoint,
        data=body,
        method="POST",
        headers={
            "Content-Encoding": "aes128gcm",
            "Content-Type": "application/octet-stream",
            "TTL": str(TTL_SECONDS),
            "Urgency": "normal",
            "Authorization": vapid_header(endpoint, public_key, private_key, subject),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10):
            return
    except urllib.error.HTTPError as exc:
        if exc.code in (404, 410):
            raise SubscriptionGone from exc
        raise
