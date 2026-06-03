# Sub-project 14 — Prod-Exposure Cleanup (Design)

Date: 2026-06-03

Closes two LOW findings from the QA/security pass: L-2 (interactive docs and the
OpenAPI schema are served unauthenticated) and L-3 (no explicit CORS policy).
Both changes are env-gated and default to today's behaviour, so nothing changes
for local development. Branched from the SP13 tip (stacked: SP11 → SP12 → SP13 →
SP14). Touches only `src/halal_scanner/api/app.py`.

## L-2 — Disable docs in production

FastAPI serves `/docs` (Swagger UI), `/redoc`, and `/openapi.json` by default,
all unauthenticated. In production those should be off. Gate on a new env var
`HALAL_ENV` (default `dev`): when it is `production` or `prod`, construct the app
with those URLs disabled (FastAPI returns 404 for each).

A pure helper keeps the decision testable without importing/booting the app
under a production environment:

```python
def _docs_kwargs(env: str) -> dict:
    """FastAPI kwargs that hide the interactive docs/schema in production."""
    if env.strip().lower() in {"prod", "production"}:
        return {"docs_url": None, "redoc_url": None, "openapi_url": None}
    return {}
```

Applied at construction:

```python
app = FastAPI(
    title="Halal Scanner API",
    description="Classify food ingredients as halal / non-halal (haram) / shubhah.",
    version="0.1.0",
    **_docs_kwargs(os.environ.get("HALAL_ENV", "dev")),
)
```

Default (`HALAL_ENV` unset → `dev`) yields `{}`, so `/docs` stays at 200 in
development and existing tests are unaffected.

## L-3 — Explicit CORS allow-list

FastAPI ships no CORS middleware by default, which is safe (browsers block
cross-origin requests). When a web frontend is added, an explicit allow-list is
needed — and a wildcard `["*"]` with credentials must be avoided. Gate on
`HALAL_CORS_ORIGINS` (comma-separated origins). Empty/unset → no CORS middleware
(keep the safe default). Set → add `CORSMiddleware` with that allow-list.

A pure helper parses the list:

```python
def _parse_cors_origins(raw: str) -> list[str]:
    """Comma-separated allow-list -> list of origins (blanks dropped)."""
    return [o.strip() for o in raw.split(",") if o.strip()]
```

Applied after the app is built:

```python
from fastapi.middleware.cors import CORSMiddleware

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

`allow_credentials=False`: the API authenticates via headers (`X-API-Key` and the
`Authorization` Bearer JWT), not cookies, so credentialed CORS is unnecessary —
and keeping it off sidesteps the wildcard-with-credentials hazard the finding
warns about. `allow_headers=["*"]` lets a browser send the auth headers on
preflight. (If cookie-based auth is ever added, this must change to a strict
allow-list with `allow_credentials=True`.)

## Out of scope (remain open)

- HIGH-1 fail-closed-in-production (refuse to start in prod unless an API
  key/rate limit is configured) — a separate posture change; could be SP15.
- HSTS at the proxy; MED-1 Redis/shared limiter; MED-3 (accepted risk).

## Testing (TDD, red → green)

`_docs_kwargs` (`tests/test_api.py`, pure):
- `"dev"` / `""` → `{}`.
- `"production"`, `"prod"`, `" PROD "` → `{"docs_url": None, "redoc_url": None, "openapi_url": None}`.

`_parse_cors_origins` (`tests/test_api.py`, pure):
- `"https://a.com, https://b.com"` → `["https://a.com", "https://b.com"]`.
- `""` → `[]`; `" , "` → `[]`.

Docs wiring (build a throwaway app from the helper, no reimport of the real app):
- `FastAPI(**_docs_kwargs("production")).docs_url is None` and `.openapi_url is None`.
- `FastAPI(**_docs_kwargs("dev")).docs_url == "/docs"`.

CORS default-closed (live app via `TestClient`):
- `GET /health` with header `Origin: http://evil.com` → the response has NO
  `access-control-allow-origin` header (no allow-list configured in the test env).

Run: `.venv/Scripts/python -m pytest -q` (baseline on this branch: 149 passing,
2 skipped).

## Conventions

Branch `sub-project-14-prod-exposure` (stacked on SP13); spec here; plan in
`docs/superpowers/plans/`; TDD; `--no-ff` merge to `main` after SP11–13; delete
the branch. Commit trailer:
`Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
