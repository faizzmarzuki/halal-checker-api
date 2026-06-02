# Halal Food Scanner

Classify food ingredients as **halal**, **haram** (non-halal), or **shubhah**
(doubtful). A deterministic English rulebook is the authority; everything else
(barcode lookup, OCR, translation, an optional local LLM) just feeds clean
ingredient text into that engine. Every verdict carries a disclaimer — this is a
decision aid, **not a religious ruling**.

## Architecture

```
                 barcode ──▶ OpenFoodFacts ─┐
  image ──▶ OCR (Tesseract) ────────────────┤
  raw ingredient list ──────────────────────┤─▶ [translate?] ─▶ HalalClassifier ─▶ verdict
                                              │      (Gemma)         │
                                              │                 rulebook (authority)
                                              │                 Gemma fallback (low-confidence)
```

The project was built in six sub-projects (specs in `docs/superpowers/specs/`):

1. **Classification engine** — `models`, `normalizer`, `rulebook`, `gemma`, `classifier`.
2. **FastAPI layer** — `POST /classify`, `GET /health`.
3. **OpenFoodFacts barcode lookup** — `POST /scan-barcode`.
4. **OCR label scanning** — `POST /scan-image`.
5. **Translation** — opt-in `translate` flag (foreign-language labels → English).
6. **Hardening** — optional API-key auth + in-memory rate limiting.

## API

| Method | Path           | Body / input                                   | Notes |
|--------|----------------|------------------------------------------------|-------|
| POST   | `/classify`    | `{"ingredients": [...], "use_gemma", "translate"}` | Classify a list of strings. |
| POST   | `/scan-barcode`| `{"barcode": "...", "use_gemma", "translate"}` | Look up ingredients on OpenFoodFacts. 404 if not found. |
| POST   | `/scan-image`  | raw image bytes; `?use_gemma=&translate=`      | OCR a label photo. 422 if no text read. |
| GET    | `/health`      | —                                              | Liveness; reports Ollama reachability. Always open. |
| GET    | `/docs`        | —                                              | Swagger UI. |

- `use_gemma` (default `true`): allow the local Gemma/Ollama fallback for
  ingredients missing from the rulebook. `false` => fully deterministic, no network.
- `translate` (default `false`): translate each ingredient to English (via the
  local Ollama server) before classifying.

### Accounts (Sub-project 7)

User accounts with JWT auth. Access tokens are short-lived; refresh tokens are
stored (hashed) server-side and rotated on every refresh, so logout revokes them.

| Method | Path             | Body / input                  | Notes |
|--------|------------------|-------------------------------|-------|
| POST   | `/auth/register` | `{"email", "password"}`       | `201`; `409` if email taken; `422` if invalid. |
| POST   | `/auth/login`    | `{"email", "password"}`       | Returns `{access_token, refresh_token, token_type}`. `401` on bad creds. |
| POST   | `/auth/refresh`  | `{"refresh_token"}`           | Rotates tokens; the old refresh token is revoked. `401` if invalid. |
| POST   | `/auth/logout`   | `{"refresh_token"}`           | `204`; revokes the refresh token. |
| GET    | `/auth/me`       | `Authorization: Bearer <jwt>` | Current user. `401` if missing/invalid. |

### API keys (Sub-project 8)

Log in (JWT), then manage keys. The raw key is shown **once** at creation.

| Method | Path          | Body      | Notes |
|--------|---------------|-----------|-------|
| POST   | `/keys`       | `{name?}` | `201`; returns the raw `api_key` once. |
| GET    | `/keys`       | —         | List your keys (metadata only, no raw value). |
| DELETE | `/keys/{id}`  | —         | `204`; revokes the key. `404` if not yours. |

Use a key by sending `X-API-Key: <key>` to the scanning endpoints.

## Configuration (environment variables)

| Var | Default | Effect |
|-----|---------|--------|
| `HALAL_RATE_LIMIT` | `0`       | Max requests per window. `0` => limiting **off**. |
| `HALAL_RATE_WINDOW`| `60`      | Rate-limit window, seconds. |
| `HALAL_DATABASE_URL` | `sqlite:///./halal_scanner.db` | SQLAlchemy connection string for the accounts DB. |
| `HALAL_JWT_SECRET` | _(required)_ | HS256 signing secret. The API **will not start** without it. |
| `HALAL_ACCESS_TTL` | `900`     | Access-token lifetime, seconds. |
| `HALAL_REFRESH_TTL`| `604800`  | Refresh-token lifetime, seconds. |

The scanning endpoints (`/classify`, `/scan-barcode`, `/scan-image`) **always**
require a valid `X-API-Key` (a key you create at `/keys`); `/health` is open.
The `/auth/*` and `/keys` endpoints use JWT bearer tokens and require
`HALAL_JWT_SECRET`. Rate limiting (env vars above) still applies.

## Install & run

```bash
cd halal-scanner
python -m venv .venv && .venv/Scripts/python -m pip install -e ".[dev]"
# Optional, for real OCR (also needs the system `tesseract` binary):
#   .venv/Scripts/python -m pip install -e ".[ocr]"

# Run the API
.venv/Scripts/python -m uvicorn halal_scanner.api.app:app --reload
# open http://localhost:8000/docs
```

The Gemma fallback and translation expect a local [Ollama](https://ollama.com)
server (`gemma4:latest`); both degrade gracefully when it is unreachable.

## Test

```bash
.venv/Scripts/python -m pytest -q
```

All tests are network-free and binary-free: the LLM, OpenFoodFacts, and OCR
backends are stubbed, so the suite runs anywhere with no external services.
