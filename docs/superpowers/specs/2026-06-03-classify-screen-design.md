# Sub-project 18 — Classify Scan Screen (Design)

Date: 2026-06-03

The first scanning feature in the mobile app: turn the Home tab into a
"paste ingredients" classifier. The user types/pastes an ingredient list, the app
calls `POST /classify` with the auto-managed `X-API-Key`, and shows the verdict
plus a per-ingredient breakdown. Functional with minimal styling — the visual
design is a later pass. Branched from `main`; lives entirely under `mobile/`.

## Scope

In: a `classify` scan API wrapper, a reusable `VerdictResult` component, the Home
screen scan UI, and **API-key 401 auto-recovery** (a revoked/stale key is
re-minted and the scan retried once).

Out: barcode and image scanning (camera — SP19), the history screen (SP20), and
final visual design.

## API response shapes (from the backend `schemas.py`)

```ts
type IngredientOut = {
  input: string; canonical: string; status: string;   // halal | haram | shubhah
  source: string; confidence: string; reason: string; citation: string;
};
type VerdictOut = {
  verdict: string;            // halal | haram | shubhah
  ingredients: IngredientOut[];
  summary: string;
  disclaimer: string;
};
```

## Components & files (`mobile/src/`)

- `api/scan.ts` — typed `classify(ingredients, opts?) => Promise<VerdictOut>`. Posts
  to `/classify` with `auth: "apiKey"`. Wraps the call in `withApiKeyRecovery`
  (below). Defines/exports the `VerdictOut` / `IngredientOut` types.
- `auth/session.ts` — add `clearApiKey()` (delete just the `hs.apiKey` entry), used
  by the recovery path.
- `components/VerdictResult.tsx` — presentational, reused by SP19. Given a
  `VerdictOut`, renders: the overall verdict (coloured by status — halal green,
  haram red, shubhah amber), the summary, a list of ingredient rows
  (`input` → `status` + `reason`), and the disclaimer.
- `app/(app)/index.tsx` (Home) — a multiline `TextInput` (one ingredient per line,
  commas also split), a "Check" button, a TanStack Query `useMutation` calling
  `classify`, and conditional rendering: idle prompt / spinner / `<VerdictResult>` /
  error message.

## API-key 401 auto-recovery

Closes the SP17 known gap. A small helper in `api/scan.ts`:

```ts
async function withApiKeyRecovery<T>(call: () => Promise<T>): Promise<T> {
  try {
    return await call();
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) {
      await clearApiKey();   // drop the stale/revoked key
      await ensureApiKey();  // re-mint via /keys (JWT; bearer refresh still applies)
      return await call();   // retry once
    }
    throw e;
  }
}
```

No circular import: `scan.ts` → `client` + `keys`; `keys` → `client`. `ensureApiKey`
itself uses a bearer call, so an expired JWT during re-minting is handled by the
client's existing refresh. If recovery still fails (user truly logged out), the
error surfaces and the UI shows it.

## Data flow

1. User enters ingredients; the screen parses on newlines/commas, dropping blanks.
2. `useMutation(() => classify(parsed))` → spinner while pending.
3. Success → render `<VerdictResult result={data} />`. (The scan is recorded
   server-side per SP16, so it will appear in the history screen later.)
4. Error → show the `ApiError` message (e.g. validation 422, or auth failure after
   recovery) below the button.

## Testing (Jest + RNTL, headless)

- `api/scan.classify`: calls `request("/classify", { method:"POST", auth:"apiKey", body:{ ingredients, use_gemma, translate } })` and returns the `VerdictOut` (mock `request`).
- `withApiKeyRecovery`: a first `ApiError(401)` triggers `clearApiKey` + `ensureApiKey` then a successful retry; a non-401 error rethrows without recovery; a second 401 after recovery propagates.
- `VerdictResult`: renders the verdict text, at least one ingredient row (input + status + reason), the summary, and the disclaimer from a sample `VerdictOut`.
- Home screen: typing ingredients then pressing Check calls `classify` and renders `VerdictResult`; an empty input does not call the API; an API error shows a message. (Mock `@/api/scan`.)

Commands: `cd mobile && npm test`, `npm run typecheck`.

## Conventions

Branch `sub-project-18-classify-screen` (from `main`); spec here; plan in
`docs/superpowers/plans/`; TDD (Jest); `--no-ff` merge to `main`; delete the
branch. Commit trailer:
`Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
