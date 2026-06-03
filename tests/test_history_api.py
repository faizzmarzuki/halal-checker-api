import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from halal_scanner.api.app import app
from halal_scanner.db import Base, get_db
import halal_scanner.auth.models  # noqa: F401
from halal_scanner.auth.models import User


@pytest.fixture()
def ctx():
    """Yield (client, SessionFactory) backed by one in-memory SQLite DB."""
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
    yield TestClient(app), TestingSession
    app.dependency_overrides.clear()


def _auth_headers(client, email="a@b.com", password="password1"):
    client.post("/auth/register", json={"email": email, "password": password})
    r = client.post("/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _make_key(client, headers):
    return client.post("/keys", json={"name": "k"}, headers=headers).json()["api_key"]


def test_valid_key_authenticates_and_bad_key_401(ctx):
    client, _ = ctx
    headers = _auth_headers(client)
    raw = _make_key(client, headers)
    assert client.post("/classify", json={"ingredients": ["sugar"]},
                       headers={"X-API-Key": raw}).status_code == 200
    assert client.post("/classify", json={"ingredients": ["sugar"]},
                       headers={"X-API-Key": "hsk_bogus"}).status_code == 401
    assert client.post("/classify", json={"ingredients": ["sugar"]}).status_code == 401


from halal_scanner import history


def _seed(SessionFactory, email, items):
    """Insert ScanHistory rows for the user with this email; return user id."""
    db = SessionFactory()
    try:
        user = db.scalar(select(User).where(User.email == email))
        for scan_type, summary, verdict in items:
            history.record(db, user.id, scan_type, summary, verdict)
        return user.id
    finally:
        db.close()


def test_get_history_newest_first(ctx):
    client, Session = ctx
    headers = _auth_headers(client)
    _seed(Session, "a@b.com", [
        ("classify", "first", "halal"),
        ("barcode", "second", "haram"),
    ])
    r = client.get("/history", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert [x["summary"] for x in body] == ["second", "first"]
    assert body[0]["scan_type"] == "barcode" and body[0]["verdict"] == "haram"


def test_get_history_paginates_and_validates(ctx):
    client, Session = ctx
    headers = _auth_headers(client)
    _seed(Session, "a@b.com", [("classify", str(i), "halal") for i in range(5)])
    r = client.get("/history?limit=2&offset=1", headers=headers)
    assert [x["summary"] for x in r.json()] == ["3", "2"]
    assert client.get("/history?limit=0", headers=headers).status_code == 422
    assert client.get("/history?limit=999", headers=headers).status_code == 422


def test_history_requires_jwt(ctx):
    client, _ = ctx
    assert client.get("/history").status_code == 401


def test_delete_one_history_item(ctx):
    client, Session = ctx
    headers = _auth_headers(client)
    _seed(Session, "a@b.com", [("classify", "x", "halal")])
    item_id = client.get("/history", headers=headers).json()[0]["id"]
    assert client.delete(f"/history/{item_id}", headers=headers).status_code == 204
    assert client.get("/history", headers=headers).json() == []


def test_cannot_delete_another_users_item(ctx):
    client, Session = ctx
    h1 = _auth_headers(client, "u1@b.com")
    h2 = _auth_headers(client, "u2@b.com")
    _seed(Session, "u1@b.com", [("classify", "x", "halal")])
    item_id = client.get("/history", headers=h1).json()[0]["id"]
    # u2 tries to delete u1's row -> 404 (no existence leak).
    assert client.delete(f"/history/{item_id}", headers=h2).status_code == 404


def test_clear_all_history(ctx):
    client, Session = ctx
    headers = _auth_headers(client)
    _seed(Session, "a@b.com", [("classify", str(i), "halal") for i in range(3)])
    assert client.delete("/history", headers=headers).status_code == 204
    assert client.get("/history", headers=headers).json() == []
