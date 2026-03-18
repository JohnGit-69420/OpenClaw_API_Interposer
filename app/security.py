from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets


KEY_PREFIX = "ocip_"


def generate_api_key() -> str:
    return f"{KEY_PREFIX}{secrets.token_urlsafe(32)}"


def hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def mask_secret(secret: str) -> str:
    if len(secret) <= 8:
        return "*" * len(secret)
    return f"{secret[:4]}{'*' * (len(secret) - 8)}{secret[-4:]}"


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    rounds = 390_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
    return f"pbkdf2_sha256${rounds}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds_s, salt_b64, digest_b64 = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        rounds = int(rounds_s)
        salt = base64.b64decode(salt_b64.encode())
        expected = base64.b64decode(digest_b64.encode())
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
        return hmac.compare_digest(expected, candidate)
    except Exception:
        return False


def validate_admin_username(username: str) -> None:
    if len(username) < 8:
        raise ValueError("Username must be at least 8 characters long.")
    if not re.fullmatch(r"[A-Za-z0-9_]+", username):
        raise ValueError("Username may only include letters, numbers, and underscores.")


def validate_strong_password(password: str, *, username: str | None = None) -> None:
    if len(password) < 14:
        raise ValueError("Password must be at least 14 characters long.")
    checks = [
        (r"[A-Z]", "one uppercase letter"),
        (r"[a-z]", "one lowercase letter"),
        (r"[0-9]", "one number"),
        (r"[^A-Za-z0-9]", "one symbol"),
    ]
    for pattern, label in checks:
        if not re.search(pattern, password):
            raise ValueError(f"Password must include at least {label}.")
    if username and username.lower() in password.lower():
        raise ValueError("Password cannot contain the username.")
