import os

import jwt
import pytest

os.environ.setdefault("HALAL_JWT_SECRET", "test-secret")

from halal_scanner.auth import tokens


def test_access_token_round_trips():
    tok = tokens.create_access_token(42)
    payload = tokens.decode_token(tok, "access")
    assert payload["sub"] == "42"
    assert payload["type"] == "access"


def test_refresh_token_round_trips_and_has_jti():
    tok = tokens.create_refresh_token(7)
    payload = tokens.decode_token(tok, "refresh")
    assert payload["sub"] == "7"
    assert payload["type"] == "refresh"
    assert payload["jti"]


def test_wrong_type_is_rejected():
    access = tokens.create_access_token(1)
    with pytest.raises(jwt.InvalidTokenError):
        tokens.decode_token(access, "refresh")


def test_tampered_token_is_rejected():
    tok = tokens.create_access_token(1)
    with pytest.raises(jwt.InvalidTokenError):
        tokens.decode_token(tok + "x", "access")


def test_expired_token_is_rejected():
    tok = tokens.create_access_token(1, ttl_seconds=-1)
    with pytest.raises(jwt.InvalidTokenError):
        tokens.decode_token(tok, "access")


def test_hash_token_is_deterministic_sha256():
    assert tokens.hash_token("abc") == tokens.hash_token("abc")
    assert tokens.hash_token("abc") != tokens.hash_token("abd")
    assert len(tokens.hash_token("abc")) == 64
