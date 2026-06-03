# Classify Scan Screen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the mobile Home tab into a "paste ingredients" classifier that calls `/classify` and shows the verdict + per-ingredient breakdown, with API-key 401 auto-recovery.

**Architecture:** A typed `scan` API wrapper (`auth: "apiKey"`, wrapped in a re-mint-on-401 recovery helper), a reusable `VerdictResult` component, and the Home screen using a TanStack Query mutation. Tests are Jest + React Native Testing Library (headless).

**Tech Stack:** Expo + TypeScript, expo-router, @tanstack/react-query, jest-expo + @testing-library/react-native. All under `mobile/`. Run from `mobile/`: `npm test`, `npm run typecheck`.

---

## File Structure (under `mobile/src/`)

- `auth/session.ts` — add `clearApiKey()`.
- `api/scan.ts` (new) — `VerdictOut`/`IngredientOut` types, `classify()`, `withApiKeyRecovery()`.
- `components/VerdictResult.tsx` (new) — presentational verdict view (reused by SP19).
- `app/(app)/index.tsx` — replace the Home placeholder with the scan UI.
- tests co-located under `__tests__/`.

---

## Task 1: scan API wrapper + clearApiKey + 401 recovery

**Files:**
- Modify: `mobile/src/auth/session.ts`
- Create: `mobile/src/api/scan.ts`, `mobile/src/api/__tests__/scan.test.ts`

- [ ] **Step 1: Write the failing tests**

Create `mobile/src/api/__tests__/scan.test.ts`:

```ts
import { classify } from "../scan";
import { request, ApiError } from "../client";
import * as keys from "../keys";
import * as session from "../../auth/session";

jest.mock("../client", () => {
  const actual = jest.requireActual("../client");
  return { ...actual, request: jest.fn() };
});
jest.mock("../keys");
jest.mock("../../auth/session");

const verdict = {
  verdict: "haram",
  ingredients: [
    { input: "lard", canonical: "lard", status: "haram", source: "rulebook",
      confidence: "high", reason: "pork fat", citation: "x" },
  ],
  summary: "Contains haram ingredients.",
  disclaimer: "Not a religious ruling.",
};

beforeEach(() => {
  jest.resetAllMocks();
  (keys.ensureApiKey as jest.Mock).mockResolvedValue("hsk_new");
  (session.clearApiKey as jest.Mock).mockResolvedValue(undefined);
});

test("classify posts ingredients with the api key and returns the verdict", async () => {
  (request as jest.Mock).mockResolvedValue(verdict);
  const result = await classify(["lard"]);
  expect(result).toEqual(verdict);
  expect(request).toHaveBeenCalledWith("/classify", {
    method: "POST",
    auth: "apiKey",
    body: { ingredients: ["lard"], use_gemma: true, translate: false },
  });
});

test("a 401 re-mints the key and retries once", async () => {
  (request as jest.Mock)
    .mockRejectedValueOnce(new ApiError(401, "bad key"))
    .mockResolvedValueOnce(verdict);
  const result = await classify(["lard"]);
  expect(result).toEqual(verdict);
  expect(session.clearApiKey).toHaveBeenCalled();
  expect(keys.ensureApiKey).toHaveBeenCalled();
  expect(request).toHaveBeenCalledTimes(2);
});

test("a non-401 error rethrows without recovery", async () => {
  (request as jest.Mock).mockRejectedValue(new ApiError(422, "bad input"));
  await expect(classify([""])).rejects.toMatchObject({ status: 422 });
  expect(keys.ensureApiKey).not.toHaveBeenCalled();
});

test("a second 401 after recovery propagates", async () => {
  (request as jest.Mock).mockRejectedValue(new ApiError(401, "still bad"));
  await expect(classify(["lard"])).rejects.toMatchObject({ status: 401 });
  expect(request).toHaveBeenCalledTimes(2);
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd mobile && npm test -- scan`
Expected: FAIL — `Cannot find module '../scan'`.

- [ ] **Step 3: Add `clearApiKey` to the session store**

In `mobile/src/auth/session.ts`, add after `clearSession`:

```ts
export async function clearApiKey(): Promise<void> {
  await SecureStore.deleteItemAsync(KEYS.apiKey);
}
```

- [ ] **Step 4: Create the scan wrapper**

Create `mobile/src/api/scan.ts`:

```ts
import { request, ApiError } from "./client";
import { ensureApiKey } from "./keys";
import { clearApiKey } from "../auth/session";

export type IngredientOut = {
  input: string;
  canonical: string;
  status: string; // halal | haram | shubhah
  source: string;
  confidence: string;
  reason: string;
  citation: string;
};

export type VerdictOut = {
  verdict: string; // halal | haram | shubhah
  ingredients: IngredientOut[];
  summary: string;
  disclaimer: string;
};

export type ClassifyOpts = { useGemma?: boolean; translate?: boolean };

// Scanning uses the auto-managed X-API-Key. If the key is stale/revoked the call
// 401s; drop it, re-mint via /keys, and retry the scan once (closes the SP17 gap).
async function withApiKeyRecovery<T>(call: () => Promise<T>): Promise<T> {
  try {
    return await call();
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) {
      await clearApiKey();
      await ensureApiKey();
      return await call();
    }
    throw e;
  }
}

export function classify(ingredients: string[], opts: ClassifyOpts = {}): Promise<VerdictOut> {
  return withApiKeyRecovery(() =>
    request<VerdictOut>("/classify", {
      method: "POST",
      auth: "apiKey",
      body: {
        ingredients,
        use_gemma: opts.useGemma ?? true,
        translate: opts.translate ?? false,
      },
    }),
  );
}
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd mobile && npm test -- scan` → PASS. `npm run typecheck` → no errors.

- [ ] **Step 6: Commit**

```bash
git add mobile/src/auth/session.ts mobile/src/api/scan.ts mobile/src/api/__tests__/scan.test.ts
git commit -m "feat(mobile): classify scan wrapper with API-key 401 recovery

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: VerdictResult component

**Files:**
- Create: `mobile/src/components/VerdictResult.tsx`, `mobile/src/components/__tests__/VerdictResult.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `mobile/src/components/__tests__/VerdictResult.test.tsx`:

```tsx
import React from "react";
import { render } from "@testing-library/react-native";
import VerdictResult from "../VerdictResult";
import type { VerdictOut } from "@/api/scan";

const sample: VerdictOut = {
  verdict: "haram",
  ingredients: [
    { input: "lard", canonical: "lard", status: "haram", source: "rulebook", confidence: "high", reason: "pork fat", citation: "x" },
    { input: "sugar", canonical: "sugar", status: "halal", source: "rulebook", confidence: "high", reason: "permitted", citation: "y" },
  ],
  summary: "Contains haram ingredients.",
  disclaimer: "Not a religious ruling.",
};

test("renders the verdict, ingredients, and disclaimer", () => {
  const { getByTestId, getAllByTestId, getByText } = render(<VerdictResult result={sample} />);
  expect(getByTestId("verdict").props.children).toContain("HARAM");
  expect(getAllByTestId("ingredient")).toHaveLength(2);
  expect(getByText("pork fat")).toBeTruthy();
  expect(getByTestId("disclaimer").props.children).toContain("Not a religious ruling.");
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd mobile && npm test -- VerdictResult`
Expected: FAIL — `Cannot find module '../VerdictResult'`.

- [ ] **Step 3: Create the component**

Create `mobile/src/components/VerdictResult.tsx`:

```tsx
import React from "react";
import { View, Text } from "react-native";
import type { VerdictOut } from "@/api/scan";

const COLOR: Record<string, string> = {
  halal: "#1a7f37",
  haram: "#cf222e",
  shubhah: "#9a6700",
};

export default function VerdictResult({ result }: { result: VerdictOut }) {
  return (
    <View style={{ gap: 12 }}>
      <Text testID="verdict" style={{ fontSize: 22, fontWeight: "700", color: COLOR[result.verdict] ?? "#333" }}>
        {result.verdict.toUpperCase()}
      </Text>
      <Text>{result.summary}</Text>
      <View style={{ gap: 8 }}>
        {result.ingredients.map((ing, i) => (
          <View key={i} testID="ingredient" style={{ borderTopWidth: 1, borderColor: "#eee", paddingTop: 6 }}>
            <Text style={{ fontWeight: "600" }}>
              {ing.input} — <Text style={{ color: COLOR[ing.status] ?? "#333" }}>{ing.status}</Text>
            </Text>
            <Text style={{ color: "#555" }}>{ing.reason}</Text>
          </View>
        ))}
      </View>
      <Text testID="disclaimer" style={{ fontSize: 12, color: "#777" }}>{result.disclaimer}</Text>
    </View>
  );
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd mobile && npm test -- VerdictResult` → PASS. `npm run typecheck` → no errors.

- [ ] **Step 5: Commit**

```bash
git add mobile/src/components/VerdictResult.tsx mobile/src/components/__tests__/VerdictResult.test.tsx
git commit -m "feat(mobile): reusable VerdictResult component

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Home scan screen

**Files:**
- Modify: `mobile/src/app/(app)/index.tsx`
- Test: `mobile/src/app/(app)/__tests__/home.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `mobile/src/app/(app)/__tests__/home.test.tsx`:

```tsx
import React from "react";
import { render, fireEvent, waitFor } from "@testing-library/react-native";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Home from "../index";
import * as scan from "@/api/scan";

jest.mock("@/api/scan");

function wrap(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  return <QueryClientProvider client={client}>{ui}</QueryClientProvider>;
}

const verdict = {
  verdict: "haram",
  ingredients: [{ input: "lard", canonical: "lard", status: "haram", source: "rulebook", confidence: "high", reason: "pork fat", citation: "x" }],
  summary: "Contains haram ingredients.",
  disclaimer: "Not a religious ruling.",
};

beforeEach(() => jest.resetAllMocks());

test("checking ingredients shows the verdict", async () => {
  (scan.classify as jest.Mock).mockResolvedValue(verdict);
  const { getByTestId } = render(wrap(<Home />));
  fireEvent.changeText(getByTestId("ingredients"), "lard\nsugar");
  fireEvent.press(getByTestId("check"));
  await waitFor(() => expect(getByTestId("verdict").props.children).toContain("HARAM"));
  expect(scan.classify).toHaveBeenCalledWith(["lard", "sugar"]);
});

test("empty input does not call the API", () => {
  const { getByTestId } = render(wrap(<Home />));
  fireEvent.press(getByTestId("check"));
  expect(scan.classify).not.toHaveBeenCalled();
});

test("an API error is shown", async () => {
  (scan.classify as jest.Mock).mockRejectedValue(new Error("Server error"));
  const { getByTestId, findByTestId } = render(wrap(<Home />));
  fireEvent.changeText(getByTestId("ingredients"), "lard");
  fireEvent.press(getByTestId("check"));
  expect((await findByTestId("error")).props.children).toContain("Server error");
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd mobile && npm test -- home`
Expected: FAIL — the Home placeholder has no `ingredients`/`check` testIDs.

- [ ] **Step 3: Replace the Home screen**

Replace `mobile/src/app/(app)/index.tsx` with:

```tsx
import React, { useState } from "react";
import { View, Text, TextInput, Button, ScrollView, ActivityIndicator } from "react-native";
import { useMutation } from "@tanstack/react-query";
import { classify } from "@/api/scan";
import VerdictResult from "@/components/VerdictResult";

function parseIngredients(text: string): string[] {
  return text.split(/[\n,]+/).map((s) => s.trim()).filter(Boolean);
}

export default function Home() {
  const [text, setText] = useState("");
  const mutation = useMutation({ mutationFn: (items: string[]) => classify(items) });

  function onCheck() {
    const parsed = parseIngredients(text);
    if (parsed.length === 0) return;
    mutation.mutate(parsed);
  }

  return (
    <ScrollView contentContainerStyle={{ padding: 20, gap: 12 }}>
      <Text style={{ fontSize: 18, fontWeight: "600" }}>Check ingredients</Text>
      <TextInput
        testID="ingredients"
        multiline
        placeholder="One ingredient per line (or comma-separated)"
        value={text}
        onChangeText={setText}
        style={{ borderWidth: 1, borderColor: "#ccc", borderRadius: 6, padding: 10, minHeight: 100, textAlignVertical: "top" }}
      />
      <Button testID="check" title="Check" onPress={onCheck} />
      {mutation.isPending ? <ActivityIndicator /> : null}
      {mutation.isError ? (
        <Text testID="error" style={{ color: "red" }}>
          {(mutation.error as Error)?.message ?? "Something went wrong"}
        </Text>
      ) : null}
      {mutation.data ? <VerdictResult result={mutation.data} /> : null}
    </ScrollView>
  );
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd mobile && npm test -- home` → PASS. `npm run typecheck` → no errors.

- [ ] **Step 5: Commit**

```bash
git add "mobile/src/app/(app)/index.tsx" "mobile/src/app/(app)/__tests__/home.test.tsx"
git commit -m "feat(mobile): Home classify scan screen

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Full verification + checkpoint

- [ ] **Step 1: Full verification**

Run from `mobile/`: `npm test` (all green) and `npm run typecheck` (clean). Report counts.

- [ ] **Step 2: Update the checkpoint**

Edit `docs/CHECKPOINT.md`: refresh the branch section (SP17 merged; SP18 in flight); update the mobile test count; add an SP18 entry under "What's built" (the classify scan screen, `VerdictResult`, the `scan` API wrapper, and API-key 401 auto-recovery — note the SP17 known gap is now closed); set the next step to SP19 (barcode + image, camera) and SP20 (history), still pending the user's visual design.

- [ ] **Step 3: Commit**

```bash
git add docs/CHECKPOINT.md docs/superpowers/plans/2026-06-03-classify-screen.md
git commit -m "docs(mobile): SP18 done — classify scan screen

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Notes for the implementer

- `jest.mock("../client", ...)` must keep the real `ApiError` (use `jest.requireActual`) so `e instanceof ApiError` works in the recovery path — only `request` is mocked.
- The Home test wraps `<Home/>` in a `QueryClientProvider` with `mutations.retry: false` so a rejected mutation surfaces immediately.
- `VerdictResult` is intentionally presentational (props in, no data fetching) so SP19's barcode/image screens reuse it.
- The app cannot be run here; "done" = `npm test` green + `npm run typecheck` clean. On-device is the user's check.
- Every commit message ends with the trailer:
  `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`
- This branch is from `main`; final `--no-ff` merge to `main` after review.
