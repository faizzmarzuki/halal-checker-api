# History Screen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the mobile History tab into a real list of the user's past scans (`GET /history`) with per-row delete, clear-all, and pull-to-refresh.

**Architecture:** A typed `history` API wrapper (JWT bearer), a pure `timeAgo` helper, and the History screen using TanStack Query (`useQuery` for the list, `useMutation` for delete/clear, invalidating `["history"]`). Tests are Jest + RNTL (headless).

**Tech Stack:** Expo + TypeScript, expo-router, @tanstack/react-query, jest-expo + @testing-library/react-native. All under `mobile/`. Run from `mobile/`: `npm test`, `npm run typecheck`.

---

## File Structure (`mobile/src/`)

- `api/history.ts` (new) — `ScanHistoryOut`, `listHistory`, `deleteHistory`, `clearHistory`.
- `lib/time.ts` (new) — `timeAgo(iso, now?)`.
- `app/(app)/history.tsx` — replace the placeholder with the list screen.
- tests co-located under `__tests__/`.

---

## Task 1: history API wrapper + timeAgo helper

**Files:**
- Create: `mobile/src/api/history.ts`, `mobile/src/lib/time.ts`, and their tests.

- [ ] **Step 1: Write the failing tests**

Create `mobile/src/api/__tests__/history.test.ts`:

```ts
import { listHistory, deleteHistory, clearHistory } from "../history";
import { request } from "../client";

jest.mock("../client", () => {
  const actual = jest.requireActual("../client");
  return { ...actual, request: jest.fn() };
});

beforeEach(() => (request as jest.Mock).mockReset());

test("listHistory fetches the latest page with the bearer token", async () => {
  const rows = [{ id: 1, scan_type: "classify", summary: "sugar", verdict: "halal", created_at: "2026-06-03T00:00:00Z" }];
  (request as jest.Mock).mockResolvedValue(rows);
  const result = await listHistory();
  expect(result).toEqual(rows);
  expect(request).toHaveBeenCalledWith("/history?limit=50&offset=0", { auth: "bearer" });
});

test("deleteHistory deletes one row", async () => {
  (request as jest.Mock).mockResolvedValue({});
  await deleteHistory(7);
  expect(request).toHaveBeenCalledWith("/history/7", { method: "DELETE", auth: "bearer" });
});

test("clearHistory deletes all rows", async () => {
  (request as jest.Mock).mockResolvedValue({});
  await clearHistory();
  expect(request).toHaveBeenCalledWith("/history", { method: "DELETE", auth: "bearer" });
});
```

Create `mobile/src/lib/__tests__/time.test.ts`:

```ts
import { timeAgo } from "../time";

const now = Date.parse("2026-06-03T12:00:00Z");
const at = (iso: string) => timeAgo(iso, now);

test("formats relative times", () => {
  expect(at("2026-06-03T11:59:40Z")).toBe("just now"); // 20s
  expect(at("2026-06-03T11:55:00Z")).toBe("5m ago");
  expect(at("2026-06-03T09:00:00Z")).toBe("3h ago");
  expect(at("2026-06-01T12:00:00Z")).toBe("2d ago");
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd mobile && npm test -- history time`
Expected: FAIL — `Cannot find module '../history'` / `'../time'`.

- [ ] **Step 3: Create the helpers**

Create `mobile/src/lib/time.ts`:

```ts
export function timeAgo(iso: string, now: number = Date.now()): string {
  const diff = Math.max(0, now - new Date(iso).getTime());
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}
```

Create `mobile/src/api/history.ts`:

```ts
import { request } from "./client";

export type ScanHistoryOut = {
  id: number;
  scan_type: string; // classify | barcode | image
  summary: string;
  verdict: string; // halal | haram | shubhah
  created_at: string; // ISO timestamp
};

export function listHistory(limit = 50, offset = 0): Promise<ScanHistoryOut[]> {
  return request<ScanHistoryOut[]>(`/history?limit=${limit}&offset=${offset}`, { auth: "bearer" });
}

export function deleteHistory(id: number): Promise<unknown> {
  return request(`/history/${id}`, { method: "DELETE", auth: "bearer" });
}

export function clearHistory(): Promise<unknown> {
  return request("/history", { method: "DELETE", auth: "bearer" });
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd mobile && npm test -- history time` → PASS. `npm run typecheck` → no errors.

- [ ] **Step 5: Commit**

```bash
git add mobile/src/api/history.ts mobile/src/lib/time.ts mobile/src/api/__tests__/history.test.ts mobile/src/lib/__tests__/time.test.ts
git commit -m "feat(mobile): history API wrapper + relative-time helper

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: History screen

**Files:**
- Modify: `mobile/src/app/(app)/history.tsx`
- Test: `mobile/src/app/(app)/__tests__/history.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `mobile/src/app/(app)/__tests__/history.test.tsx`:

```tsx
import React from "react";
import { render, fireEvent, waitFor } from "@testing-library/react-native";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import HistoryScreen from "../history";
import * as api from "@/api/history";

jest.mock("@/api/history");

let client: QueryClient;
beforeEach(() => {
  jest.resetAllMocks();
  client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  });
});
afterEach(() => client.clear());

function wrap(ui: React.ReactElement) {
  return <QueryClientProvider client={client}>{ui}</QueryClientProvider>;
}

const rows = [
  { id: 1, scan_type: "classify", summary: "sugar, lard", verdict: "haram", created_at: "2026-06-03T11:00:00Z" },
  { id: 2, scan_type: "barcode", summary: "0123456789 (Nutella)", verdict: "halal", created_at: "2026-06-03T10:00:00Z" },
];

test("renders the user's scans", async () => {
  (api.listHistory as jest.Mock).mockResolvedValue(rows);
  const { getByText, getAllByTestId } = render(wrap(<HistoryScreen />));
  await waitFor(() => expect(getAllByTestId("history-row")).toHaveLength(2));
  expect(getByText("sugar, lard")).toBeTruthy();
});

test("deleting a row calls deleteHistory with its id", async () => {
  (api.listHistory as jest.Mock).mockResolvedValue(rows);
  (api.deleteHistory as jest.Mock).mockResolvedValue({});
  const { getByTestId } = render(wrap(<HistoryScreen />));
  await waitFor(() => getByTestId("delete-1"));
  fireEvent.press(getByTestId("delete-1"));
  expect(api.deleteHistory).toHaveBeenCalledWith(1);
});

test("an empty list shows a placeholder", async () => {
  (api.listHistory as jest.Mock).mockResolvedValue([]);
  const { getByTestId } = render(wrap(<HistoryScreen />));
  await waitFor(() => expect(getByTestId("empty")).toBeTruthy());
});

test("a load error is shown", async () => {
  (api.listHistory as jest.Mock).mockRejectedValue(new Error("Server error"));
  const { findByTestId } = render(wrap(<HistoryScreen />));
  expect((await findByTestId("error")).props.children).toContain("Server error");
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd mobile && npm test -- history.test`
Expected: FAIL — the placeholder `history.tsx` has no list/testIDs.

- [ ] **Step 3: Replace the History screen**

Replace `mobile/src/app/(app)/history.tsx` with:

```tsx
import React from "react";
import { View, Text, Button, FlatList, ActivityIndicator, RefreshControl } from "react-native";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listHistory, deleteHistory, clearHistory, type ScanHistoryOut } from "@/api/history";
import { timeAgo } from "@/lib/time";

const COLOR: Record<string, string> = { halal: "#1a7f37", haram: "#cf222e", shubhah: "#9a6700" };

function Row({ item, onDelete }: { item: ScanHistoryOut; onDelete: (id: number) => void }) {
  return (
    <View testID="history-row" style={{ borderBottomWidth: 1, borderColor: "#eee", paddingVertical: 10, gap: 4 }}>
      <Text style={{ fontWeight: "700", color: COLOR[item.verdict] ?? "#333" }}>{item.verdict.toUpperCase()}</Text>
      <Text numberOfLines={2}>{item.summary}</Text>
      <Text style={{ color: "#777", fontSize: 12 }}>{item.scan_type} · {timeAgo(item.created_at)}</Text>
      <Button testID={`delete-${item.id}`} title="Delete" onPress={() => onDelete(item.id)} />
    </View>
  );
}

export default function HistoryScreen() {
  const qc = useQueryClient();
  const query = useQuery({ queryKey: ["history"], queryFn: () => listHistory() });
  const del = useMutation({
    mutationFn: (id: number) => deleteHistory(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["history"] }),
  });
  const clear = useMutation({
    mutationFn: () => clearHistory(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["history"] }),
  });

  if (query.isLoading) {
    return <View style={{ flex: 1, alignItems: "center", justifyContent: "center" }}><ActivityIndicator /></View>;
  }
  if (query.isError) {
    return (
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center", padding: 24 }}>
        <Text testID="error" style={{ color: "red" }}>{(query.error as Error)?.message ?? "Failed to load history"}</Text>
      </View>
    );
  }

  const data = query.data ?? [];
  return (
    <FlatList
      testID="history-list"
      data={data}
      keyExtractor={(it) => String(it.id)}
      contentContainerStyle={{ padding: 16 }}
      refreshControl={<RefreshControl refreshing={query.isFetching} onRefresh={() => query.refetch()} />}
      ListHeaderComponent={data.length ? <Button testID="clear-all" title="Clear all" onPress={() => clear.mutate()} /> : null}
      ListEmptyComponent={<Text testID="empty" style={{ textAlign: "center", marginTop: 40, color: "#777" }}>No scans yet</Text>}
      renderItem={({ item }) => <Row item={item} onDelete={del.mutate} />}
    />
  );
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd mobile && npm test -- history.test` → PASS. `npm run typecheck` → no errors.

- [ ] **Step 5: Commit**

```bash
git add "mobile/src/app/(app)/history.tsx" "mobile/src/app/(app)/__tests__/history.test.tsx"
git commit -m "feat(mobile): History screen (list + delete + clear + refresh)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Full verification + checkpoint

- [ ] **Step 1: Full verification**

Run from `mobile/`: `npm test` (all green) and `npm run typecheck` (clean). Report counts.

- [ ] **Step 2: Update the checkpoint**

Edit `docs/CHECKPOINT.md`: refresh the branch section (SP18 merged; SP19 in flight); update the mobile test count; add an SP19 entry under "What's built" (the History screen + `history` API + `timeAgo`); set the next step to SP20 (barcode + image, camera — pending the user's on-device testing and visual design).

- [ ] **Step 3: Commit**

```bash
git add docs/CHECKPOINT.md docs/superpowers/plans/2026-06-03-history-screen.md
git commit -m "docs(mobile): SP19 done — History screen

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Notes for the implementer

- `jest.mock("../client", ...)` keeps the real exports and only mocks `request` (consistent with `scan.test.ts`).
- History screen tests wrap in a `QueryClientProvider` with `retry: false` + `gcTime: 0` and `client.clear()` in `afterEach` (test hygiene, matching the Home test).
- `request` returns `{}` for a 204 (its `resp.json().catch(() => ({}))`), so `deleteHistory`/`clearHistory` resolve fine.
- The app cannot be run here; "done" = `npm test` green + `npm run typecheck` clean. On-device is the user's check.
- Every commit message ends with the trailer:
  `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`
- This branch is from `main`; final `--no-ff` merge to `main` after review.
