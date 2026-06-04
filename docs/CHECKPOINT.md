# Project Checkpoint — 2026-06-03

Resume point for the Halal Checker API. Tell Claude "refer to docs/CHECKPOINT.md"
to pick up exactly here.

## Where things stand
- **SP11–SP24 are merged into `main`** (PRs #1–#14 closed; branches deleted).
  QA security track is done bar infra-gated items (see Open work); product so far:
  scan history (SP16, backend) + the mobile app (foundation through barcode scan).
  Stacked-PR footgun, learned the hard way: a stacked PR's base is the branch
  below it, so merging it lands changes on that branch, not `main` — retarget
  each PR's base to `main` (in order) before merging.
- **In flight:** `sp25-image-scan` (from `main`) — photo scan: take/pick an image
  and OCR it via `/scan-image`. Implemented + tested locally; not yet PR'd/merged.
- Private GitHub repo: `https://github.com/faizzmarzuki/halal-checker-api`.
  `gh` CLI is NOT installed locally — PRs are created/merged via the GitHub REST
  API using the stored git credential.
- **Tests:** backend `188 passing` (0 skipped now that the `ocr` extra is
  installed — Pillow + pytesseract), `.venv/Scripts/python -m pytest -q`.
  Mobile: `46 passing`, `cd mobile && npm test` (also `npm run typecheck`).
- **On-device bugfixes (merged, PR #16):** three issues found testing on a real
  phone — (1) **non-Latin ingredients reported as confident HALAL**: `normalize()`
  strips non-`[a-z0-9]`, so e.g. Korean became `""`, was dropped, and
  `_aggregate([])` fell through to HALAL. Fixed so unreadable input → SHUBHAH
  (`Source.NONE`, low conf) and an empty result set → SHUBHAH, never HALAL.
  (2) **barcode never scanned**: `expo-camera` v17 defaults `autoFocus='off'`;
  set `autofocus="on"` on the live `CameraView`. (3) **OCR always 422**: the
  backend env was missing `Pillow`/`pytesseract`/the `tesseract` binary. Now
  installed: `pip install -e ".[ocr]"` done; Tesseract v5.5.0 engine installed at
  `C:\Program Files\Tesseract-OCR` (only `eng`+`osd` language data). It was NOT on
  PATH, so `ocr.py` now auto-detects the binary (`_resolve_tesseract_cmd`:
  `HALAL_TESSERACT_CMD` env → PATH → common Windows install dirs) and sets
  `pytesseract.tesseract_cmd` — verified OCR works end-to-end (PR #17). Note:
  non-English labels need extra Tesseract language packs and/or translation
  (Ollama, not running) to classify beyond SHUBHAH; OCR'ing a *nutrition table*
  (not an ingredient list) won't yield meaningful ingredient verdicts.
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
- **SP17 Mobile Foundation** — Expo **SDK 54** (scaffolded on 56, pinned 56→55
  in SP21, then 55→54 in SP22 because the user's latest Expo Go only supports 54)
  + TS, expo-router
  (routes under `src/app/`, `@/` alias for `src/`). Typed `fetch` client with JWT auto-refresh
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
- **SP18 Classify Scan Screen** — the Home tab is a "paste ingredients"
  classifier: `src/api/scan.ts` (`classify`, typed `VerdictOut`) posts to
  `/classify` with the auto-managed `X-API-Key`; a reusable
  `src/components/VerdictResult.tsx` renders the verdict + per-ingredient
  breakdown + disclaimer; `app/(app)/index.tsx` uses a TanStack Query mutation.
  Includes **API-key 401 auto-recovery** (`withApiKeyRecovery` + `clearApiKey` →
  re-mint via `ensureApiKey` → retry once), closing the SP17 known gap. Functional
  only; styling minimal.
- **SP19 History Screen** — the History tab lists the user's scans from
  `/history` (`src/api/history.ts`: `listHistory`/`deleteHistory`/`clearHistory`,
  bearer) with per-row delete, a clear-all header, pull-to-refresh, and
  empty/loading/error states via TanStack Query (`useQuery`/`useMutation`
  invalidating `["history"]`). `src/lib/time.ts` `timeAgo` shows relative times.
  Functional only.
- **SP20 Web Storage** — `src/auth/session.ts` uses `localStorage` on web
  (`Platform.OS === "web"`), secure-store on native. Without it the app hung on
  the loading spinner on web (expo-secure-store is native-only). Unblocked
  web-browser testing.
- **SP23 Design System + Restyle** — cream/light design system: `src/theme/tokens.ts`
  (colours / spacing / radii / type + `verdictColor`) and reusable
  `src/components/ui/` primitives (`Screen`, `Text`/`Heading`, `Button` pill with
  primary/secondary/accent + loading, underline `Input`, `Card`). Every screen
  (auth / Home / VerdictResult / History / Settings + tab bar) rebuilt on these —
  bold ALL-CAPS headings, pill buttons, terracotta/green accents, verdict colours.
  All test IDs preserved so the existing tests stay green (34 total with the new
  tokens/ui tests). Custom display font is a fast-follow; camera screens next.
- **SP24 Barcode Scan** — `scanBarcode` in `src/api/scan.ts` (POST `/scan-barcode`,
  apiKey auth + 401 recovery; `BarcodeVerdictOut`). New screen
  `app/(app)/barcode.tsx` (registered hidden via `href: null`, pushed from a Home
  "Scan barcode" button): `expo-camera` `CameraView` live scan (EAN/UPC) with a
  `scanned` guard + permission gate, plus a manual barcode `Input` fallback; both
  feed one mutation → `VerdictResult` (+ product name) / error / "Scan again".
  Tests mock `expo-camera`; 38 mobile tests total.
- **SP25 Image/Photo Scan** — `scanImage(uri)` in `src/api/scan.ts` uploads the
  raw image bytes to `/scan-image` (apiKey auth + 401 recovery; `ImageVerdictOut`
  = `VerdictOut` + `extracted_text`). Because `request()` is JSON-only, it streams
  the file via `expo-file-system`'s **`uploadAsync`** (imported from
  `expo-file-system/legacy` — the root export has no `uploadAsync`) with
  `FileSystemUploadType.BINARY_CONTENT` + `X-API-Key`. New screen
  `app/(app)/photo.tsx` (hidden via `href: null`, pushed from a Home "Scan photo"
  button): "Take photo" (`expo-image-picker` `launchCameraAsync` + camera-perm
  gate) and "Choose from gallery" (`launchImageLibraryAsync`, system picker, no
  explicit perm), shows a preview, runs one mutation → `VerdictResult`
  (+ OCR'd text) / error / "Scan another". Tests mock `expo-image-picker` +
  `expo-file-system/legacy`; 45 mobile tests total. Added `expo-image-picker`
  (~17.0.11, SDK-54-aligned).
- **SP26 Backend deploy to Render** — committed `render.yaml` Blueprint for Render:
  Docker web service (installs `tesseract-ocr` in image for `/scan-image` in prod)
  + managed PostgreSQL database. New `postgres` extra in `pyproject.toml`
  (`psycopg[binary]>=3.1`); `_normalize_db_url` in `db.py` adapts the Render
  Postgres URL scheme to psycopg3 (changes `postgresql://` → `postgresql+psycopg://`).
  Blueprint sets `HALAL_ENV=production` (docs hidden, rate limiting enforced),
  `HALAL_RATE_LIMIT=60`, `HALAL_JWT_SECRET` auto-generated by Render, and wires
  `HALAL_DATABASE_URL` from managed Postgres. Two manual env vars (`HALAL_ADMIN_EMAILS`,
  `HALAL_CORS_ORIGINS`) declared `sync: false` — operator fills them on the Render
  dashboard. Operator still has to click through Blueprint, fill those env vars,
  then point `mobile/.env`'s `EXPO_PUBLIC_API_URL` at the Render service URL.
- **SP21/SP22 Expo SDK pin** — `create-expo-app` scaffolded on SDK 56 (the npm
  `latest`), but the user's latest **Expo Go only supports SDK 54**. Pinned
  56→55 (SP21) then 55→54 (SP22) via `expo install --fix` + realigned devDeps
  (`jest-expo`, `react-test-renderer`/`@types/react` to match the SDK's React).
  Jest runs serially with a higher timeout + `--forceExit` (`maxWorkers: 1`,
  `testTimeout: 20000`, `test: "jest --forceExit"`) — the RN test env leaks
  handles that accumulate across suites (each passes alone). Verified on SDK 54:
  30 tests, tsc clean, `expo export --platform web` bundles all routes. To bump
  the SDK later (when Expo Go supports it): `npx expo install expo@<ver> --fix`,
  realign devDeps, re-run.

Dev-run notes (for testing): start the backend with `HALAL_JWT_SECRET` set and
bind `0.0.0.0` (`--host 0.0.0.0 --port 8000`). The mobile app reads
`EXPO_PUBLIC_API_URL` from `mobile/.env` (gitignored). **On a device** use the
dev machine's LAN IP (`http://192.168.100.21:8000`) and allow port 8000 through
Windows Firewall. **In a browser** use `http://localhost:8000` (Chrome blocks
localhost→LAN-IP) and set the backend's `HALAL_CORS_ORIGINS` to the Expo web
origin (`http://localhost:8081`). A stale `halal_scanner.db` from an early
project phase can cause 500s (missing columns) — delete it so `create_all`
rebuilds the current schema.

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
All four core scan flows exist on mobile (classify, history, barcode, photo).
Backend deploy to Render is now available via committed `render.yaml` Blueprint;
the operator's next manual step is to apply the Blueprint in the Render dashboard
and fill the two sync-false env vars. Candidate next steps for the app/backend:
- **Custom heavy display font** (`expo-font`) to land the cream/editorial vibe.
- On-device pass of the camera screens (barcode + photo) — both shipped untested
  on a physical device (the user chose to keep building first).

Backend backlog (infra-gated/accepted only): MED-1 (Redis shared limiter, when
scaling out), MED-3 (LLM prompt-injection, accepted), HSTS (proxy).

## Conventions for this repo
- Chat in casual Malay (bahasa pasar); code/comments/docs/commits in English.
- Per feature: branch `sub-project-N-...`, spec in `docs/superpowers/specs/`,
  plan in `docs/superpowers/plans/`, TDD, `--no-ff` merge to main, delete branch.
- Commit trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
