# Sub-project 19 — History Screen (Design)

Date: 2026-06-03

The mobile History tab becomes a real list of the user's past scans, read from
`GET /history`, with per-row delete and a clear-all action. Functional with
minimal styling — the visual design is a later pass. Branched from `main`; lives
entirely under `mobile/`. No camera.

## Scope

In: a typed `history` API wrapper (list/delete/clear, JWT bearer), the History
screen (list + per-row delete + clear-all + pull-to-refresh + empty/loading/error
states), and a small relative-time helper.

Out: barcode/image scanning (SP20), final visual design, infinite-scroll /
"load more" (fetches the latest 50 for now), swipe-to-delete (a per-row button).

## API shape (backend `/history`, JWT bearer)

`GET /history?limit=&offset=` → `list[ScanHistoryOut]` (newest first);
`DELETE /history/{id}` → 204; `DELETE /history` → 204.

```ts
type ScanHistoryOut = {
  id: number;
  scan_type: string;   // classify | barcode | image
  summary: string;
  verdict: string;     // halal | haram | shubhah
  created_at: string;  // ISO timestamp
};
```

## Files (`mobile/src/`)

- `api/history.ts` (new) — `ScanHistoryOut` type; `listHistory(limit?, offset?)`,
  `deleteHistory(id)`, `clearHistory()`, all via `request(..., { auth: "bearer" })`.
- `lib/time.ts` (new) — `timeAgo(iso, now?)` → "just now" / "5m ago" / "3h ago" /
  "2d ago". Pure and `now`-injectable for tests.
- `app/(app)/history.tsx` — replace the placeholder. `useQuery(["history"], listHistory)`
  renders a `FlatList`; each row shows the summary, the verdict (colour-coded),
  the scan type, the relative time, and a Delete button; a header "Clear all"
  button; pull-to-refresh (`refetch`); empty / loading / error states. Delete and
  clear are `useMutation`s that invalidate `["history"]` on success.

## Data flow

1. Open the tab → `useQuery` fetches the latest 50 scans (bearer; the client
   refreshes the token if needed).
2. Tap a row's Delete → `deleteHistory(id)` → invalidate `["history"]` → list
   refetches and the row drops.
3. Clear all → `clearHistory()` → list becomes empty.
4. Pull-to-refresh → `refetch()`.

## Testing (Jest + RNTL, headless)

- `api/history`: `listHistory()` calls `request("/history?limit=50&offset=0", { auth:"bearer" })` and returns the array; `deleteHistory(7)` calls `request("/history/7", { method:"DELETE", auth:"bearer" })`; `clearHistory()` calls `request("/history", { method:"DELETE", auth:"bearer" })`. (Mock `request`.)
- `lib/time.ts`: `timeAgo` returns "just now" / minutes / hours / days for known deltas with an injected `now`.
- History screen (wrapped in a `QueryClientProvider`, `@/api/history` mocked): renders rows from a mocked list (summary + verdict visible); tapping a row's Delete calls `deleteHistory` with that id; the empty list shows "No scans yet"; a failed fetch shows an error message.

Commands: `cd mobile && npm test`, `npm run typecheck`.

## Conventions

Branch `sub-project-19-history-screen` (from `main`); spec here; plan in
`docs/superpowers/plans/`; TDD (Jest); `--no-ff` merge to `main`; delete the
branch. Commit trailer:
`Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
