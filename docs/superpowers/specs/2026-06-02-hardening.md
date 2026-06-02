# Sub-project 6: Hardening (Auth + Rate Limiting) — Design Spec

**Date:** 2026-06-02
**Status:** Approved (autonomous continuation)
**Part of:** Halal Food Scanner — Sub-project 6 of 6 (final)
**Depends on:** Sub-projects 1–5

## Purpose
Make the API safe to expose: optional **API-key auth** and a simple **in-memory
rate limiter**, applied to the scanning endpoints. Both are **disabled by
default** and configured purely via environment variables, so local/dev use and
the existing test suite are unaffected.

## New module: `api/security.py`
- `require_api_key(x_api_key: str | None = Header(None))` — FastAPI dependency.
  - Reads allowed keys **live** from `HALAL_API_KEYS` (comma-separated) each call.
  - No keys configured → auth disabled (request allowed).
  - Keys configured and header missing/unknown → **HTTP 401**.
- `class RateLimiter` — a sliding-window-log limiter.
  - `__init__(limit, window, now=time.monotonic)` — `now` is injectable so tests
    use a fake clock (no `sleep`). Thread-safe via a lock.
  - `allow(key) -> bool` — `limit <= 0` disables it (always allows). Otherwise
    drops timestamps older than `window`, then allows iff fewer than `limit`
    hits remain in the window.
- `rate_limit(request: Request, x_api_key=Header(None))` — FastAPI dependency
  that calls the module-level `limiter` (built from `HALAL_RATE_LIMIT` /
  `HALAL_RATE_WINDOW`, default limit `0` = disabled). Bucket key = API key if
  present, else client IP. Over limit → **HTTP 429**.

## API wiring
The three scanning routes — `POST /classify`, `POST /scan-barcode`,
`POST /scan-image` — get `dependencies=[Depends(require_api_key), Depends(rate_limit)]`.
`GET /health` is left **open** so liveness probes never need a key.

## Configuration (env vars)
- `HALAL_API_KEYS` — comma-separated allowed keys. Unset/empty → auth off.
- `HALAL_RATE_LIMIT` — max requests per window (int). Unset/`0` → limiting off.
- `HALAL_RATE_WINDOW` — window length in seconds (float, default `60`).

## Dependencies
None new — stdlib (`os`, `time`, `threading`, `collections`) + FastAPI.

## Testing (TDD, network-free)
`tests/test_security.py` (unit, fake clock):
- allows up to `limit` within the window, blocks the next.
- after the clock advances past `window`, allows again.
- `limit <= 0` always allows.
- missing/unknown key with keys configured raises 401; correct key passes;
  no keys configured allows.

`tests/test_api.py`:
- with `HALAL_API_KEYS` set: `POST /classify` without header → 401; with the
  correct `X-API-Key` → 200; `GET /health` still works without a key.
- rate limit: patch the module-level `limiter` to `limit=1` → first
  `POST /classify` 200, second → 429.

## Out of scope
Persistent/distributed rate limiting (Redis), OAuth/JWT, per-route quotas.
