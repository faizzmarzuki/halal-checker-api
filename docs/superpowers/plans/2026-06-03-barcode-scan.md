# Barcode Scan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scan a barcode (camera or manual entry) and look it up via `/scan-barcode`, showing the verdict — reached from a Home button.

**Architecture:** A `scanBarcode` API wrapper (apiKey auth + the existing 401 recovery), a new `barcode` screen using `expo-camera` for live scanning plus a manual `Input` fallback, both feeding one TanStack Query mutation → `VerdictResult`. The route is registered hidden (`href: null`) and pushed from Home. Tests mock the native camera module.

**Tech Stack:** Expo (SDK 54), expo-camera, expo-router, @tanstack/react-query, Jest + RNTL. Under `mobile/`. Run from `mobile/`: `npm test`, `npm run typecheck`.

---

## File Structure (`mobile/src/`)

- `api/scan.ts` — add `BarcodeVerdictOut` type + `scanBarcode()`.
- `app/(app)/barcode.tsx` (new) — the scan screen.
- `app/(app)/index.tsx` — add a "Scan barcode" button.
- `app/(app)/_layout.tsx` — register the hidden `barcode` route.
- tests under `__tests__/`.

---

## Task 1: scanBarcode API

**Files:** `mobile/src/api/scan.ts`, `mobile/src/api/__tests__/scan.test.ts`

- [ ] **Step 1: Write the failing test**

Append to `mobile/src/api/__tests__/scan.test.ts`:

```ts
test("scanBarcode posts the barcode with the api key", async () => {
  const bv = { ...verdict, barcode: "0123456789", product_name: "Nutella" };
  (request as jest.Mock).mockResolvedValue(bv);
  const { scanBarcode } = await import("../scan");
  const result = await scanBarcode("0123456789");
  expect(result).toEqual(bv);
  expect(request).toHaveBeenCalledWith("/scan-barcode", {
    method: "POST",
    auth: "apiKey",
    body: { barcode: "0123456789", use_gemma: true, translate: false },
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd mobile && npm test -- scan.test`
Expected: FAIL — `scanBarcode` is not exported.

- [ ] **Step 3: Add `scanBarcode`**

In `mobile/src/api/scan.ts`, after `classify`, add:

```ts
export type BarcodeVerdictOut = VerdictOut & { barcode: string; product_name: string };

export function scanBarcode(barcode: string, opts: ClassifyOpts = {}): Promise<BarcodeVerdictOut> {
  return withApiKeyRecovery(() =>
    request<BarcodeVerdictOut>("/scan-barcode", {
      method: "POST",
      auth: "apiKey",
      body: {
        barcode,
        use_gemma: opts.useGemma ?? true,
        translate: opts.translate ?? false,
      },
    }),
  );
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd mobile && npm test -- scan.test` → PASS. `npm run typecheck` → clean.

- [ ] **Step 5: Commit**

```bash
git add mobile/src/api/scan.ts mobile/src/api/__tests__/scan.test.ts
git commit -m "feat(mobile): scanBarcode API wrapper

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Barcode screen + camera + Home entry

**Files:** add `expo-camera`; create `mobile/src/app/(app)/barcode.tsx` + its test; modify `index.tsx` and `_layout.tsx`.

- [ ] **Step 1: Install expo-camera**

Run from `mobile/`: `npx expo install expo-camera`. (Adds the camera permission usage string to the app config; works in Expo Go on SDK 54.)

- [ ] **Step 2: Write the failing test**

Create `mobile/src/app/(app)/__tests__/barcode.test.tsx`:

```tsx
import React from "react";
import { render, fireEvent, waitFor } from "@testing-library/react-native";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import BarcodeScreen from "../barcode";
import * as scan from "@/api/scan";
import { useCameraPermissions } from "expo-camera";

jest.mock("@/api/scan");
jest.mock("expo-camera", () => ({
  CameraView: () => null,
  useCameraPermissions: jest.fn(() => [{ granted: true }, jest.fn()]),
}));

let client: QueryClient;
beforeEach(() => {
  jest.clearAllMocks();
  (useCameraPermissions as jest.Mock).mockReturnValue([{ granted: true }, jest.fn()]);
  client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
});
afterEach(() => client.clear());

function wrap(ui: React.ReactElement) {
  return <QueryClientProvider client={client}>{ui}</QueryClientProvider>;
}

const bv = {
  verdict: "haram",
  ingredients: [{ input: "lard", canonical: "lard", status: "haram", source: "rulebook", confidence: "high", reason: "pork fat", citation: "x" }],
  summary: "Contains haram ingredients.",
  disclaimer: "Not a religious ruling.",
  barcode: "0123456789",
  product_name: "Nutella",
};

test("manual look up shows the verdict", async () => {
  (scan.scanBarcode as jest.Mock).mockResolvedValue(bv);
  const { getByTestId } = render(wrap(<BarcodeScreen />));
  fireEvent.changeText(getByTestId("barcode"), "0123456789");
  fireEvent.press(getByTestId("lookup"));
  await waitFor(() => expect(getByTestId("verdict").props.children).toContain("HARAM"));
  expect(scan.scanBarcode).toHaveBeenCalledWith("0123456789");
});

test("a lookup error is shown", async () => {
  (scan.scanBarcode as jest.Mock).mockRejectedValue(new Error("Product not found"));
  const { getByTestId, findByTestId } = render(wrap(<BarcodeScreen />));
  fireEvent.changeText(getByTestId("barcode"), "0000000000");
  fireEvent.press(getByTestId("lookup"));
  expect((await findByTestId("error")).props.children).toContain("Product not found");
});

test("shows Allow camera when permission is undetermined", () => {
  (useCameraPermissions as jest.Mock).mockReturnValue([{ granted: false, status: "undetermined" }, jest.fn()]);
  const { getByTestId } = render(wrap(<BarcodeScreen />));
  expect(getByTestId("allow-camera")).toBeTruthy();
});
```

- [ ] **Step 3: Run to verify it fails**

Run: `cd mobile && npm test -- barcode`
Expected: FAIL — `Cannot find module '../barcode'`.

- [ ] **Step 4: Create the barcode screen**

Create `mobile/src/app/(app)/barcode.tsx`:

```tsx
import React, { useState } from "react";
import { View } from "react-native";
import { CameraView, useCameraPermissions } from "expo-camera";
import { useMutation } from "@tanstack/react-query";
import { scanBarcode } from "@/api/scan";
import VerdictResult from "@/components/VerdictResult";
import { Screen } from "@/components/ui/Screen";
import { Heading, Text } from "@/components/ui/Text";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { colors, radius, space } from "@/theme/tokens";

export default function BarcodeScreen() {
  const [permission, requestPermission] = useCameraPermissions();
  const [manual, setManual] = useState("");
  const [scanned, setScanned] = useState(false);
  const mutation = useMutation({ mutationFn: (code: string) => scanBarcode(code) });

  function lookup(code: string) {
    if (!code) return;
    setScanned(true);
    mutation.mutate(code);
  }

  function reset() {
    setScanned(false);
    mutation.reset();
  }

  return (
    <Screen scroll>
      <Heading>Scan barcode</Heading>

      {permission?.granted ? (
        <View style={{ height: 240, borderRadius: radius.card, overflow: "hidden", backgroundColor: "#000" }}>
          <CameraView
            style={{ flex: 1 }}
            barcodeScannerSettings={{ barcodeTypes: ["ean13", "ean8", "upc_a", "upc_e"] }}
            onBarcodeScanned={scanned ? undefined : ({ data }: { data: string }) => lookup(data)}
          />
        </View>
      ) : (
        <Button testID="allow-camera" title="Allow camera" variant="secondary" onPress={() => requestPermission()} />
      )}

      <Text variant="label" color={colors.muted}>OR ENTER MANUALLY</Text>
      <Input testID="barcode" label="Barcode" placeholder="e.g. 0123456789" keyboardType="number-pad"
        value={manual} onChangeText={setManual} />
      <Button testID="lookup" title="Look up" onPress={() => lookup(manual)} loading={mutation.isPending} />

      {mutation.isError ? (
        <Text testID="error" variant="small" color={colors.haram}>{(mutation.error as Error)?.message ?? "Lookup failed"}</Text>
      ) : null}
      {mutation.data ? (
        <View style={{ gap: space.md }}>
          <Text variant="h2">{mutation.data.product_name || mutation.data.barcode}</Text>
          <VerdictResult result={mutation.data} />
          <Button testID="scan-again" title="Scan again" variant="secondary" onPress={reset} />
        </View>
      ) : null}
    </Screen>
  );
}
```

- [ ] **Step 5: Add the Home entry button**

In `mobile/src/app/(app)/index.tsx`, add the import `import { router } from "expo-router";` and, right after the `<Button testID="check" ... />` line, add:

```tsx
      <Button testID="go-barcode" title="Scan barcode" variant="secondary" onPress={() => router.push("/barcode")} />
```

- [ ] **Step 6: Register the hidden route**

In `mobile/src/app/(app)/_layout.tsx`, add inside `<Tabs>` (after the three existing `Tabs.Screen`s):

```tsx
      <Tabs.Screen name="barcode" options={{ href: null }} />
```

- [ ] **Step 7: Run tests + typecheck**

Run: `cd mobile && npm test` then `npm run typecheck`.
Expected: all suites pass (the 3 barcode tests + the rest); typecheck clean. If `router.push("/barcode")` trips typed-routes, change it to `router.push("/(app)/barcode" as any)` (the route is hidden via `href:null`, so the generated union may exclude it).

- [ ] **Step 8: Commit**

```bash
git add "mobile/src/app/(app)/barcode.tsx" "mobile/src/app/(app)/__tests__/barcode.test.tsx" "mobile/src/app/(app)/index.tsx" "mobile/src/app/(app)/_layout.tsx" mobile/package.json mobile/package-lock.json mobile/app.json
git commit -m "feat(mobile): barcode scan screen (camera + manual) reached from Home

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Full verification + checkpoint

- [ ] **Step 1: Full verification**

Run from `mobile/`: `npm test` (all green), `npm run typecheck` (clean), `npx expo export --platform web` (bundles — catches import errors; note the camera view is a no-op on web but must not break the bundle). Report counts.

- [ ] **Step 2: Update the checkpoint**

Edit `docs/CHECKPOINT.md`: refresh the branch section (SP23 merged; SP24 in flight); update the mobile test count; add an SP24 entry under "What's built" (the barcode scan screen + `scanBarcode` + expo-camera); set the next step to SP25 (image/photo scan).

- [ ] **Step 3: Commit**

```bash
git add docs/CHECKPOINT.md docs/superpowers/plans/2026-06-03-barcode-scan.md
git commit -m "docs(mobile): SP24 done — barcode scan

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Notes for the implementer

- Mock `expo-camera` in tests (`CameraView` stub + controllable `useCameraPermissions`); the manual-entry path exercises the same `lookup()` the live `onBarcodeScanned` calls.
- `BarcodeVerdictOut` extends `VerdictOut`, so `VerdictResult` accepts it directly; the screen also shows `product_name`.
- Keep `maxWorkers: 1` + `--forceExit` (already in the jest config).
- The app can't be run here; "done" = `npm test` green + `npm run typecheck` clean + web export OK. The live camera scan is the user's on-device check.
- Every commit message ends with the trailer:
  `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`
- This branch is from `main`; final `--no-ff` merge to `main` after review.
