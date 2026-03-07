from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "ce.iccd@utem.cl").strip().lower()
ADMIN_PASSWORD_FROM_ENV = os.getenv("ADMIN_PASSWORD")
ADMIN_PASSWORD = ADMIN_PASSWORD_FROM_ENV if ADMIN_PASSWORD_FROM_ENV is not None else "carrera21049"
ADMIN_PASSWORD_IS_IMPLICIT_DEFAULT = ADMIN_PASSWORD_FROM_ENV is None
ADMIN_TOKEN_SECRET = os.getenv(
    "ADMIN_TOKEN_SECRET",
    "ce-iccd-admin-secret-change-me",
)
ADMIN_TOKEN_TTL_S = int(os.getenv("ADMIN_TOKEN_TTL_S", "86400"))


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def verify_credentials(email: str, password: str) -> bool:
    email_clean = email.strip().lower()
    return hmac.compare_digest(email_clean, ADMIN_EMAIL) and hmac.compare_digest(
        password,
        ADMIN_PASSWORD,
    )


def create_token(email: str) -> str:
    payload = {
        "sub": email.strip().lower(),
        "exp": int(time.time()) + ADMIN_TOKEN_TTL_S,
        "nonce": secrets.token_urlsafe(12),
    }
    body = _b64url_encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signature = _b64url_encode(
        hmac.new(
            ADMIN_TOKEN_SECRET.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).digest()
    )
    return f"{body}.{signature}"


def verify_token(token: str) -> dict[str, Any] | None:
    if not token or "." not in token:
        return None

    body, signature = token.split(".", 1)
    expected = _b64url_encode(
        hmac.new(
            ADMIN_TOKEN_SECRET.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).digest()
    )
    if not hmac.compare_digest(signature, expected):
        return None

    try:
        payload = json.loads(_b64url_decode(body).decode("utf-8"))
    except Exception:
        return None

    if payload.get("sub") != ADMIN_EMAIL:
        return None
    if int(payload.get("exp", 0)) < int(time.time()):
        return None
    return payload
