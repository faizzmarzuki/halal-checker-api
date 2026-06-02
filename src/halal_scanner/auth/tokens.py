"""JWT access/refresh token creation and decoding (HS256)."""
from __future__ import annotations

import hashlib
import os
import uuid
from datetime import datetime, timedelta, timezone

import jwt

ALGORITHM = "HS256"
_ACCESS_DEFAULT = 900       # 15 minutes
_REFRESH_DEFAULT = 604800   # 7 days


def _secret() -> str:
    secret = os.environ.get("HALAL_JWT_SECRET")
    if not secret:
        raise RuntimeError("HALAL_JWT_SECRET must be set.")
    return secret


def _ttl(env_name: str, default: int) -> int:
    return int(os.environ.get(env_name, str(default)) or str(default))


def _encode(user_id: int, token_type: str, ttl_seconds: int, extra: dict) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "iat": now,
        "exp": now + timedelta(seconds=ttl_seconds),
        **extra,
    }
    return jwt.encode(payload, _secret(), algorithm=ALGORITHM)


def create_access_token(user_id: int, ttl_seconds: int | None = None) -> str:
    ttl = _ttl("HALAL_ACCESS_TTL", _ACCESS_DEFAULT) if ttl_seconds is None else ttl_seconds
    return _encode(user_id, "access", ttl, {})


def create_refresh_token(user_id: int, ttl_seconds: int | None = None) -> str:
    ttl = _ttl("HALAL_REFRESH_TTL", _REFRESH_DEFAULT) if ttl_seconds is None else ttl_seconds
    return _encode(user_id, "refresh", ttl, {"jti": uuid.uuid4().hex})


def decode_token(token: str, expected_type: str) -> dict:
    """Decode and validate a token; raise jwt.InvalidTokenError on any problem."""
    payload = jwt.decode(token, _secret(), algorithms=[ALGORITHM])
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("Unexpected token type.")
    return payload


def hash_token(token: str) -> str:
    """SHA-256 hex digest — what we store, so a raw token never hits the DB."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
