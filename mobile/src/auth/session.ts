import { Platform } from "react-native";
import * as SecureStore from "expo-secure-store";

// expo-secure-store is native-only. On web (and tests under Expo web) fall back
// to localStorage so the session layer works everywhere. Native uses the
// encrypted store.
const webStorage = {
  async getItemAsync(k: string): Promise<string | null> {
    return typeof localStorage !== "undefined" ? localStorage.getItem(k) : null;
  },
  async setItemAsync(k: string, v: string): Promise<void> {
    if (typeof localStorage !== "undefined") localStorage.setItem(k, v);
  },
  async deleteItemAsync(k: string): Promise<void> {
    if (typeof localStorage !== "undefined") localStorage.removeItem(k);
  },
};

const storage = Platform.OS === "web" ? webStorage : SecureStore;

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
    if (v !== undefined) await storage.setItemAsync(k, v);
  }
}

export async function readSession(): Promise<Session> {
  return {
    access: await storage.getItemAsync(KEYS.access),
    refresh: await storage.getItemAsync(KEYS.refresh),
    apiKey: await storage.getItemAsync(KEYS.apiKey),
    email: await storage.getItemAsync(KEYS.email),
  };
}

export async function clearSession(): Promise<void> {
  for (const k of Object.values(KEYS)) await storage.deleteItemAsync(k);
}

export async function clearApiKey(): Promise<void> {
  await storage.deleteItemAsync(KEYS.apiKey);
}
