"""Argon2 password hashing."""
from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error

_ph = PasswordHasher()


def hash_password(plaintext: str) -> str:
    """Return an argon2 hash (includes a random salt)."""
    return _ph.hash(plaintext)


def verify_password(password_hash: str, plaintext: str) -> bool:
    """Return True iff plaintext matches the hash; never raises."""
    try:
        return _ph.verify(password_hash, plaintext)
    except Argon2Error:
        return False
