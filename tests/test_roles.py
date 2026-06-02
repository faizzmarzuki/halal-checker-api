import os

os.environ.setdefault("HALAL_JWT_SECRET", "test-secret")

from unittest.mock import patch

import pytest
from fastapi import HTTPException

from halal_scanner.auth import roles
from halal_scanner.auth.models import User


def test_resolve_role_admin_for_listed_email():
    with patch.dict(os.environ, {"HALAL_ADMIN_EMAILS": "boss@x.com, admin@x.com"}):
        assert roles.resolve_role("admin@x.com") == "admin"
        assert roles.resolve_role("boss@x.com") == "admin"
        assert roles.resolve_role("nobody@x.com") == "user"


def test_resolve_role_user_when_env_unset():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("HALAL_ADMIN_EMAILS", None)
        assert roles.resolve_role("a@b.com") == "user"


def test_is_admin_reflects_role():
    assert roles.is_admin(User(email="a", password_hash="x", role="admin")) is True
    assert roles.is_admin(User(email="a", password_hash="x", role="user")) is False


def test_require_admin_allows_admin_blocks_user():
    admin = User(email="a", password_hash="x", role="admin")
    normal = User(email="b", password_hash="x", role="user")
    assert roles.require_admin(user=admin) is admin
    with pytest.raises(HTTPException) as exc:
        roles.require_admin(user=normal)
    assert exc.value.status_code == 403
