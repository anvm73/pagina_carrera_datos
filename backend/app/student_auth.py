from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import datetime, timezone
from typing import Any

try:
    from app import content_store
except ModuleNotFoundError:
    import content_store


STUDENT_TOKEN_SECRET = os.getenv(
    "STUDENT_TOKEN_SECRET",
    "ce-iccd-student-secret-change-me",
)
STUDENT_TOKEN_TTL_S = int(os.getenv("STUDENT_TOKEN_TTL_S", "2592000"))
PASSWORD_HASH_ITERATIONS = int(os.getenv("STUDENT_PASSWORD_ITERATIONS", "260000"))


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _encode_secret(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def _decode_secret(value: str) -> bytes:
    return base64.b64decode(value.encode("ascii"))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_HASH_ITERATIONS,
    )
    return f"{PASSWORD_HASH_ITERATIONS}${_encode_secret(salt)}${_encode_secret(digest)}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        raw_iterations, raw_salt, raw_digest = stored_hash.split("$", 2)
        iterations = int(raw_iterations)
        salt = _decode_secret(raw_salt)
        expected = _decode_secret(raw_digest)
    except Exception:
        return False

    candidate = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(candidate, expected)


def _load_data() -> dict[str, Any]:
    return content_store.load_student_accounts()


def _save_data(data: dict[str, Any]) -> None:
    content_store.save_student_accounts(data)


def get_user(email: str) -> dict[str, Any] | None:
    email_clean = email.strip().lower()
    data = _load_data()
    for item in data.get("items", []):
        if str(item.get("email", "")).strip().lower() == email_clean:
            return item
    return None


def create_user(name: str, email: str, password: str) -> dict[str, str]:
    name_clean = name.strip()
    email_clean = email.strip().lower()
    password_clean = password.strip()

    if len(name_clean) < 3:
        raise ValueError("Ingresa tu nombre completo")
    if len(password_clean) < 8:
        raise ValueError("La clave debe tener al menos 8 caracteres")
    if get_user(email_clean):
        raise ValueError("Ya existe una cuenta registrada con este correo")

    data = _load_data()
    user = {
        "id": content_store.unique_slug(email_clean, {item.get("id", "") for item in data.get("items", [])}),
        "name": name_clean,
        "email": email_clean,
        "password_hash": hash_password(password_clean),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    data.setdefault("items", []).append(user)
    _save_data(data)
    return {
        "name": user["name"],
        "email": user["email"],
    }


def verify_credentials(email: str, password: str) -> dict[str, str] | None:
    user = get_user(email)
    if not user:
        return None
    if not verify_password(password, str(user.get("password_hash", ""))):
        return None
    return {
        "name": str(user.get("name", "")).strip(),
        "email": str(user.get("email", "")).strip().lower(),
    }


def create_token(email: str, name: str) -> str:
    payload = {
        "sub": email.strip().lower(),
        "name": name.strip(),
        "role": "student",
        "exp": int(time.time()) + STUDENT_TOKEN_TTL_S,
        "nonce": secrets.token_urlsafe(12),
    }
    body = _b64url_encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signature = _b64url_encode(
        hmac.new(
            STUDENT_TOKEN_SECRET.encode("utf-8"),
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
            STUDENT_TOKEN_SECRET.encode("utf-8"),
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

    if payload.get("role") != "student":
        return None
    if int(payload.get("exp", 0)) < int(time.time()):
        return None
    user = get_user(str(payload.get("sub", "")))
    if not user:
        return None
    payload["name"] = str(user.get("name", "")).strip()
    payload["sub"] = str(user.get("email", "")).strip().lower()
    return payload
