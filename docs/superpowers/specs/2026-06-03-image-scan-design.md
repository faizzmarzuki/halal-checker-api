# SP25 — Image / Photo Scan (Design)

**Date:** 2026-06-03
**Status:** Approved

## Goal

Let a mobile user point at (or pick) a photo of an ingredient label, send the
raw image to the backend `/scan-image` endpoint for OCR, and show the resulting
halal/haram/shubhah verdict — reusing the existing `VerdictResult` component.

This is the second half of "camera scanning" (SP24 did barcode lookup).

## Scope

In scope:
- New screen `app/(app)/photo.tsx` (hidden route, mirrors `barcode.tsx`).
- "Take photo" (camera) and "Choose from gallery" image sources via `expo-image-picker`.
- Preview of the chosen image, then auto-upload.
- `scanImage(uri)` API helper that uploads raw bytes to `/scan-image`.
- A "Scan photo" entry button on Home.
- Hidden `photo` route registered in `(app)/_layout.tsx`.
- Jest tests (native modules mocked).

Out of scope (not now):
- Custom display font (`expo-font`).
- Backend deploy for a stable URL.
- Image cropping / rotation UI.

## Backend contract (already built)

`POST /scan-image`
- Auth: `X-API-Key` header (same auto-managed key the app already mints).
- Body: **raw image bytes** (read via `await request.body()`), not multipart, not JSON.
- Response (200): `VerdictOut` plus `extracted_text` — the OCR'd label text.
- Error responses use FastAPI's `{ "detail": "..." }` shape (e.g. 422 when no
  text can be read, 401 when the key is stale, 413 when the image is too large).

## Architecture

### `src/api/scan.ts` — `scanImage(uri)`

The existing `request()` helper only does JSON bodies, so image upload bypasses
it and uses `expo-file-system`'s `uploadAsync` to stream the file's raw bytes.

```ts
export type ImageVerdictOut = VerdictOut & { extracted_text: string };

export function scanImage(uri: string): Promise<ImageVerdictOut> {
  return withApiKeyRecovery(async () => {
    const apiKey = await getApiKeyHeaderValue(); // current stored key
    const res = await uploadAsync(`${API_URL}/scan-image`, uri, {
      httpMethod: "POST",
      uploadType: BINARY_CONTENT,
      headers: { "X-API-Key": apiKey, "Content-Type": "application/octet-stream" },
    });
    const data = res.body ? JSON.parse(res.body) : {};
    if (res.status < 200 || res.status >= 300) {
      throw new ApiError(res.status, data?.detail ?? "Scan failed");
    }
    return data as ImageVerdictOut;
  });
}
```

- Wrapped in the existing `withApiKeyRecovery` so a 401 drops the stale key,
  re-mints via `/keys`, and retries once (the retried call re-reads the key).
- The exact `uploadAsync` import path is verified during implementation — on
  Expo SDK 54 it may live under `expo-file-system/legacy`. `BINARY_CONTENT`
  comes from `FileSystemUploadType`.
- The current key value is read from secure storage (the same `hs.apiKey` slot
  `session.ts` already manages).

### `app/(app)/photo.tsx` — Photo scan screen

Mirrors `barcode.tsx`:
- `useMutation({ mutationFn: scanImage })`.
- Two buttons: "Take photo" → `ImagePicker.launchCameraAsync`, "Choose from
  gallery" → `ImagePicker.launchImageLibraryAsync`. Camera needs
  `requestCameraPermissionsAsync`; if denied, show a message.
- On a non-cancelled pick: store the local `uri`, render an `Image` preview,
  and `mutation.mutate(uri)`.
- States: pending (`Button loading`), error (`testID="error"`, haram colour),
  success → `<VerdictResult result={mutation.data} />`. Optionally surface
  `extracted_text` under the verdict.
- "Scan another" resets the uri and `mutation.reset()`.

### `app/(app)/index.tsx` — Home entry

Add below the barcode button:
```tsx
<Button testID="go-photo" title="Scan photo" variant="secondary"
  onPress={() => router.push("/photo")} />
```

### `app/(app)/_layout.tsx` — route registration

Add a hidden tab:
```tsx
<Tabs.Screen name="photo" options={{ href: null, title: "Scan photo" }} />
```

## Data flow

1. User taps "Scan photo" on Home → navigates to `/photo`.
2. User taps "Take photo" or "Choose from gallery" → `expo-image-picker` returns a local file `uri`.
3. Screen shows the preview and calls `scanImage(uri)`.
4. `scanImage` uploads the raw bytes to `/scan-image` with `X-API-Key`.
5. Backend OCRs the image and classifies → `ImageVerdictOut`.
6. Screen renders `VerdictResult` (+ extracted text).

## Error handling

- **Picker cancelled:** no-op (don't mutate, don't show an error).
- **Camera permission denied:** show a short message, keep the gallery option usable.
- **Stale API key (401):** handled transparently by `withApiKeyRecovery`.
- **No text / unreadable (422) or other non-2xx:** `scanImage` throws `ApiError`
  with the backend `detail`; the screen renders it in `testID="error"`.
- **Network failure:** `uploadAsync` rejects; surfaced the same way via the mutation's error.

## Testing (Jest, jest-expo, RNTL — native mocked)

`src/api/__tests__/scan.image.test.ts`:
- Mocks `expo-file-system` (`uploadAsync`) and the session/key read.
- Success: asserts the URL, `httpMethod`, `BINARY_CONTENT`, and `X-API-Key`
  header, parses `body` → `ImageVerdictOut`.
- Non-2xx: rejects with `ApiError` carrying the backend `detail`.
- 401: first call 401s, recovery re-mints, second call succeeds.

`app/(app)/__tests__/photo.test.tsx`:
- Mocks `expo-image-picker` (returns a fake non-cancelled asset) and `@/api/scan`.
- Pick → `scanImage` called with the uri → `VerdictResult` verdict shown.
- A scan error renders `testID="error"`.
- Cancelled pick → `scanImage` not called.

## Dependencies

- `expo-image-picker` (camera + gallery) — installed via `npx expo install`.
- `expo-file-system` (`uploadAsync`) — installed via `npx expo install`.
Both ship with Expo Go SDK 54, so no dev build is required.
