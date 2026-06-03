# Prod-Exposure Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Disable the interactive docs/OpenAPI schema in production and add an opt-in CORS allow-list — both env-gated and default-safe (L-2, L-3).

**Architecture:** Two pure config helpers (`_docs_kwargs`, `_parse_cors_origins`) in `src/halal_scanner/api/app.py`; the first feeds the `FastAPI(...)` constructor, the second conditionally adds `CORSMiddleware`. Defaults preserve today's behaviour.

**Tech Stack:** FastAPI (`docs_url`/`openapi_url` args, `CORSMiddleware`), pytest + `fastapi.testclient.TestClient`. Baseline on this branch (stacked on SP13): **149 passing, 2 skipped**.

---

## File Structure

- `src/halal_scanner/api/app.py` — add `_docs_kwargs` + `_parse_cors_origins`; pass docs kwargs to `FastAPI(...)`; conditionally add `CORSMiddleware`.
- `tests/test_api.py` — pure-helper tests + a docs-wiring test + a CORS-default-closed test.

Run the full suite at any point with: `.venv/Scripts/python -m pytest -q`

---

## Task 1: Disable docs in production (L-2)

**Files:**
- Modify: `src/halal_scanner/api/app.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_api.py`:

```python
def test_docs_kwargs_dev_is_empty():
    from halal_scanner.api.app import _docs_kwargs

    assert _docs_kwargs("dev") == {}
    assert _docs_kwargs("") == {}


def test_docs_kwargs_production_disables_docs():
    from halal_scanner.api.app import _docs_kwargs

    expected = {"docs_url": None, "redoc_url": None, "openapi_url": None}
    assert _docs_kwargs("production") == expected
    assert _docs_kwargs("prod") == expected
    assert _docs_kwargs(" PROD ") == expected


def test_docs_disabled_app_has_none_urls():
    from fastapi import FastAPI

    from halal_scanner.api.app import _docs_kwargs

    prod = FastAPI(**_docs_kwargs("production"))
    assert prod.docs_url is None
    assert prod.openapi_url is None
    dev = FastAPI(**_docs_kwargs("dev"))
    assert dev.docs_url == "/docs"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_api.py::test_docs_kwargs_dev_is_empty -v`
Expected: FAIL with `ImportError: cannot import name '_docs_kwargs'`.

- [ ] **Step 3: Add the helper and wire the constructor**

In `src/halal_scanner/api/app.py`, add the helper just BEFORE the `app = FastAPI(...)` block (it currently sits at lines ~37-41, right after the `from .schemas import (...)` block). Insert:

```python
def _docs_kwargs(env: str) -> dict:
    """FastAPI kwargs that hide the interactive docs/schema in production (L-2)."""
    if env.strip().lower() in {"prod", "production"}:
        return {"docs_url": None, "redoc_url": None, "openapi_url": None}
    return {}
```

Then change the `FastAPI(...)` call from:

```python
app = FastAPI(
    title="Halal Scanner API",
    description="Classify food ingredients as halal / non-halal (haram) / shubhah.",
    version="0.1.0",
)
```

to:

```python
app = FastAPI(
    title="Halal Scanner API",
    description="Classify food ingredients as halal / non-halal (haram) / shubhah.",
    version="0.1.0",
    **_docs_kwargs(os.environ.get("HALAL_ENV", "dev")),
)
```

`os` is already imported at the top of the file (`import os`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_api.py -v`
Expected: PASS — the three new tests green; all existing endpoint tests still pass (the test env does not set `HALAL_ENV`, so the live app stays in `dev` mode with docs enabled).

- [ ] **Step 5: Commit**

```bash
git add src/halal_scanner/api/app.py tests/test_api.py
git commit -m "feat(api): disable /docs and /openapi.json in production (L-2)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Explicit CORS allow-list (L-3)

**Files:**
- Modify: `src/halal_scanner/api/app.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_api.py`:

```python
def test_parse_cors_origins():
    from halal_scanner.api.app import _parse_cors_origins

    assert _parse_cors_origins("https://a.com, https://b.com") == [
        "https://a.com",
        "https://b.com",
    ]
    assert _parse_cors_origins("") == []
    assert _parse_cors_origins(" , ") == []


def test_cors_closed_by_default():
    # No HALAL_CORS_ORIGINS in the test env => no CORS middleware => a cross-origin
    # request gets no allow-origin header (browsers will block it).
    resp = client.get("/health", headers={"Origin": "http://evil.com"})
    assert resp.status_code == 200
    assert "access-control-allow-origin" not in resp.headers
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_api.py::test_parse_cors_origins -v`
Expected: FAIL with `ImportError: cannot import name '_parse_cors_origins'`.

- [ ] **Step 3: Add the helper, import, and conditional middleware**

In `src/halal_scanner/api/app.py`:

1. Add the CORS middleware import. The file imports `from fastapi import Depends, FastAPI, HTTPException, Request` (around line 13). Add directly below it:

```python
from fastapi.middleware.cors import CORSMiddleware
```

2. Add the helper next to `_docs_kwargs` (just before the `app = FastAPI(...)` block):

```python
def _parse_cors_origins(raw: str) -> list[str]:
    """Comma-separated allow-list -> list of origins, blanks dropped (L-3)."""
    return [o.strip() for o in raw.split(",") if o.strip()]
```

3. Add the conditional middleware immediately AFTER the `app = FastAPI(...)` block (before the existing `@app.middleware("http")` security-headers function):

```python
# Default-closed: with no allow-list configured, no CORS middleware is added, so
# browsers block cross-origin requests (the safe FastAPI default). Auth is via
# headers (X-API-Key / Bearer), not cookies, so credentials are not enabled (L-3).
_cors_origins = _parse_cors_origins(os.environ.get("HALAL_CORS_ORIGINS", ""))
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_api.py -v`
Expected: PASS — the two new tests green; existing tests still pass (no `HALAL_CORS_ORIGINS` in the test env, so no CORS middleware is added and behaviour is unchanged).

- [ ] **Step 5: Commit**

```bash
git add src/halal_scanner/api/app.py tests/test_api.py
git commit -m "feat(api): opt-in CORS allow-list via HALAL_CORS_ORIGINS (L-3)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Full-suite verification & checkpoint

- [ ] **Step 1: Run the whole suite**

Run: `.venv/Scripts/python -m pytest -q`
Expected: all tests pass (149 baseline + 5 new = 154 passing, 2 skipped). If anything fails, fix before proceeding.

- [ ] **Step 2: Update the checkpoint**

Edit `docs/CHECKPOINT.md`:
- Update the test count.
- Add an SP14 entry under "What's built".
- Under "Already fixed", add L-2 (docs disabled in prod, via SP14) and L-3 (explicit CORS allow-list, via SP14).
- Add `HALAL_ENV` and `HALAL_CORS_ORIGINS` to the "Key env vars" list.
- Remove the now-done items from "Still open" / "LOW"; leave HIGH-1 (fail-closed-prod), MED-1 (Redis), MED-3, and HSTS-at-proxy as still open.
- Update the SP11–14 branch state (SP14 stacked on SP13) and "Suggested next step" (e.g. HIGH-1 fail-closed-in-production as SP15).

- [ ] **Step 3: Commit the checkpoint and plan**

```bash
git add docs/CHECKPOINT.md docs/superpowers/plans/2026-06-03-prod-exposure.md
git commit -m "docs(halal-scanner): SP14 done — docs disabled in prod + CORS allow-list

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Notes for the implementer

- `HALAL_ENV` (default `dev`): set to `production`/`prod` to hide `/docs`, `/redoc`, `/openapi.json`.
- `HALAL_CORS_ORIGINS` (default empty): comma-separated origin allow-list; empty = no CORS middleware (safe default).
- `allow_credentials=False` is deliberate — the API uses header auth, not cookies. Do NOT change it without switching to cookie-based auth and a strict origin list.
- Do NOT implement HIGH-1 fail-closed-in-production here — that is a separate posture change (potential SP15) and out of scope.
- Every commit message ends with the trailer:
  `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`
- This branch is stacked on SP13; final `--no-ff` merge to `main` happens after SP11–13 merge (handled after review, not in this plan).
