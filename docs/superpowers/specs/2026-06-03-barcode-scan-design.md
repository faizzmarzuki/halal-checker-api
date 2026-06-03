# Sub-project 24 — Barcode Scan (Design)

Date: 2026-06-03

Add barcode scanning to the mobile app: from Home, open a barcode screen that
either reads a barcode with the camera or accepts a typed one, looks it up via
`/scan-barcode`, and shows the verdict. Built on the SP23 design system. Branched
from `main`; lives under `mobile/`. Image/photo scanning is SP25.

## Information architecture

Home (Check ingredients) gains a **"Scan barcode"** `Button` that
`router.push`es to a new screen `app/(app)/barcode.tsx`. The screen is registered
in the tab layout with `href: null` so it is routable but **not** a visible tab.

## Barcode screen (`app/(app)/barcode.tsx`)

- **Camera scan** (`expo-camera`): `CameraView` with
  `barcodeScannerSettings={{ barcodeTypes: ["ean13","ean8","upc_a","upc_e"] }}` and
  `onBarcodeScanned`; a `scanned` guard prevents repeated firing (scan once, then
  the lookup runs).
- **Permission** via `useCameraPermissions`: if undetermined, show an "Allow
  camera" `Button` (calls `requestPermission`); if denied, hide the camera and
  rely on manual entry.
- **Manual fallback** (always available): an `Input` for a barcode + a "Look up"
  `Button`.
- Both paths call one `lookup(barcode)` → `useMutation(scanBarcode)` → spinner →
  `VerdictResult` (verdict + product). A 404 ("not found") or other `ApiError`
  shows a message. A "Scan again" `Button` resets the `scanned` guard + result.

## API — `src/api/scan.ts`

```ts
export type BarcodeVerdictOut = VerdictOut & { barcode: string; product_name: string };

export function scanBarcode(barcode: string, opts: ClassifyOpts = {}): Promise<BarcodeVerdictOut> {
  return withApiKeyRecovery(() =>
    request<BarcodeVerdictOut>("/scan-barcode", {
      method: "POST",
      auth: "apiKey",
      body: { barcode, use_gemma: opts.useGemma ?? true, translate: opts.translate ?? false },
    }),
  );
}
```

(`VerdictOut`, `ClassifyOpts`, `withApiKeyRecovery` already exist.) The backend
validates the barcode `^[0-9]{6,14}$` (422 for bad input) and returns 404 when the
product is unknown — both surface as the screen's error message.

## Dependency

Add `expo-camera` via `npx expo install expo-camera` (works in Expo Go on SDK 54;
adds the camera permission usage string to the app config).

## Testing (Jest + RNTL — mock the native module)

- `scanBarcode`: calls `request("/scan-barcode", { method:"POST", auth:"apiKey", body:{ barcode, use_gemma, translate } })` and returns the `BarcodeVerdictOut` (mock `request`).
- Barcode screen (mock `expo-camera` so `CameraView` is a stub and
  `useCameraPermissions` returns `[{ granted: true }, fn]`; mock `@/api/scan`):
  - typing a barcode + pressing **Look up** calls `scanBarcode` with that value and
    renders `VerdictResult` (the `verdict` testID);
  - a rejected lookup shows the error message;
  - when permission is undetermined (`[{ granted: false, status: "undetermined" }, fn]`),
    an "Allow camera" control is shown.
  (The live `onBarcodeScanned` path shares `lookup()`, covered by the manual test.)

Run: `cd mobile && npm test`, `npm run typecheck`.

## Out of scope

Image/photo scan (SP25), custom font, backend deploy, torch/zoom camera controls.

## Conventions

Branch `sub-project-24-barcode-scan` (from `main`); spec here; plan in
`docs/superpowers/plans/`; TDD where it applies (Jest); `--no-ff` merge to `main`;
delete the branch. Commit trailer:
`Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
