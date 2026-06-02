# Project Checkpoint — 2026-06-02

Resume point for the Halal Checker API. Tell Claude "refer to docs/CHECKPOINT.md"
to pick up exactly here.

## Where things stand
- **Branch:** `main` (clean working tree). Pushed to **private** GitHub repo
  `https://github.com/faizzmarzuki/halal-checker-api` and `main` tracks
  `origin/main`. (This checkpoint commit itself is **local-only** until the next push.)
- **Tests:** `122 passing`, coverage ~98%. Run: `.venv/Scripts/python -m pytest -q`
- **Run the API:** set `HALAL_JWT_SECRET` then
  `.venv/Scripts/python -m uvicorn halal_scanner.api.app:app --reload` → http://localhost:8000/docs

## What's built (all merged to main)
Original product (sub-projects 1–6): classification engine, FastAPI layer,
OpenFoodFacts barcode lookup, OCR, translation, hardening (rate limiting).

Auth track (sub-projects 7–10), built this session via spec → plan → TDD →
subagent review → merge (docs in `docs/superpowers/specs` & `/plans`):
- **SP7 Accounts Core** — SQLAlchemy+SQLite DB, `/auth/register|login|logout|refresh|me`,
  JWT access + DB-backed refresh tokens (rotation).
- **SP8 API-Key Management** — `/keys` (create/list/delete, JWT); scanning endpoints
  (`/classify`, `/scan-barcode`, `/scan-image`) now ALWAYS require a valid DB
  `X-API-Key` (env-var `HALAL_API_KEYS` removed).
- **SP9 Account Recovery** — `/auth/verify/*` + `/auth/password-reset/*`; single-use
  hashed expiring tokens; pluggable `Emailer` (default console/log backend).
- **SP10 Roles & Audit** — `user`/`admin` role (admin via `HALAL_ADMIN_EMAILS`),
  `/admin/users` + `/admin/audit`, audit log of auth/key events.

## Two auth layers (don't confuse)
- **JWT Bearer** → `/auth/*`, `/keys`, `/admin/*` (humans managing accounts).
- **`X-API-Key`** → scanning endpoints (machines calling the classifier).

## Key env vars
`HALAL_JWT_SECRET` (required), `HALAL_DATABASE_URL`, `HALAL_ACCESS_TTL`,
`HALAL_REFRESH_TTL`, `HALAL_ADMIN_EMAILS`, `HALAL_RATE_LIMIT`, `HALAL_RATE_WINDOW`.

## Open work (NOT done yet) — from the QA/security pass
Full details in `QA_SECURITY_FINDINGS.txt` (kept local / gitignored, not on GitHub).
Already fixed: HIGH-1 (scanning auth secure-by-default, via SP8), L-4 (audit log, via SP10).
Still open:
- **HIGH-2** — no request-size limits (DoS): `/classify` ingredient list has no
  `max_length`, `/scan-image` reads the whole body uncapped; LLM/translate fan-out
  amplification.
- **HIGH-3** — barcode is interpolated into the OpenFoodFacts URL without
  validation (path/SSRF risk); validate `^[0-9]{6,14}$` + urlencode + no redirects.
- **MED/LOW** — Pillow decompression-bomb guard, LLM prompt-injection note,
  constant-time API-key compare, security headers, disable public `/docs` in prod,
  proxy-aware/shared rate limiting.

## Suggested next step
Harden HIGH-2 then HIGH-3 (each as its own small spec → plan → TDD → merge,
same workflow as SP7–10). Could be "Sub-project 11: DoS/input hardening".

## Conventions for this repo
- Chat in casual Malay (bahasa pasar); code/comments/docs/commits in English.
- Per feature: branch `sub-project-N-...`, spec in `docs/superpowers/specs/`,
  plan in `docs/superpowers/plans/`, TDD, `--no-ff` merge to main, delete branch.
- Commit trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
