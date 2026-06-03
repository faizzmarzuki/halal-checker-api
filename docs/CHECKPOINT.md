# Project Checkpoint — 2026-06-03

Resume point for the Halal Checker API. Tell Claude "refer to docs/CHECKPOINT.md"
to pick up exactly here.

## Where things stand
- **SP11–SP16 are merged into `main`** (PRs #1–#6 closed; branches deleted). The
  whole QA security track is done bar infra-gated items (see Open work), plus the
  first product feature (scan history, SP16).
  Stacked-PR footgun, learned the hard way: a stacked PR's base is the branch
  below it, so merging it lands changes on that branch, not `main` — retarget
  each PR's base to `main` (in order) before merging.
- **In flight:** `sub-project-17-mobile-foundation` (from `main`) — the first
  piece of the React Native + Expo mobile app, under `mobile/`.
- Private GitHub repo: `https://github.com/faizzmarzuki/halal-checker-api`.
  `gh` CLI is NOT installed locally — PRs are created/merged via the GitHub REST
  API using the stored git credential.
- **Tests:** backend `179 passing` (+2 skipped — Pillow-gated OCR; install the
  `ocr` extra), `.venv/Scripts/python -m pytest -q`. Mobile: `13 passing`,
  `cd mobile && npm test` (also `npm run typecheck`).
- **Run the API:** set `HALAL_JWT_SECRET` then
  `.venv/Scripts/python -m uvicorn halal_scanner.api.app:app --reload` → http://localhost:8000/docs
- **Run the app:** `cd mobile && EXPO_PUBLIC_API_URL=<reachable-api> npx expo start`
  (LAN IP or `--tunnel`); open in Expo Go. The app can't be run from this
  environment — on-device checks are the user's. See `mobile/README.md`.

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
- **SP13 Rate-Limit Hardening** — `RateLimiter` evicts stale keys periodically
  (`evict_every`, `_maybe_evict`) to bound memory; new `client_ip()` keys the
  limiter on a trusted `X-Forwarded-For` (left-most entry) only when
  `HALAL_TRUST_PROXY` is set, else the socket peer. (Redis/shared-across-workers
  limiter still deferred.)
- **SP14 Prod-Exposure Cleanup** — `/docs`, `/redoc`, `/openapi.json` disabled
  when `HALAL_ENV` is `prod`/`production` (`_docs_kwargs`); opt-in CORS allow-list
  via `HALAL_CORS_ORIGINS` (`_parse_cors_origins` + `CORSMiddleware`,
  `allow_credentials=False`), default-closed when unset.
- **SP15 Fail-Closed in Production** — `_require_prod_posture` refuses to start
  when `HALAL_ENV=production` unless `HALAL_RATE_LIMIT` is a positive integer
  (called at import time beside the JWT-secret guard). Completes HIGH-1 (auth
  half was SP8). Default `dev` = no-op.

First product feature (post-hardening):
- **SP16 Scan History** — every scan is recorded per account (best-effort): new
  `ScanHistory` model + `history` service (`record`/`list_for_user`/`delete_one`/
  `delete_all`); `require_api_key` was replaced by `current_api_key` (returns the
  key row) so the scanning endpoints attribute each scan to `key.user_id` via a
  `_record_scan` helper (a recording failure never breaks a scan). JWT-protected
  `/history` router: `GET /history` (paginated, newest-first), `DELETE /history/{id}`,
  `DELETE /history` (clear all); deletes are audit-logged. Lightweight rows:
  scan_type / summary / verdict / created_at. Ready for the upcoming frontend.

Mobile app (`mobile/`, React Native + Expo, iOS + Android):
- **SP17 Mobile Foundation** — Expo SDK 56 + TS, expo-router (routes under
  `src/app/`, `@/` alias for `src/`). Typed `fetch` client with JWT auto-refresh
  (`src/api/client.ts`), secure session in expo-secure-store
  (`src/auth/session.ts`), auth flow (register/login/logout, `AuthProvider`), an
  **auto-managed API key** (`ensureApiKey` — created on login, stored, used for
  scanning later), and an authed tab shell (Home/History/Settings placeholders)
  behind a session navigation guard. Jest + RNTL tests (12). Functional only —
  visual design is a later sub-project. App not runnable from this env; on-device
  is the user's check (`EXPO_PUBLIC_API_URL` → reachable backend). Notable scaffold
  adaptations vs the plan: the SDK-56 default template puts routes in `src/app/`
  (not `app/`); trimmed the template's example UI; pinned `react-test-renderer` to
  the installed React; set tsconfig `types: [jest, node, react]`.

## Two auth layers (don't confuse)
- **JWT Bearer** → `/auth/*`, `/keys`, `/admin/*` (humans managing accounts).
- **`X-API-Key`** → scanning endpoints (machines calling the classifier).

## Key env vars
`HALAL_JWT_SECRET` (required), `HALAL_DATABASE_URL`, `HALAL_ACCESS_TTL`,
`HALAL_REFRESH_TTL`, `HALAL_ADMIN_EMAILS`, `HALAL_RATE_LIMIT`, `HALAL_RATE_WINDOW`,
`HALAL_TRUST_PROXY` (set `1`/`true`/`yes` ONLY behind your own proxy → trust
`X-Forwarded-For` for rate-limit keying; default off = socket peer),
`HALAL_ENV` (set `prod`/`production` → hide docs AND require `HALAL_RATE_LIMIT`
to be a positive integer or the app refuses to start; default `dev` = docs on,
no posture check), `HALAL_CORS_ORIGINS` (comma-separated allow-list;
default empty = no CORS / browsers block cross-origin).

## Open work (NOT done yet) — from the QA/security pass
Full details in `QA_SECURITY_FINDINGS.txt` (kept local / gitignored, not on GitHub).
Already fixed: HIGH-1 (scanning auth secure-by-default, via SP8), L-4 (audit log, via SP10),
HIGH-2 (request-size limits, via SP11), HIGH-3 (barcode validation/SSRF guard, via SP11),
MED-2 (image decompression-bomb guard, via SP12), L-1 (security headers, via SP12),
L-5 (`extra="forbid"` on scanning models, via SP12; auth models already had it).
Already mitigated by design (no code change): MED-4 (constant-time API-key compare) —
SP8 replaced the old plaintext key compare with a SHA-256 hash + DB lookup, so there
is no exploitable timing side channel.
Already fixed (cont.): MED-1 in-process half (proxy-aware IP + stale-key
eviction, via SP13); L-2 (docs/schema disabled in prod, via SP14); L-3 (explicit
opt-in CORS allow-list, via SP14); HIGH-1 fully closed (auth always-on via SP8 +
prod fail-closed rate limit via SP15).
Still open:
- **MED-1 (remaining)** — limiter is still per-process: not shared across uvicorn
  workers/replicas, so the effective limit = configured × worker count. Needs a
  Redis-backed (or API-gateway) limiter for scale-out. Deferred until a real
  multi-worker deploy.
- **MED-3** — LLM prompt-injection note (accepted risk: rulebook is authority,
  Gemma is low-confidence + disclaimed).
- **LOW** — HSTS at the proxy (the rest of the LOW items are done).

## Suggested next step
**SP18 — Mobile scanning screens** (classify → barcode camera → image). The
foundation (SP17) provides auth, the auto-managed API key, and the tab shell, so
SP18 builds the Home tab's scan UI on the `/classify` etc. endpoints (the client's
`apiKey` auth path is already plumbed). Then **SP19 — History** screen on
`/history`. The visual **design/vibe is still to be shared** by the user; screens
are functional until then, with a design pass after.

Backend backlog (infra-gated/accepted only): MED-1 (Redis shared limiter, when
scaling out), MED-3 (LLM prompt-injection, accepted), HSTS (proxy). A backend
**deploy** sub-project is also pending so the app has a stable URL (currently
local-only via LAN/tunnel).

## Conventions for this repo
- Chat in casual Malay (bahasa pasar); code/comments/docs/commits in English.
- Per feature: branch `sub-project-N-...`, spec in `docs/superpowers/specs/`,
  plan in `docs/superpowers/plans/`, TDD, `--no-ff` merge to main, delete branch.
- Commit trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
