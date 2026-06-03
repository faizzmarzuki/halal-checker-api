# Image / Photo Scan (SP25) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a mobile user take or pick a photo of an ingredient label, upload the raw image to `/scan-image` for OCR, and show the halal/haram/shubhah verdict.

**Architecture:** A new `scanImage(uri)` API helper streams the file's raw bytes to `/scan-image` via `expo-file-system`'s `uploadAsync` (the JSON `request()` helper can't send binary), wrapped in the existing `withApiKeyRecovery`. A new hidden `photo.tsx` screen (mirroring `barcode.tsx`) picks an image with `expo-image-picker`, previews it, runs the mutation, and reuses `VerdictResult`. Home gets a "Scan photo" button.

**Tech Stack:** React Native + Expo SDK 54, TypeScript, expo-router, TanStack Query, expo-image-picker, expo-file-system (`legacy` upload API), Jest + jest-expo + React Native Testing Library.

---

## Context for the implementer

Run all commands from the repo root `D:\Development\halal-scanner` unless noted. The mobile app lives in `mobile/`. Tests run with `npm test` **from inside `mobile/`** (script is `jest --forceExit`, `maxWorkers: 1`, `testTimeout: 20000`). The `@/` alias maps to `mobile/src/`.

Key existing facts (already verified — do not re-derive):
- `expo-file-system@19.0.23` is installed. `uploadAsync` and `FileSystemUploadType.BINARY_CONTENT` are exported from the subpath **`expo-file-system/legacy`** (the root export is the new API which has no `uploadAsync`).
- `src/api/scan.ts` already exports `VerdictOut`, `withApiKeyRecovery`, and imports `ApiError` from `./client`, `ensureApiKey` from `./keys`, `clearApiKey` from `../auth/session`.
- `src/auth/session.ts` exports `readSession()` → `{ access, refresh, apiKey, email }`.
- `src/config.ts` exports `API_URL`.
- `src/components/VerdictResult.tsx` takes `result: VerdictOut` and renders `testID="verdict"` (uppercased verdict), ingredient cards, and `testID="disclaimer"`.
- `app/(app)/barcode.tsx` is the screen pattern to mirror; `app/(app)/index.tsx` (Home) and `app/(app)/_layout.tsx` (Tabs) are the integration points.

---

## File Structure

- `mobile/src/api/scan.ts` — **modify**: add `ImageVerdictOut` type + `scanImage(uri)`.
- `mobile/src/api/__tests__/scan.image.test.ts` — **create**: unit tests for `scanImage`.
- `mobile/src/app/(app)/photo.tsx` — **create**: photo scan screen.
- `mobile/src/app/(app)/__tests__/photo.test.tsx` — **create**: screen tests.
- `mobile/src/app/(app)/index.tsx` — **modify**: add "Scan photo" button.
- `mobile/src/app/(app)/_layout.tsx` — **modify**: register hidden `photo` route.

---

## Task 1: Install `expo-image-picker`

**Files:** none (dependency install only)

- [ ] **Step 1: Install the package with Expo's version resolver**

Run from `mobile/`:
```bash
npx expo install expo-image-picker
```
Expected: adds `expo-image-picker` (~17.x for SDK 54) to `mobile/package.json` dependencies and installs it. If npm errors on peer deps, re-run with `npm install --legacy-peer-deps` (this repo uses that due to the SDK 54 pin).

- [ ] **Step 2: Verify it resolves**

Run from `mobile/`:
```bash
node -e "console.log(require('expo-image-picker/package.json').version)"
```
Expected: prints a `17.x` (or the SDK-54-aligned) version, no error.

- [ ] **Step 3: Commit**

```bash
git add mobile/package.json mobile/package-lock.json
git commit -m "chore(sp25): add expo-image-picker"
```

---

## Task 2: `scanImage(uri)` API helper

**Files:**
- Modify: `mobile/src/api/scan.ts`
- Test: `mobile/src/api/__tests__/scan.image.test.ts`

- [ ] **Step 1: Write the failing test**

Create `mobile/src/api/__tests__/scan.image.test.ts`:
```ts
import { uploadAsync, FileSystemUploadType } from "expo-file-system/legacy";
import { scanImage } from "../scan";
import { ApiError } from "../client";

jest.mock("expo-file-system/legacy", () => ({
  uploadAsync: jest.fn(),
  FileSystemUploadType: { BINARY_CONTENT: 0 },
}));
jest.mock("../../auth/session", () => ({
  readSession: jest.fn(async () => ({ apiKey: "key-123" })),
  clearApiKey: jest.fn(async () => {}),
}));
jest.mock("../keys", () => ({ ensureApiKey: jest.fn(async () => {}) }));

const session = require("../../auth/session");
const keys = require("../keys");

const ok = {
  verdict: "halal",
  ingredients: [],
  summary: "All clear.",
  disclaimer: "Not a religious ruling.",
  extracted_text: "sugar, salt",
};

beforeEach(() => jest.clearAllMocks());

test("uploads raw bytes with the api key and returns the verdict", async () => {
  (uploadAsync as jest.Mock).mockResolvedValue({ status: 200, body: JSON.stringify(ok) });
  const result = await scanImage("file:///tmp/label.jpg");
  expect(result).toEqual(ok);
  const [url, fileUri, options] = (uploadAsync as jest.Mock).mock.calls[0];
  expect(url).toContain("/scan-image");
  expect(fileUri).toBe("file:///tmp/label.jpg");
  expect(options.httpMethod).toBe("POST");
  expect(options.uploadType).toBe(FileSystemUploadType.BINARY_CONTENT);
  expect(options.headers["X-API-Key"]).toBe("key-123");
});

test("throws ApiError with the backend detail on non-2xx", async () => {
  (uploadAsync as jest.Mock).mockResolvedValue({
    status: 422,
    body: JSON.stringify({ detail: "Could not read any text" }),
  });
  await expect(scanImage("file:///tmp/blurry.jpg")).rejects.toMatchObject({
    name: "ApiError",
    status: 422,
    message: "Could not read any text",
  });
});

test("on 401 it re-mints the key and retries once", async () => {
  (uploadAsync as jest.Mock)
    .mockResolvedValueOnce({ status: 401, body: JSON.stringify({ detail: "Invalid API key" }) })
    .mockResolvedValueOnce({ status: 200, body: JSON.stringify(ok) });
  const result = await scanImage("file:///tmp/label.jpg");
  expect(result).toEqual(ok);
  expect(session.clearApiKey).toHaveBeenCalledTimes(1);
  expect(keys.ensureApiKey).toHaveBeenCalledTimes(1);
  expect((uploadAsync as jest.Mock).mock.calls.length).toBe(2);
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run from `mobile/`:
```bash
npm test -- scan.image
```
Expected: FAIL — `scanImage` is not exported from `../scan`.

- [ ] **Step 3: Implement `scanImage`**

Edit `mobile/src/api/scan.ts`. Add `readSession` to the session import and `API_URL` import at the top:
```ts
import { request, ApiError } from "./client";
import { ensureApiKey } from "./keys";
import { clearApiKey, readSession } from "../auth/session";
import { uploadAsync, FileSystemUploadType } from "expo-file-system/legacy";
import { API_URL } from "../config";
```
Then append at the end of the file:
```ts
export type ImageVerdictOut = VerdictOut & { extracted_text: string };

// /scan-image takes raw image bytes (not JSON), so it bypasses request() and
// streams the file with expo-file-system. Reuses the X-API-Key recovery flow.
export function scanImage(uri: string): Promise<ImageVerdictOut> {
  return withApiKeyRecovery(async () => {
    const { apiKey } = await readSession();
    const res = await uploadAsync(`${API_URL}/scan-image`, uri, {
      httpMethod: "POST",
      uploadType: FileSystemUploadType.BINARY_CONTENT,
      headers: {
        "X-API-Key": apiKey ?? "",
        "Content-Type": "application/octet-stream",
      },
    });
    const data = res.body ? JSON.parse(res.body) : {};
    if (res.status < 200 || res.status >= 300) {
      throw new ApiError(res.status, data?.detail ?? "Scan failed");
    }
    return data as ImageVerdictOut;
  });
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run from `mobile/`:
```bash
npm test -- scan.image
```
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add mobile/src/api/scan.ts mobile/src/api/__tests__/scan.image.test.ts
git commit -m "feat(sp25): scanImage uploads raw bytes to /scan-image"
```

---

## Task 3: Photo scan screen

**Files:**
- Create: `mobile/src/app/(app)/photo.tsx`
- Test: `mobile/src/app/(app)/__tests__/photo.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `mobile/src/app/(app)/__tests__/photo.test.tsx`:
```tsx
import React from "react";
import { render, fireEvent, waitFor } from "@testing-library/react-native";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import PhotoScreen from "../photo";
import * as scan from "@/api/scan";
import * as ImagePicker from "expo-image-picker";

jest.mock("@/api/scan");
jest.mock("expo-image-picker", () => ({
  requestCameraPermissionsAsync: jest.fn(async () => ({ granted: true })),
  launchCameraAsync: jest.fn(async () => ({ canceled: false, assets: [{ uri: "file:///cam.jpg" }] })),
  launchImageLibraryAsync: jest.fn(async () => ({ canceled: false, assets: [{ uri: "file:///lib.jpg" }] })),
}));

let client: QueryClient;
beforeEach(() => {
  jest.clearAllMocks();
  (ImagePicker.requestCameraPermissionsAsync as jest.Mock).mockResolvedValue({ granted: true });
  (ImagePicker.launchCameraAsync as jest.Mock).mockResolvedValue({ canceled: false, assets: [{ uri: "file:///cam.jpg" }] });
  (ImagePicker.launchImageLibraryAsync as jest.Mock).mockResolvedValue({ canceled: false, assets: [{ uri: "file:///lib.jpg" }] });
  client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
});
afterEach(() => client.clear());

function wrap(ui: React.ReactElement) {
  return <QueryClientProvider client={client}>{ui}</QueryClientProvider>;
}

const iv = {
  verdict: "halal",
  ingredients: [{ input: "sugar", canonical: "sugar", status: "halal", source: "rulebook", confidence: "high", reason: "ok", citation: "x" }],
  summary: "All clear.",
  disclaimer: "Not a religious ruling.",
  extracted_text: "sugar, salt",
};

test("taking a photo scans it and shows the verdict", async () => {
  (scan.scanImage as jest.Mock).mockResolvedValue(iv);
  const { getByTestId } = render(wrap(<PhotoScreen />));
  fireEvent.press(getByTestId("take-photo"));
  await waitFor(() => expect(getByTestId("verdict").props.children).toContain("HALAL"));
  expect(scan.scanImage).toHaveBeenCalledWith("file:///cam.jpg");
});

test("choosing from gallery scans the picked image", async () => {
  (scan.scanImage as jest.Mock).mockResolvedValue(iv);
  const { getByTestId } = render(wrap(<PhotoScreen />));
  fireEvent.press(getByTestId("pick-gallery"));
  await waitFor(() => expect(scan.scanImage).toHaveBeenCalledWith("file:///lib.jpg"));
});

test("a cancelled pick does not scan", async () => {
  (ImagePicker.launchImageLibraryAsync as jest.Mock).mockResolvedValue({ canceled: true, assets: null });
  (scan.scanImage as jest.Mock).mockResolvedValue(iv);
  const { getByTestId } = render(wrap(<PhotoScreen />));
  fireEvent.press(getByTestId("pick-gallery"));
  await waitFor(() => expect(ImagePicker.launchImageLibraryAsync).toHaveBeenCalled());
  expect(scan.scanImage).not.toHaveBeenCalled();
});

test("a scan error is shown", async () => {
  (scan.scanImage as jest.Mock).mockRejectedValue(new Error("Could not read any text"));
  const { getByTestId, findByTestId } = render(wrap(<PhotoScreen />));
  fireEvent.press(getByTestId("pick-gallery"));
  expect((await findByTestId("error")).props.children).toContain("Could not read any text");
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run from `mobile/`:
```bash
npm test -- photo
```
Expected: FAIL — cannot find module `../photo`.

- [ ] **Step 3: Implement the screen**

Create `mobile/src/app/(app)/photo.tsx`:
```tsx
import React, { useState } from "react";
import { View, Image } from "react-native";
import * as ImagePicker from "expo-image-picker";
import { useMutation } from "@tanstack/react-query";
import { scanImage } from "@/api/scan";
import VerdictResult from "@/components/VerdictResult";
import { Screen } from "@/components/ui/Screen";
import { Heading, Text } from "@/components/ui/Text";
import { Button } from "@/components/ui/Button";
import { colors, radius, space } from "@/theme/tokens";

export default function PhotoScreen() {
  const [uri, setUri] = useState<string | null>(null);
  const mutation = useMutation({ mutationFn: (u: string) => scanImage(u) });

  function run(u: string) {
    setUri(u);
    mutation.mutate(u);
  }

  async function takePhoto() {
    const perm = await ImagePicker.requestCameraPermissionsAsync();
    if (!perm.granted) return;
    const res = await ImagePicker.launchCameraAsync({ quality: 0.6 });
    if (!res.canceled && res.assets?.[0]) run(res.assets[0].uri);
  }

  async function pickGallery() {
    const res = await ImagePicker.launchImageLibraryAsync({ quality: 0.6 });
    if (!res.canceled && res.assets?.[0]) run(res.assets[0].uri);
  }

  function reset() {
    setUri(null);
    mutation.reset();
  }

  return (
    <Screen scroll>
      <Heading>Scan photo</Heading>
      <Text variant="small" color={colors.muted}>
        Snap or pick a photo of the ingredient list.
      </Text>

      <Button testID="take-photo" title="Take photo" onPress={takePhoto} />
      <Button testID="pick-gallery" title="Choose from gallery" variant="secondary" onPress={pickGallery} />

      {uri ? (
        <Image
          testID="preview"
          source={{ uri }}
          style={{ height: 200, borderRadius: radius.card, backgroundColor: colors.border }}
          resizeMode="cover"
        />
      ) : null}

      {mutation.isPending ? <Text variant="small" color={colors.muted}>Reading label…</Text> : null}
      {mutation.isError ? (
        <Text testID="error" variant="small" color={colors.haram}>
          {(mutation.error as Error)?.message ?? "Scan failed"}
        </Text>
      ) : null}
      {mutation.data ? (
        <View style={{ gap: space.md }}>
          <VerdictResult result={mutation.data} />
          {mutation.data.extracted_text ? (
            <Text variant="small" color={colors.muted}>Read: {mutation.data.extracted_text}</Text>
          ) : null}
          <Button testID="scan-again" title="Scan another" variant="secondary" onPress={reset} />
        </View>
      ) : null}
    </Screen>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run from `mobile/`:
```bash
npm test -- photo
```
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add "mobile/src/app/(app)/photo.tsx" "mobile/src/app/(app)/__tests__/photo.test.tsx"
git commit -m "feat(sp25): photo scan screen (camera + gallery)"
```

---

## Task 4: Wire Home button + register route

**Files:**
- Modify: `mobile/src/app/(app)/index.tsx`
- Modify: `mobile/src/app/(app)/_layout.tsx`

- [ ] **Step 1: Add the "Scan photo" button on Home**

In `mobile/src/app/(app)/index.tsx`, add a button immediately after the existing `go-barcode` button (line 40):
```tsx
<Button testID="go-photo" title="Scan photo" variant="secondary" onPress={() => router.push("/photo")} />
```

- [ ] **Step 2: Register the hidden route**

In `mobile/src/app/(app)/_layout.tsx`, add after the existing hidden `barcode` screen (line 25):
```tsx
<Tabs.Screen name="photo" options={{ href: null, title: "Scan photo" }} />
```

- [ ] **Step 3: Typecheck**

Run from `mobile/`:
```bash
npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add "mobile/src/app/(app)/index.tsx" "mobile/src/app/(app)/_layout.tsx"
git commit -m "feat(sp25): home Scan photo button + hidden route"
```

---

## Task 5: Full verification

**Files:** none (verification + checkpoint)

- [ ] **Step 1: Run the full mobile test suite**

Run from `mobile/`:
```bash
npm test
```
Expected: all suites pass (38 prior + 7 new = 45), no open handles failure.

- [ ] **Step 2: Typecheck the whole app**

Run from `mobile/`:
```bash
npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Update the checkpoint**

Edit `docs/CHECKPOINT.md`: record SP25 as built (scanImage + photo screen, Home entry, hidden route), bump the mobile test count, and set the next step. Then commit:
```bash
git add docs/CHECKPOINT.md
git commit -m "docs(sp25): checkpoint after image/photo scan"
```

---

## Notes / gotchas

- Import upload from **`expo-file-system/legacy`**, not `expo-file-system` (root export has no `uploadAsync`).
- `mediaTypes` is intentionally omitted from `launchImageLibraryAsync` — the default is images, which avoids the SDK-version churn around `MediaTypeOptions` vs `['images']`.
- Gallery picking uses the system photo picker and does not require an explicit permission request on SDK 54; only the camera path calls `requestCameraPermissionsAsync`.
- Tests mock all native modules (`expo-image-picker`, `expo-file-system/legacy`), so they run under jest-expo without a device.
- On-device, the app reaches the backend via the LAN IP in `mobile/.env`; web uses `localhost`. No change needed for SP25.
