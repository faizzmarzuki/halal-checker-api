import contextlib
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from halal_scanner.api.app import app
from halal_scanner.db import Base, get_db
import halal_scanner.auth.models  # noqa: F401


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def _override():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override
    yield TestClient(app)
    app.dependency_overrides.clear()


@contextlib.contextmanager
def patch_admin(email):
    prev = os.environ.get("HALAL_ADMIN_EMAILS")
    os.environ["HALAL_ADMIN_EMAILS"] = email
    try:
        yield
    finally:
        if prev is None:
            os.environ.pop("HALAL_ADMIN_EMAILS", None)
        else:
            os.environ["HALAL_ADMIN_EMAILS"] = prev


def _register_login(client, email, password="password1"):
    client.post("/auth/register", json={"email": email, "password": password})
    r = client.post("/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_normal_user_forbidden_no_jwt_unauthorized(client):
    assert client.get("/admin/users").status_code == 401
    headers = _register_login(client, "user@x.com")
    assert client.get("/admin/users", headers=headers).status_code == 403


def test_admin_can_list_users_and_me_shows_role(client):
    with patch_admin("admin@x.com"):
        headers = _register_login(client, "admin@x.com")
    me = client.get("/auth/me", headers=headers)
    assert me.json()["role"] == "admin"
    r = client.get("/admin/users", headers=headers)
    assert r.status_code == 200
    assert any(u["email"] == "admin@x.com" for u in r.json())


def test_audit_log_captures_auth_events(client):
    with patch_admin("admin@x.com"):
        headers = _register_login(client, "admin@x.com")
    client.post("/auth/login", json={"email": "ghost@x.com", "password": "whatever1"})
    r = client.get("/admin/audit", headers=headers)
    assert r.status_code == 200
    actions = [e["action"] for e in r.json()]
    assert "user.register" in actions
    assert "auth.login" in actions
    assert "auth.login_failed" in actions


def test_audit_log_captures_key_events(client):
    with patch_admin("admin@x.com"):
        headers = _register_login(client, "admin@x.com")
    created = client.post("/keys", json={"name": "k"}, headers=headers).json()
    client.delete(f"/keys/{created['id']}", headers=headers)
    actions = [e["action"] for e in client.get("/admin/audit", headers=headers).json()]
    assert "key.create" in actions
    assert "key.revoke" in actions
