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
