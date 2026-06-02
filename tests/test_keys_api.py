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


def _auth_headers(client, email="a@b.com", password="password1"):
    client.post("/auth/register", json={"email": email, "password": password})
    r = client.post("/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_create_key_then_use_it_on_classify(client):
    headers = _auth_headers(client)
    r = client.post("/keys", json={"name": "laptop"}, headers=headers)
    assert r.status_code == 201
    body = r.json()
    assert body["api_key"].startswith("hsk_")
    assert body["name"] == "laptop"
    raw = body["api_key"]

    # The raw key authenticates the scanning endpoint.
    c = client.post("/classify", json={"ingredients": ["sugar"]}, headers={"X-API-Key": raw})
    assert c.status_code == 200


def test_list_keys_hides_raw_value(client):
    headers = _auth_headers(client)
    created = client.post("/keys", json={"name": "k1"}, headers=headers).json()
    r = client.get("/keys", headers=headers)
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["prefix"] == created["prefix"]
    assert "api_key" not in items[0]  # raw never returned by list


def test_delete_key_revokes_it(client):
    headers = _auth_headers(client)
    created = client.post("/keys", json={}, headers=headers).json()
    raw, key_id = created["api_key"], created["id"]
    assert client.delete(f"/keys/{key_id}", headers=headers).status_code == 204
    # Revoked key no longer authenticates.
    c = client.post("/classify", json={"ingredients": ["sugar"]}, headers={"X-API-Key": raw})
    assert c.status_code == 401


def test_classify_requires_a_key(client):
    # No key at all -> 401.
    assert client.post("/classify", json={"ingredients": ["sugar"]}).status_code == 401
    # Bogus key -> 401.
    bad = client.post("/classify", json={"ingredients": ["sugar"]}, headers={"X-API-Key": "hsk_bogus"})
    assert bad.status_code == 401


def test_keys_endpoint_requires_jwt(client):
    assert client.get("/keys").status_code == 401
    assert client.post("/keys", json={}).status_code == 401


def test_user_cannot_delete_another_users_key(client):
    h1 = _auth_headers(client, "u1@b.com")
    h2 = _auth_headers(client, "u2@b.com")
    key_id = client.post("/keys", json={}, headers=h1).json()["id"]
    # u2 tries to delete u1's key -> 404 (not 403, no existence leak).
    assert client.delete(f"/keys/{key_id}", headers=h2).status_code == 404
