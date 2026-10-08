"""Password hashing and session tokens, using only the standard library."""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from . import config
from .db import db

_SCRYPT = dict(n=2**14, r=8, p=1, dklen=32)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt_hex, digest_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), **_SCRYPT)
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(days=config.SESSION_DAYS)
    with db() as conn:
        conn.execute("DELETE FROM sessions WHERE expires_at < ?", (datetime.now(timezone.utc).isoformat(),))
        conn.execute(
            "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
            (_hash_token(token), user_id, expires.isoformat()),
        )
    return token


def user_for_token(token: str | None):
    if not token:
        return None
    with db() as conn:
        row = conn.execute(
            "SELECT u.id, u.email, u.name, u.created_at, s.expires_at FROM sessions s "
            "JOIN users u ON u.id = s.user_id WHERE s.token_hash = ?",
            (_hash_token(token),),
        ).fetchone()
    if row is None or datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
        return None
    return {"id": row["id"], "email": row["email"], "name": row["name"], "created_at": row["created_at"]}


def delete_session(token: str | None) -> None:
    if token:
        with db() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_hash_token(token),))
