# Fail-Closed in Production Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refuse to start the API in production unless a positive rate limit is configured, closing the remaining half of HIGH-1.

**Architecture:** One pure helper `_require_prod_posture(env, rate_limit_raw)` in `src/halal_scanner/api/app.py` that raises `RuntimeError` when `HALAL_ENV` is prod/production and `HALAL_RATE_LIMIT` is not a positive integer; called at import time beside the existing JWT-secret fail-closed check.

**Tech Stack:** FastAPI app module, pytest. Baseline on this branch (from merged `main`): **155 passing, 2 skipped**.

---

## File Structure

- `src/halal_scanner/api/app.py` — add `_require_prod_posture`; call it at import time after the `HALAL_JWT_SECRET` guard.
- `tests/test_api.py` — pure-helper tests covering the prod/dev × configured/unconfigured matrix.

Run the full suite at any point with: `.venv/Scripts/python -m pytest -q`

---

## Task 1: Production rate-limit posture check (HIGH-1)

**Files:**
- Modify: `src/halal_scanner/api/app.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_api.py`:

```python
def test_require_prod_posture_dev_is_noop():
    from halal_scanner.api.app import _require_prod_posture

    # Non-prod never raises, regardless of the rate-limit value.
    assert _require_prod_posture("dev", None) is None
    assert _require_prod_posture("dev", "0") is None


def test_require_prod_posture_production_requires_rate_limit():
    import pytest

    from halal_scanner.api.app import _require_prod_posture

    for bad in (None, "0", "abc"):
        with pytest.raises(RuntimeError):
            _require_prod_posture("production", bad)


def test_require_prod_posture_production_with_limit_ok():
    from halal_scanner.api.app import _require_prod_posture

    assert _require_prod_posture("production", "100") is None
    assert _require_prod_posture("prod", "1") is None
    assert _require_prod_posture(" PROD ", "5") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_api.py::test_require_prod_posture_dev_is_noop -v`
Expected: FAIL with `ImportError: cannot import name '_require_prod_posture'`.

- [ ] **Step 3: Add the helper and call it at import time**

In `src/halal_scanner/api/app.py`, add the helper next to the existing `_docs_kwargs` / `_parse_cors_origins` helpers (which sit just before the `app = FastAPI(...)` block):

```python
def _require_prod_posture(env: str, rate_limit_raw: str | None) -> None:
    """In production, refuse to start unless a positive rate limit is set (HIGH-1).

    Auth (a valid DB API key) is already mandatory in every environment; the only
    insecure-by-default surface left is rate limiting, which is off unless
    HALAL_RATE_LIMIT is set. In prod we require it to be a positive integer.
    """
    if env.strip().lower() not in {"prod", "production"}:
        return
    try:
        limit = int(rate_limit_raw or "0")
    except ValueError:
        limit = 0
    if limit <= 0:
        raise RuntimeError(
            "In production (HALAL_ENV=production), HALAL_RATE_LIMIT must be a "
            "positive integer so the API is not unthrottled. Set it before starting."
        )
```

Then find the existing JWT fail-closed guard (it reads, around line 86-88):

```python
# Fail closed: refuse to start without a signing secret (see security spec).
if not os.environ.get("HALAL_JWT_SECRET"):
    raise RuntimeError("HALAL_JWT_SECRET must be set to start the API.")
```

Add the production posture call immediately AFTER it:

```python
# Fail closed in production: a rate limit must be configured (HIGH-1).
_require_prod_posture(
    os.environ.get("HALAL_ENV", "dev"), os.environ.get("HALAL_RATE_LIMIT")
)
```

`os` is already imported at the top of the file.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_api.py -v`
Expected: PASS — the three new tests green; all existing endpoint tests still pass (the test env never sets `HALAL_ENV`, so the import-time call is a no-op and the app imports normally).

- [ ] **Step 5: Commit**

```bash
git add src/halal_scanner/api/app.py tests/test_api.py
git commit -m "feat(api): fail closed in production without a rate limit (HIGH-1)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Full-suite verification & checkpoint

- [ ] **Step 1: Run the whole suite**

Run: `.venv/Scripts/python -m pytest -q`
Expected: all tests pass (155 baseline + 3 new = 158 passing, 2 skipped). If anything fails, fix before proceeding.

- [ ] **Step 2: Update the checkpoint**

Edit `docs/CHECKPOINT.md`:
- Refresh the "Where things stand" branch section: the SP11–SP14 stack is now merged into `main` (PRs #1–#4 closed); only the SP15 branch is in flight.
- Update the test count.
- Add an SP15 entry under "What's built".
- Under "Already fixed", record HIGH-1 as now fully closed (auth via SP8 + prod fail-closed rate limit via SP15); remove the "HIGH-1 (remaining)" item from "Still open".
- Note `HALAL_ENV=production` now also requires `HALAL_RATE_LIMIT` in the env-var section.
- Update "Suggested next step": the QA security backlog is down to infra-gated (MED-1 Redis) and accepted (MED-3) / proxy (HSTS) items; next meaningful work is a product feature.

- [ ] **Step 3: Commit the checkpoint and plan**

```bash
git add docs/CHECKPOINT.md docs/superpowers/plans/2026-06-03-fail-closed-prod.md
git commit -m "docs(halal-scanner): SP15 done — fail closed in production (HIGH-1 complete)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Notes for the implementer

- The check is intentionally prod-only: `HALAL_ENV` unset → `dev` → no-op, so nothing changes for local dev or the test suite.
- Only `HALAL_RATE_LIMIT` is required in prod. Do NOT also require API keys (they are always mandatory via SP8) or other env vars — that is out of scope for HIGH-1.
- Keep PEP 8 spacing (two blank lines around the new top-level helper).
- Every commit message ends with the trailer:
  `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`
- This branch is from `main`; final `--no-ff` merge to `main` happens after review (handled after review, not in this plan).
