# Sub-project 15 — Fail-Closed in Production (Design)

Date: 2026-06-03

Closes the remaining half of QA finding HIGH-1. Branched from `main` (the SP11–14
stack is merged). Touches only `src/halal_scanner/api/app.py`.

## Context

HIGH-1 had two parts. The **auth** part is already done: SP8 made the scanning
endpoints always require a valid DB-backed `X-API-Key` (there is no "auth off"
mode). The remaining gap is **rate limiting is off by default** — if the API is
deployed to production without setting `HALAL_RATE_LIMIT`, it serves unthrottled.

The fix is to **fail closed in production**: refuse to start when
`HALAL_ENV` is `prod`/`production` unless a positive `HALAL_RATE_LIMIT` is
configured. (`HALAL_ENV` was introduced in SP14 for the docs gate; this reuses
it, so prod posture is controlled by one consistent variable.)

Auth is NOT re-checked here — a valid API key is already mandatory for every
scanning request regardless of environment. The production posture this adds is
simply "a rate limit must be configured".

## Fix

Add a pure helper in `src/halal_scanner/api/app.py`, next to `_docs_kwargs`:

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

Call it at import time, right next to the existing JWT-secret fail-closed check:

```python
# Fail closed: refuse to start without a signing secret (any environment).
if not os.environ.get("HALAL_JWT_SECRET"):
    raise RuntimeError("HALAL_JWT_SECRET must be set to start the API.")

# Fail closed in production: a rate limit must be configured (HIGH-1).
_require_prod_posture(
    os.environ.get("HALAL_ENV", "dev"), os.environ.get("HALAL_RATE_LIMIT")
)
```

Default (`HALAL_ENV` unset → `dev`) is a no-op, so local development and the
existing test suite (which never sets `HALAL_ENV`) are unaffected.

## Out of scope (remain open)

- MED-1 Redis / shared-across-workers limiter (infra-gated).
- MED-3 LLM prompt-injection (accepted risk).
- LOW HSTS at the reverse proxy.

After this sub-project, all HIGH findings are closed and the QA security backlog
is down to infra-gated / accepted items only.

## Testing (TDD, red → green)

`_require_prod_posture` (`tests/test_api.py`, pure — no app reload needed):
- `("dev", None)` → no raise.
- `("dev", "0")` → no raise (non-prod ignores the rate limit).
- `("production", None)` → raises `RuntimeError`.
- `("production", "0")` → raises `RuntimeError`.
- `("prod", "abc")` → raises `RuntimeError` (unparseable treated as 0).
- `("production", "100")` → no raise.
- `(" PROD ", "5")` → no raise (case/space-insensitive prod match).

Run: `.venv/Scripts/python -m pytest -q` (baseline on this branch: 155 passing,
2 skipped).

## Conventions

Branch `sub-project-15-fail-closed-prod` (from `main`); spec here; plan in
`docs/superpowers/plans/`; TDD; `--no-ff` merge to `main`; delete the branch.
Commit trailer:
`Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
