import { request, ApiError } from "./client";
import { ensureApiKey } from "./keys";
import { clearApiKey, readSession } from "../auth/session";
import { uploadAsync, FileSystemUploadType } from "expo-file-system/legacy";
import { API_URL } from "../config";

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
