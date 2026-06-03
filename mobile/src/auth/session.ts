import * as SecureStore from "expo-secure-store";

export type Session = {
  access: string | null;
  refresh: string | null;
  apiKey: string | null;
  email: string | null;
};

const KEYS = {
  access: "hs.access",
  refresh: "hs.refresh",
  apiKey: "hs.apiKey",
  email: "hs.email",
} as const;

type SaveInput = {
  access?: string;
  refresh?: string;
  apiKey?: string;
  email?: string;
};

export async function saveSession(s: SaveInput): Promise<void> {
  const entries: [string, string | undefined][] = [
    [KEYS.access, s.access],
    [KEYS.refresh, s.refresh],
    [KEYS.apiKey, s.apiKey],
    [KEYS.email, s.email],
  ];
  for (const [k, v] of entries) {
    if (v !== undefined) await SecureStore.setItemAsync(k, v);
  }
}

export async function readSession(): Promise<Session> {
  return {
    access: await SecureStore.getItemAsync(KEYS.access),
    refresh: await SecureStore.getItemAsync(KEYS.refresh),
    apiKey: await SecureStore.getItemAsync(KEYS.apiKey),
    email: await SecureStore.getItemAsync(KEYS.email),
  };
}

export async function clearSession(): Promise<void> {
  for (const k of Object.values(KEYS)) await SecureStore.deleteItemAsync(k);
}
