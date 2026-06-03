import { request } from "./client";
import { readSession, saveSession } from "../auth/session";

// Auto-manage a single API key for the device: reuse the stored one, or create
// and persist a new one. The raw key is only returned once at creation.
export async function ensureApiKey(): Promise<string> {
  const s = await readSession();
  if (s.apiKey) return s.apiKey;
  const created = await request<{ api_key: string }>("/keys", {
    method: "POST",
    body: { name: "mobile-app" },
    auth: "bearer",
  });
  await saveSession({ apiKey: created.api_key });
  return created.api_key;
}
