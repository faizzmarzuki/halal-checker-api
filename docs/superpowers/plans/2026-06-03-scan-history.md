# Scan History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record every scan against the API key's owner and let that account list and delete its scan history.

**Architecture:** A `ScanHistory` ORM model + a best-effort `history` service (record/list/delete); the scanning endpoints attribute scans via a new `current_api_key` dependency that returns the authenticated key; a JWT-protected `/history` router for retrieval and deletion.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Pydantic v2, pytest + `TestClient` with an in-memory SQLite override. Baseline on this branch: **159 passing, 2 skipped**.

---

## File Structure

- `src/halal_scanner/auth/models.py` — add the `ScanHistory` model (all ORM models live here; co-located so `Base.metadata.create_all` picks it up).
- `src/halal_scanner/history.py` (new) — service: `record`, `list_for_user`, `delete_one`, `delete_all`, `NotFound`, `_summarize`, `MAX_SUMMARY_LEN`.
- `src/halal_scanner/api/security.py` — add `current_api_key`; remove `require_api_key`.
- `src/halal_scanner/api/app.py` — swap the protect dependency; wire recording into the three scanning endpoints; register the history router.
- `src/halal_scanner/api/schemas.py` — add `ScanHistoryOut`.
- `src/halal_scanner/api/history_router.py` (new) — `GET /history`, `DELETE /history/{id}`, `DELETE /history`.
- `tests/test_history.py` (new) — service unit tests.
- `tests/test_api.py` — update the auth-bypass fixture; add recording + best-effort tests.
- `tests/test_history_api.py` (new) — router + end-to-end recording tests.

Run the full suite at any point with: `.venv/Scripts/python -m pytest -q`

---

## Task 1: ScanHistory model + history service

**Files:**
- Modify: `src/halal_scanner/auth/models.py`
- Create: `src/halal_scanner/history.py`
- Test: `tests/test_history.py`

- [ ] **Step 1: Write the failing service tests**

Create `tests/test_history.py`:

```python
import os

os.environ.setdefault("HALAL_JWT_SECRET", "test-secret")

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from halal_scanner.db import Base
import halal_scanner.auth.models  # noqa: F401
from halal_scanner.auth.models import ScanHistory, User
from halal_scanner import history


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _user(db, email):
    u = User(email=email, password_hash="x")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def test_record_inserts_row(db):
    u = _user(db, "a@b.com")
    history.record(db, u.id, "classify", "sugar, lard", "haram")
    rows = db.scalars(select(ScanHistory)).all()
    assert len(rows) == 1
    assert rows[0].user_id == u.id
    assert rows[0].scan_type == "classify"
    assert rows[0].summary == "sugar, lard"
    assert rows[0].verdict == "haram"


def test_record_truncates_summary(db):
    u = _user(db, "a@b.com")
    history.record(db, u.id, "image", "x" * 500, "halal")
    row = db.scalars(select(ScanHistory)).one()
    assert len(row.summary) == history.MAX_SUMMARY_LEN


def test_list_for_user_is_newest_first_and_scoped(db):
    u1 = _user(db, "u1@b.com")
    u2 = _user(db, "u2@b.com")
    for v in ("halal", "haram", "shubhah"):
        history.record(db, u1.id, "classify", v, v)
    history.record(db, u2.id, "classify", "other", "halal")
    rows = history.list_for_user(db, u1)
    assert [r.summary for r in rows] == ["shubhah", "haram", "halal"]  # newest first
    assert all(r.user_id == u1.id for r in rows)  # never another user's rows


def test_list_for_user_paginates(db):
    u = _user(db, "a@b.com")
    for i in range(5):
        history.record(db, u.id, "classify", str(i), "halal")
    page = history.list_for_user(db, u, limit=2, offset=1)
    assert [r.summary for r in page] == ["3", "2"]


def test_delete_one_removes_own_row(db):
    u = _user(db, "a@b.com")
    history.record(db, u.id, "classify", "sugar", "halal")
    row_id = db.scalars(select(ScanHistory)).one().id
    history.delete_one(db, u, row_id)
    assert db.scalars(select(ScanHistory)).all() == []


def test_delete_one_other_user_raises_notfound(db):
    u1 = _user(db, "u1@b.com")
    u2 = _user(db, "u2@b.com")
    history.record(db, u1.id, "classify", "sugar", "halal")
    row_id = db.scalars(select(ScanHistory)).one().id
    with pytest.raises(history.NotFound):
        history.delete_one(db, u2, row_id)
    with pytest.raises(history.NotFound):
        history.delete_one(db, u1, 9999)  # missing


def test_delete_all_scopes_to_user(db):
    u1 = _user(db, "u1@b.com")
    u2 = _user(db, "u2@b.com")
    for _ in range(3):
        history.record(db, u1.id, "classify", "x", "halal")
    history.record(db, u2.id, "classify", "y", "halal")
    n = history.delete_all(db, u1)
    assert n == 3
    remaining = db.scalars(select(ScanHistory)).all()
    assert len(remaining) == 1 and remaining[0].user_id == u2.id
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_history.py -q`
Expected: FAIL — `ImportError` / `cannot import name 'ScanHistory'` (model and service do not exist yet).

- [ ] **Step 3: Add the model**

In `src/halal_scanner/auth/models.py`, append after the `AuditLog` class (the imports `datetime`, `ForeignKey`, `String`, `DateTime`, `Mapped`, `mapped_column`, and `_utcnow` already exist in this file):

```python
class ScanHistory(Base):
    """One recorded scan, owned by the user whose API key made it (product data)."""
    __tablename__ = "scan_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    scan_type: Mapped[str] = mapped_column(String)          # classify | barcode | image
    summary: Mapped[str] = mapped_column(String, default="")
    verdict: Mapped[str] = mapped_column(String)            # halal | haram | shubhah
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )
```

- [ ] **Step 4: Add the service**

Create `src/halal_scanner/history.py`:

```python
"""Per-account scan history: best-effort recording, plus listing and deletion."""
from __future__ import annotations

import logging

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .auth.models import ScanHistory, User

logger = logging.getLogger(__name__)

MAX_SUMMARY_LEN = 200


class NotFound(Exception):
    """Raised when deleting a scan that is missing or not owned by the user."""


def _summarize(text: str) -> str:
    """Trim and cap the human-readable summary of a scan's input."""
    return text.strip()[:MAX_SUMMARY_LEN]


def record(db: Session, user_id: int, scan_type: str, summary: str, verdict: str) -> None:
    """Append one scan-history row and commit. Best-effort: a failure here must
    never break the scan that triggered it, so errors are swallowed."""
    try:
        db.add(
            ScanHistory(
                user_id=user_id,
                scan_type=scan_type,
                summary=_summarize(summary),
                verdict=verdict,
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to record scan history for user %s", user_id)


def list_for_user(
    db: Session, user: User, limit: int = 50, offset: int = 0
) -> list[ScanHistory]:
    """Return the user's scans, newest first, paginated."""
    return list(
        db.scalars(
            select(ScanHistory)
            .where(ScanHistory.user_id == user.id)
            .order_by(ScanHistory.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )


def delete_one(db: Session, user: User, scan_id: int) -> None:
    """Delete one of the user's own scans, or raise NotFound."""
    row = db.scalar(
        select(ScanHistory).where(
            ScanHistory.id == scan_id, ScanHistory.user_id == user.id
        )
    )
    if row is None:
        raise NotFound()
    db.delete(row)
    db.commit()


def delete_all(db: Session, user: User) -> int:
    """Delete all of the user's scans; return how many rows were removed."""
    result = db.execute(delete(ScanHistory).where(ScanHistory.user_id == user.id))
    db.commit()
    return result.rowcount
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_history.py -q`
Expected: PASS (all service tests green).

- [ ] **Step 6: Commit**

```bash
git add src/halal_scanner/auth/models.py src/halal_scanner/history.py tests/test_history.py
git commit -m "feat(history): ScanHistory model + record/list/delete service

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: current_api_key dependency (auth refactor)

**Files:**
- Modify: `src/halal_scanner/api/security.py`
- Modify: `src/halal_scanner/api/app.py`
- Test: `tests/test_history_api.py` (new), `tests/test_api.py`

This swaps the scanning gate from `require_api_key` (returns `None`) to
`current_api_key` (returns the `ApiKey`), so later tasks can attribute scans. No
recording yet.

- [ ] **Step 1: Write the failing test for current_api_key**

Create `tests/test_history_api.py` with a reusable client fixture and a first test:

```python
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
```

- [ ] **Step 2: Run the test to verify the current state**

Run: `.venv/Scripts/python -m pytest tests/test_history_api.py -q`
Expected: PASS already (the existing `require_api_key` enforces this). This test is a guard that the refactor in Step 3 keeps the behaviour. If it does not pass, stop and investigate before refactoring.

- [ ] **Step 3: Add `current_api_key` and remove `require_api_key`**

In `src/halal_scanner/api/security.py`, replace the `require_api_key` function (currently lines ~26-32) with `current_api_key`, and add the `ApiKey` import. The current imports include `from ..auth.keys import verify_key` and `from ..db import get_db`; add:

```python
from ..auth.models import ApiKey
```

Replace:

```python
def require_api_key(
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> None:
    """Dependency: require a valid, non-revoked DB API key in X-API-Key."""
    if not x_api_key or verify_key(db, x_api_key) is None:
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")
```

with:

```python
def current_api_key(
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> ApiKey:
    """Dependency: require a valid, non-revoked DB API key and return its row."""
    key = verify_key(db, x_api_key) if x_api_key else None
    if key is None:
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")
    return key
```

- [ ] **Step 4: Update `app.py` to use `current_api_key`**

In `src/halal_scanner/api/app.py`:
- Change the import `from .security import rate_limit, require_api_key` to
  `from .security import current_api_key, rate_limit`.
- Change `_PROTECTED = [Depends(require_api_key), Depends(rate_limit)]` to
  `_PROTECTED = [Depends(current_api_key), Depends(rate_limit)]`.

- [ ] **Step 5: Update the auth-bypass fixture in `tests/test_api.py`**

`tests/test_api.py` imports and overrides `require_api_key`. Change the import line
`from halal_scanner.api.security import require_api_key` to:

```python
from halal_scanner.api.security import current_api_key
from halal_scanner.auth.models import ApiKey
```

And change the autouse fixture body from overriding `require_api_key` to:

```python
@pytest.fixture(autouse=True)
def _bypass_api_key():
    # Scanning auth is DB-backed; these tests aren't about auth, so return a
    # fake key (carrying a user_id for history attribution) and restore after.
    app.dependency_overrides[current_api_key] = lambda: ApiKey(id=1, user_id=1)
    yield
    app.dependency_overrides.pop(current_api_key, None)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_history_api.py tests/test_api.py tests/test_keys_api.py -q`
Expected: PASS — the new guard test, all existing scanning tests (via the fake key), and the real-key keys-api tests all stay green.

- [ ] **Step 7: Commit**

```bash
git add src/halal_scanner/api/security.py src/halal_scanner/api/app.py tests/test_api.py tests/test_history_api.py
git commit -m "refactor(api): current_api_key returns the key row for attribution

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: History router (GET + DELETE)

**Files:**
- Modify: `src/halal_scanner/api/schemas.py`
- Create: `src/halal_scanner/api/history_router.py`
- Modify: `src/halal_scanner/api/app.py`
- Test: `tests/test_history_api.py`

- [ ] **Step 1: Write the failing router tests**

Append to `tests/test_history_api.py` (the `ctx`, `_auth_headers`, `_make_key` helpers already exist there from Task 2):

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_history_api.py -q`
Expected: FAIL — `/history` routes return 404 (router not registered yet).

- [ ] **Step 3: Add the response schema**

In `src/halal_scanner/api/schemas.py`, append (the file already imports `BaseModel`, `ConfigDict`, and `datetime` is available via `from datetime import datetime` — if `datetime` is not imported, add `from datetime import datetime` at the top):

```python
class ScanHistoryOut(BaseModel):
    """One scan-history row, serialized for GET /history."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    scan_type: str
    summary: str
    verdict: str
    created_at: datetime
```

- [ ] **Step 4: Add the router**

Create `src/halal_scanner/api/history_router.py`:

```python
"""HTTP routes for a user's own scan history, mounted at /history (JWT required)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import history
from ..auth.dependencies import get_current_user
from ..auth.models import User
from ..db import get_db
from .schemas import ScanHistoryOut

router = APIRouter(prefix="/history", tags=["history"])


@router.get("", response_model=list[ScanHistoryOut])
def list_history(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list:
    return history.list_for_user(db, user, limit=limit, offset=offset)


@router.delete("/{scan_id}", status_code=204)
def delete_history_item(
    scan_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    try:
        history.delete_one(db, user, scan_id)
    except history.NotFound:
        raise HTTPException(status_code=404, detail="Scan not found.")


@router.delete("", status_code=204)
def clear_history(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    history.delete_all(db, user)
```

- [ ] **Step 5: Register the router in `app.py`**

In `src/halal_scanner/api/app.py`, add the import next to the other router imports (e.g. after `from ..auth.admin_router import router as admin_router`):

```python
from .history_router import router as history_router
```

And add the include next to the other `app.include_router(...)` calls:

```python
app.include_router(history_router)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_history_api.py -q`
Expected: PASS — list (newest-first), pagination + 422 bounds, JWT required, delete-one, cross-user 404, clear-all.

- [ ] **Step 7: Commit**

```bash
git add src/halal_scanner/api/schemas.py src/halal_scanner/api/history_router.py src/halal_scanner/api/app.py tests/test_history_api.py
git commit -m "feat(api): GET /history + DELETE endpoints (JWT)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Record scans in the scanning endpoints

**Files:**
- Modify: `src/halal_scanner/api/app.py`
- Test: `tests/test_history_api.py`, `tests/test_api.py`

- [ ] **Step 1: Write the failing end-to-end recording tests**

Append to `tests/test_history_api.py`:

```python
def test_classify_records_history(ctx):
    client, _ = ctx
    headers = _auth_headers(client)
    raw = _make_key(client, headers)
    client.post("/classify", json={"ingredients": ["sugar", "lard"]},
                headers={"X-API-Key": raw})
    rows = client.get("/history", headers=headers).json()
    assert len(rows) == 1
    assert rows[0]["scan_type"] == "classify"
    assert rows[0]["verdict"] == "haram"
    assert "sugar" in rows[0]["summary"] and "lard" in rows[0]["summary"]


def test_scan_image_records_history(ctx, monkeypatch):
    client, _ = ctx
    headers = _auth_headers(client)
    raw = _make_key(client, headers)
    monkeypatch.setattr(
        "halal_scanner.api.app._ocr_engine.extract_text", lambda b: "sugar\nlard"
    )
    client.post("/scan-image", content=b"img", headers={"X-API-Key": raw})
    rows = client.get("/history", headers=headers).json()
    assert len(rows) == 1 and rows[0]["scan_type"] == "image"
    assert rows[0]["verdict"] == "haram"
```

Also append to `tests/test_api.py` a best-effort test (a recording failure must not break the scan):

```python
def test_scan_still_succeeds_if_history_record_fails(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr("halal_scanner.api.app.history.record", boom)
    resp = client.post("/classify", json={"ingredients": ["sugar"]})
    assert resp.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest "tests/test_history_api.py::test_classify_records_history" "tests/test_api.py::test_scan_still_succeeds_if_history_record_fails" -q`
Expected: FAIL — `test_classify_records_history` finds 0 rows (nothing recorded yet); the best-effort test fails because `history.record` is not yet imported/called in `app.py` (AttributeError on monkeypatch target).

- [ ] **Step 3: Wire recording into the scanning endpoints**

In `src/halal_scanner/api/app.py`:

1. Add imports near the existing ones:

```python
from sqlalchemy.orm import Session

from .. import history
from ..auth.models import ApiKey
from ..db import get_db
```

(`Base, engine` are already imported from `..db`; importing `get_db` from the same module is fine. `ApiKey` and `history` are new.)

2. Remove `current_api_key` from `_PROTECTED` so it can be a value-returning per-endpoint dependency, leaving rate limiting shared:

```python
_PROTECTED = [Depends(rate_limit)]
```

3. Update `classify` to capture the key + db and record:

```python
@app.post("/classify", response_model=VerdictOut, dependencies=_PROTECTED)
def classify(
    req: ClassifyRequest,
    key: ApiKey = Depends(current_api_key),
    db: Session = Depends(get_db),
) -> VerdictOut:
    """Classify a list of ingredient strings and return an overall verdict."""
    client = _gemma_client if req.use_gemma else None
    engine = HalalClassifier(_rulebook, gemma_client=client)
    ingredients = _translate_all(req.ingredients, req.translate)
    verdict = engine.classify(ingredients)
    history.record(db, key.user_id, "classify", ", ".join(req.ingredients), verdict.verdict.value)
    return VerdictOut.from_verdict(verdict)
```

4. Update `scan_barcode`:

```python
@app.post("/scan-barcode", response_model=BarcodeVerdictOut, dependencies=_PROTECTED)
def scan_barcode(
    req: ScanBarcodeRequest,
    key: ApiKey = Depends(current_api_key),
    db: Session = Depends(get_db),
) -> BarcodeVerdictOut:
    """Look up a barcode on OpenFoodFacts, then classify its ingredients."""
    product = _off_client.fetch(req.barcode)
    if product is None:
        raise HTTPException(
            status_code=404,
            detail="Product not found or has no ingredient list.",
        )
    client = _gemma_client if req.use_gemma else None
    engine = HalalClassifier(_rulebook, gemma_client=client)
    ingredients = _translate_all(product.ingredients, req.translate)
    verdict = engine.classify(ingredients)
    history.record(
        db, key.user_id, "barcode",
        f"{product.barcode} ({product.name})", verdict.verdict.value,
    )
    return BarcodeVerdictOut.from_verdict_and_product(
        verdict, barcode=product.barcode, product_name=product.name
    )
```

5. Update `scan_image` (it is `async`; add the two dependencies and record before returning):

```python
@app.post("/scan-image", response_model=ImageVerdictOut, dependencies=_PROTECTED)
async def scan_image(
    request: Request,
    key: ApiKey = Depends(current_api_key),
    db: Session = Depends(get_db),
    use_gemma: bool = True,
    translate: bool = False,
) -> ImageVerdictOut:
    """OCR a label image (sent as the raw request body), then classify it."""
    image_bytes = await read_capped_body(request, MAX_IMAGE_BYTES)
    text = _ocr_engine.extract_text(image_bytes)
    ingredients = parse_ingredients(text)
    if not ingredients:
        raise HTTPException(
            status_code=422,
            detail="Could not read any text from the image.",
        )
    client = _gemma_client if use_gemma else None
    engine = HalalClassifier(_rulebook, gemma_client=client)
    ingredients = _translate_all(ingredients, translate)
    verdict = engine.classify(ingredients)
    history.record(db, key.user_id, "image", text, verdict.verdict.value)
    return ImageVerdictOut.from_verdict_and_text(verdict, extracted_text=text)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_history_api.py tests/test_api.py -q`
Expected: PASS — scans record one row each with the right type/verdict/summary; a failing `history.record` does not break the scan (best-effort). The `tests/test_api.py` fake key (`user_id=1`) makes recording attribute `user_id=1` against the temp DB; the best-effort test confirms a raise is swallowed.

- [ ] **Step 5: Commit**

```bash
git add src/halal_scanner/api/app.py tests/test_history_api.py tests/test_api.py
git commit -m "feat(api): record each scan to history (best-effort, attributed by key)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Full-suite verification & checkpoint

- [ ] **Step 1: Run the whole suite**

Run: `.venv/Scripts/python -m pytest -q`
Expected: all tests pass (159 baseline + the new history tests; 2 skipped unchanged). If anything fails, fix before proceeding.

- [ ] **Step 2: Update the checkpoint**

Edit `docs/CHECKPOINT.md`:
- Update the test count.
- Refresh the branch section (SP15 merged; SP16 in flight).
- Add an SP16 entry under "What's built": the `ScanHistory` model, the `history`
  service, `current_api_key` (replacing `require_api_key`), automatic best-effort
  recording on every scan, and the JWT `/history` GET/DELETE endpoints.
- Note that scans are now recorded per account, ready for the upcoming frontend.

- [ ] **Step 3: Commit the checkpoint and plan**

```bash
git add docs/CHECKPOINT.md docs/superpowers/plans/2026-06-03-scan-history.md
git commit -m "docs(halal-scanner): SP16 done — scan history (record + /history endpoints)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Notes for the implementer

- `current_api_key` fully replaces `require_api_key`; only `security.py`, `app.py`, and `tests/test_api.py` reference the old name (verified by grep). Update all three.
- Recording is best-effort (mirrors `auth/audit.py`): never let a history write break a scan. The `monkeypatch` best-effort test enforces this.
- `ScanHistoryOut` uses `from_attributes=True` so the router returns ORM rows directly (like `ApiKeyOut`).
- The `/history` router is JWT-authenticated (humans viewing their own history); scans are written via the machine-facing `X-API-Key` path. Both resolve to the same `User`.
- Every commit message ends with the trailer:
  `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`
- This branch is from `main`; final `--no-ff` merge to `main` after review.
