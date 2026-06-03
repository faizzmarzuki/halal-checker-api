# Project Checkpoint — 2026-06-03

Resume point for the Halal Checker API. Tell Claude "refer to docs/CHECKPOINT.md"
to pick up exactly here.

## Where things stand
- **Branches in flight (not yet merged to `main`):**
  - `sub-project-11-dos-input-hardening` — pushed; open as **PR #1**
    (`https://github.com/faizzmarzuki/halal-checker-api/pull/1`).
  - `sub-project-12-image-response-hardening` — **stacked on SP11** (branched off
    its tip), local only. Merge order: SP11 first, then SP12.
- Private GitHub repo: `https://github.com/faizzmarzuki/halal-checker-api`.
  `gh` CLI is NOT installed locally — PRs are created via the GitHub REST API
  using the stored git credential.
- **Tests:** `142 passing` (+2 skipped — Pillow-gated OCR tests; install the
  `ocr` extra to run them), coverage ~98%. Run: `.venv/Scripts/python -m pytest -q`
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

SP11 DoS/input hardening (built this session, same spec → plan → TDD → subagent
review → merge workflow):
- **SP11 DoS/Input Hardening** — `/classify` ingredient list capped (≤200 items,
  ≤200 chars each → 422); `/scan-image` body capped at 5 MB → 413 (streaming
  `read_capped_body`); barcode validated `^[0-9]{6,14}$` at the edge (422) plus
  defence-in-depth in `OpenFoodFactsClient.fetch` (regex guard, URL-encode,
  `allow_redirects=False`).
- **SP12 Image/Response Hardening** — `/scan-image` OCR caps decoded image area
  at 40 MP (`ocr._open_image` / `_ensure_within_pixel_cap`) to block
  decompression bombs; security headers on every response
  (`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `Referrer-Policy: no-referrer`); `extra="forbid"` on the scanning request
  models so unknown JSON fields are rejected (422).

## Two auth layers (don't confuse)
- **JWT Bearer** → `/auth/*`, `/keys`, `/admin/*` (humans managing accounts).
- **`X-API-Key`** → scanning endpoints (machines calling the classifier).

## Key env vars
`HALAL_JWT_SECRET` (required), `HALAL_DATABASE_URL`, `HALAL_ACCESS_TTL`,
`HALAL_REFRESH_TTL`, `HALAL_ADMIN_EMAILS`, `HALAL_RATE_LIMIT`, `HALAL_RATE_WINDOW`.

## Open work (NOT done yet) — from the QA/security pass
Full details in `QA_SECURITY_FINDINGS.txt` (kept local / gitignored, not on GitHub).
Already fixed: HIGH-1 (scanning auth secure-by-default, via SP8), L-4 (audit log, via SP10),
HIGH-2 (request-size limits, via SP11), HIGH-3 (barcode validation/SSRF guard, via SP11),
MED-2 (image decompression-bomb guard, via SP12), L-1 (security headers, via SP12),
L-5 (`extra="forbid"` on scanning models, via SP12; auth models already had it).
Already mitigated by design (no code change): MED-4 (constant-time API-key compare) —
SP8 replaced the old plaintext key compare with a SHA-256 hash + DB lookup, so there
is no exploitable timing side channel.
Still open:
- **MED-1** — rate limiter is proxy-blind (keys on `request.client.host`,
  ignores `X-Forwarded-For`), per-process (not shared across workers), and never
  evicts stale keys. Needs trusted-proxy IP handling + Redis/gateway for scale-out.
- **MED-3** — LLM prompt-injection note (accepted risk: rulebook is authority,
  Gemma is low-confidence + disclaimed).
- **LOW** — disable public `/docs`/`/openapi.json` in prod, explicit CORS
  allow-list when a web frontend lands, HSTS at the proxy.

## Suggested next step
HIGH + the cheap MED/LOW items are done. Biggest remaining is **MED-1**
(proxy-aware + shared rate limiting) — worth doing before any real multi-worker
deploy. Could be "Sub-project 13: rate-limit hardening". Otherwise LOW items
(disable `/docs` in prod, CORS allow-list) as a small cleanup pass.

## Conventions for this repo
- Chat in casual Malay (bahasa pasar); code/comments/docs/commits in English.
- Per feature: branch `sub-project-N-...`, spec in `docs/superpowers/specs/`,
  plan in `docs/superpowers/plans/`, TDD, `--no-ff` merge to main, delete branch.
- Commit trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
