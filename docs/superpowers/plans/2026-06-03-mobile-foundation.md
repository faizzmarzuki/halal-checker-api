# Mobile App Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **NOTE:** This sub-project scaffolds a fresh Expo app — the early steps are interactive (npm installs, generated files vary by Expo SDK version). Inline execution is recommended over blind subagents so the implementer can adapt to what `create-expo-app` actually produces. All commands run from `mobile/` unless stated.

**Goal:** A React Native + Expo (iOS + Android) app in `mobile/` that can register, log in, hold a secure session, auto-manage an API key, and navigate an authenticated shell — functional only, no visual design.

**Architecture:** Expo + TypeScript + expo-router (file-based nav). A typed `fetch` client with JWT auto-refresh sits over `expo-secure-store`-backed session storage; thin endpoint wrappers (`auth`, `keys`) and a React `AuthProvider` orchestrate login/logout. TanStack Query manages server state. Tests are Jest + React Native Testing Library (headless).

**Tech Stack:** Expo (managed), TypeScript, expo-router, @tanstack/react-query, expo-secure-store, jest-expo, @testing-library/react-native.

---

## File Structure (under `mobile/`)

- `src/config.ts` — reads `EXPO_PUBLIC_API_URL`.
- `src/auth/session.ts` — persist/read/clear tokens + api key in secure-store.
- `src/api/client.ts` — typed fetch wrapper: base URL, JSON, `ApiError`, Bearer, 401-refresh-retry.
- `src/api/auth.ts` — register / login / logout / refresh / me.
- `src/api/keys.ts` — `ensureApiKey()`.
- `src/auth/AuthProvider.tsx` — context: restore on launch, `login`, `logout`, state.
- `app/_layout.tsx`, `app/index.tsx`, `app/(auth)/login.tsx`, `app/(auth)/register.tsx`, `app/(app)/_layout.tsx`, `app/(app)/index.tsx`, `app/(app)/history.tsx`, `app/(app)/settings.tsx` — expo-router routes.
- `__tests__/*` co-located or under `src/**`.

Run from `mobile/`: `npm test` (jest), `npm run typecheck` (`tsc --noEmit`).

---

## Task 1: Scaffold the Expo app + test harness

**Files:** new `mobile/` tree; modify root `.gitignore`.

- [ ] **Step 1: Scaffold**

From the repo root run:

```bash
npx create-expo-app@latest mobile --template default --yes
```

The "default" template is TypeScript + expo-router with a tabs example. If the flag form differs in the installed version, run `npx create-expo-app@latest mobile` and pick the default template. After it finishes, `cd mobile` for the rest.

- [ ] **Step 2: Record the generated layout**

Run `ls app && cat package.json` and note the Expo SDK version and the generated `app/` routes. The later tasks REPLACE the example routes under `app/` with the ones in this plan; keep `app/_layout.tsx` as the place that mounts providers.

- [ ] **Step 3: Add runtime + dev dependencies**

```bash
npx expo install expo-secure-store
npm install @tanstack/react-query
npm install -D jest-expo jest @testing-library/react-native @types/jest
```

- [ ] **Step 4: Configure Jest + scripts**

Create `mobile/jest.config.js`:

```js
module.exports = {
  preset: "jest-expo",
  setupFilesAfterEnv: ["@testing-library/react-native/extend-expect"],
  transformIgnorePatterns: [
    "node_modules/(?!((jest-)?react-native|@react-native(-community)?|expo(nent)?|@expo(nent)?/.*|@expo-google-fonts/.*|react-navigation|@react-navigation/.*|@unimodules/.*|unimodules|sentry-expo|native-base|react-native-svg|@tanstack/.*))",
  ],
};
```

In `mobile/package.json`, add to `"scripts"`:

```json
"test": "jest",
"typecheck": "tsc --noEmit"
```

- [ ] **Step 5: Gitignore the install**

In the repo-root `.gitignore`, append:

```
# Expo mobile app
mobile/node_modules/
mobile/.expo/
mobile/dist/
mobile/web-build/
```

- [ ] **Step 6: Smoke test the harness**

Create `mobile/src/__tests__/smoke.test.ts`:

```ts
test("jest harness works", () => {
  expect(1 + 1).toBe(2);
});
```

Run: `npm test`
Expected: PASS (1 test). Then run `npm run typecheck` — Expected: no errors.

- [ ] **Step 7: Commit**

```bash
cd ..  # repo root
git add mobile .gitignore
git commit -m "feat(mobile): scaffold Expo TS app + Jest harness

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

(`mobile/node_modules` is ignored, so the commit holds source + lockfile only.)

---

## Task 2: config + secure session store

**Files:** `mobile/src/config.ts`, `mobile/src/auth/session.ts`, tests.

- [ ] **Step 1: Write the failing session test**

Create `mobile/src/auth/__tests__/session.test.ts`:

```ts
import * as SecureStore from "expo-secure-store";
import { saveSession, readSession, clearSession } from "../session";

jest.mock("expo-secure-store");

const mem: Record<string, string> = {};
beforeEach(() => {
  for (const k of Object.keys(mem)) delete mem[k];
  (SecureStore.setItemAsync as jest.Mock).mockImplementation(async (k, v) => {
    mem[k] = v;
  });
  (SecureStore.getItemAsync as jest.Mock).mockImplementation(async (k) => mem[k] ?? null);
  (SecureStore.deleteItemAsync as jest.Mock).mockImplementation(async (k) => {
    delete mem[k];
  });
});

test("save then read round-trips", async () => {
  await saveSession({ access: "a", refresh: "r", apiKey: "hsk_x", email: "u@b.com" });
  expect(await readSession()).toEqual({
    access: "a", refresh: "r", apiKey: "hsk_x", email: "u@b.com",
  });
});

test("clear removes everything", async () => {
  await saveSession({ access: "a", refresh: "r" });
  await clearSession();
  expect(await readSession()).toEqual({
    access: null, refresh: null, apiKey: null, email: null,
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `npm test -- session`
Expected: FAIL — `Cannot find module '../session'`.

- [ ] **Step 3: Implement config + session**

Create `mobile/src/config.ts`:

```ts
const url = process.env.EXPO_PUBLIC_API_URL;

export const API_URL: string = url ?? "http://localhost:8000";

// In dev the default points at localhost; on a device set EXPO_PUBLIC_API_URL to
// the dev machine's LAN IP (or use `expo start --tunnel`).
```

Create `mobile/src/auth/session.ts`:

```ts
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `npm test -- session` → PASS. `npm run typecheck` → no errors.

- [ ] **Step 5: Commit**

```bash
git add mobile/src/config.ts mobile/src/auth/session.ts mobile/src/auth/__tests__/session.test.ts
git commit -m "feat(mobile): config + secure-store session store

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Typed API client with JWT refresh

**Files:** `mobile/src/api/client.ts`, test.

- [ ] **Step 1: Write the failing client test**

Create `mobile/src/api/__tests__/client.test.ts`:

```ts
import { request, ApiError } from "../client";
import * as session from "../../auth/session";

jest.mock("../../auth/session");

beforeEach(() => {
  jest.resetAllMocks();
  (session.readSession as jest.Mock).mockResolvedValue({
    access: "acc", refresh: "ref", apiKey: null, email: null,
  });
  (session.saveSession as jest.Mock).mockResolvedValue(undefined);
  (session.clearSession as jest.Mock).mockResolvedValue(undefined);
});

function jsonResponse(status: number, body: unknown) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

test("GET parses JSON on 2xx", async () => {
  global.fetch = jest.fn().mockResolvedValue(jsonResponse(200, { hello: "world" }));
  const data = await request("/health");
  expect(data).toEqual({ hello: "world" });
  expect(global.fetch).toHaveBeenCalledWith(
    "http://localhost:8000/health",
    expect.objectContaining({ method: "GET" }),
  );
});

test("throws ApiError with detail on 4xx", async () => {
  global.fetch = jest.fn().mockResolvedValue(jsonResponse(422, { detail: "bad" }));
  await expect(request("/x", { method: "POST", body: {} })).rejects.toMatchObject({
    status: 422,
    message: "bad",
  });
});

test("bearer 401 refreshes once then retries", async () => {
  const fetchMock = jest.fn()
    .mockResolvedValueOnce(jsonResponse(401, { detail: "expired" }))      // first protected call
    .mockResolvedValueOnce(jsonResponse(200, { access_token: "new", refresh_token: "newref" })) // refresh
    .mockResolvedValueOnce(jsonResponse(200, { ok: true }));              // retry
  global.fetch = fetchMock;
  const data = await request("/keys", { method: "GET", auth: "bearer" });
  expect(data).toEqual({ ok: true });
  expect(session.saveSession).toHaveBeenCalledWith(
    expect.objectContaining({ access: "new", refresh: "newref" }),
  );
});

test("failed refresh clears session and throws 401", async () => {
  global.fetch = jest.fn()
    .mockResolvedValueOnce(jsonResponse(401, { detail: "expired" }))
    .mockResolvedValueOnce(jsonResponse(401, { detail: "no" }));  // refresh fails
  await expect(request("/keys", { auth: "bearer" })).rejects.toMatchObject({ status: 401 });
  expect(session.clearSession).toHaveBeenCalled();
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `npm test -- client`
Expected: FAIL — `Cannot find module '../client'`.

- [ ] **Step 3: Implement the client**

Create `mobile/src/api/client.ts`:

```ts
import { API_URL } from "../config";
import { readSession, saveSession, clearSession } from "../auth/session";

export class ApiError extends Error {
  status: number;
  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
  }
}

type Auth = "none" | "bearer" | "apiKey";

export type RequestOptions = {
  method?: "GET" | "POST" | "DELETE";
  body?: unknown;
  auth?: Auth;
};

async function authHeaders(auth: Auth): Promise<Record<string, string>> {
  if (auth === "none") return {};
  const s = await readSession();
  if (auth === "bearer") return s.access ? { Authorization: `Bearer ${s.access}` } : {};
  return s.apiKey ? { "X-API-Key": s.apiKey } : {};
}

async function doFetch(path: string, opts: RequestOptions, headers: Record<string, string>) {
  return fetch(`${API_URL}${path}`, {
    method: opts.method ?? "GET",
    headers: { "Content-Type": "application/json", ...headers },
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  });
}

async function refresh(): Promise<boolean> {
  const s = await readSession();
  if (!s.refresh) return false;
  const resp = await fetch(`${API_URL}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: s.refresh }),
  });
  if (!resp.ok) return false;
  const data = await resp.json();
  await saveSession({ access: data.access_token, refresh: data.refresh_token });
  return true;
}

export async function request<T = any>(path: string, opts: RequestOptions = {}): Promise<T> {
  const auth = opts.auth ?? "none";
  let resp = await doFetch(path, opts, await authHeaders(auth));

  if (resp.status === 401 && auth === "bearer") {
    if (await refresh()) {
      resp = await doFetch(path, opts, await authHeaders(auth));
    } else {
      await clearSession();
    }
  }

  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new ApiError(resp.status, (data && data.detail) || "Request failed");
  return data as T;
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `npm test -- client` → PASS. `npm run typecheck` → no errors.

- [ ] **Step 5: Commit**

```bash
git add mobile/src/api/client.ts mobile/src/api/__tests__/client.test.ts
git commit -m "feat(mobile): typed API client with JWT auto-refresh

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Auth + keys endpoint wrappers

**Files:** `mobile/src/api/auth.ts`, `mobile/src/api/keys.ts`, tests.

- [ ] **Step 1: Write the failing tests**

Create `mobile/src/api/__tests__/keys.test.ts`:

```ts
import { ensureApiKey } from "../keys";
import * as client from "../client";
import * as session from "../../auth/session";

jest.mock("../client");
jest.mock("../../auth/session");

beforeEach(() => jest.resetAllMocks());

test("reuses a stored key without calling the API", async () => {
  (session.readSession as jest.Mock).mockResolvedValue({ apiKey: "hsk_existing" });
  const key = await ensureApiKey();
  expect(key).toBe("hsk_existing");
  expect(client.request).not.toHaveBeenCalled();
});

test("creates and stores a key when none exists", async () => {
  (session.readSession as jest.Mock).mockResolvedValue({ apiKey: null });
  (client.request as jest.Mock).mockResolvedValue({ api_key: "hsk_new" });
  (session.saveSession as jest.Mock).mockResolvedValue(undefined);
  const key = await ensureApiKey();
  expect(key).toBe("hsk_new");
  expect(client.request).toHaveBeenCalledWith("/keys", expect.objectContaining({
    method: "POST", auth: "bearer",
  }));
  expect(session.saveSession).toHaveBeenCalledWith({ apiKey: "hsk_new" });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `npm test -- keys`
Expected: FAIL — `Cannot find module '../keys'`.

- [ ] **Step 3: Implement the wrappers**

Create `mobile/src/api/auth.ts`:

```ts
import { request } from "./client";

export type Tokens = { access_token: string; refresh_token: string };
export type Me = { id: number; email: string; role: string };

export function registerUser(email: string, password: string): Promise<unknown> {
  return request("/auth/register", { method: "POST", body: { email, password } });
}

export function login(email: string, password: string): Promise<Tokens> {
  return request<Tokens>("/auth/login", { method: "POST", body: { email, password } });
}

export function me(): Promise<Me> {
  return request<Me>("/auth/me", { auth: "bearer" });
}

export function logout(): Promise<unknown> {
  return request("/auth/logout", { method: "POST", auth: "bearer" }).catch(() => ({}));
}
```

Create `mobile/src/api/keys.ts`:

```ts
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `npm test -- keys` → PASS. `npm run typecheck` → no errors.

- [ ] **Step 5: Commit**

```bash
git add mobile/src/api/auth.ts mobile/src/api/keys.ts mobile/src/api/__tests__/keys.test.ts
git commit -m "feat(mobile): auth + auto-managed API key wrappers

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: AuthProvider (session context)

**Files:** `mobile/src/auth/AuthProvider.tsx`, test.

- [ ] **Step 1: Write the failing test**

Create `mobile/src/auth/__tests__/AuthProvider.test.tsx`:

```tsx
import React from "react";
import { Text } from "react-native";
import { render, waitFor, act } from "@testing-library/react-native";
import { AuthProvider, useAuth } from "../AuthProvider";
import * as authApi from "../../api/auth";
import * as keysApi from "../../api/keys";
import * as session from "../session";

jest.mock("../../api/auth");
jest.mock("../../api/keys");
jest.mock("../session");

function Probe() {
  const { status, email, signIn, signOut } = useAuth();
  return (
    <>
      <Text testID="status">{status}</Text>
      <Text testID="email">{email ?? "none"}</Text>
      <Text testID="signin" onPress={() => signIn("u@b.com", "pw")}>signin</Text>
      <Text testID="signout" onPress={() => signOut()}>signout</Text>
    </>
  );
}

beforeEach(() => {
  jest.resetAllMocks();
  (session.readSession as jest.Mock).mockResolvedValue({ access: null, refresh: null, apiKey: null, email: null });
  (session.saveSession as jest.Mock).mockResolvedValue(undefined);
  (session.clearSession as jest.Mock).mockResolvedValue(undefined);
});

test("starts unauthenticated when no stored session", async () => {
  const { getByTestId } = render(<AuthProvider><Probe /></AuthProvider>);
  await waitFor(() => expect(getByTestId("status").props.children).toBe("unauthenticated"));
});

test("signIn logs in, ensures a key, and stores email", async () => {
  (authApi.login as jest.Mock).mockResolvedValue({ access_token: "a", refresh_token: "r" });
  (authApi.me as jest.Mock).mockResolvedValue({ id: 1, email: "u@b.com", role: "user" });
  (keysApi.ensureApiKey as jest.Mock).mockResolvedValue("hsk_x");
  const { getByTestId } = render(<AuthProvider><Probe /></AuthProvider>);
  await waitFor(() => expect(getByTestId("status").props.children).toBe("unauthenticated"));
  await act(async () => { getByTestId("signin").props.onPress(); });
  await waitFor(() => expect(getByTestId("status").props.children).toBe("authenticated"));
  expect(getByTestId("email").props.children).toBe("u@b.com");
  expect(session.saveSession).toHaveBeenCalledWith(expect.objectContaining({ access: "a", refresh: "r", email: "u@b.com" }));
  expect(keysApi.ensureApiKey).toHaveBeenCalled();
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `npm test -- AuthProvider`
Expected: FAIL — `Cannot find module '../AuthProvider'`.

- [ ] **Step 3: Implement the provider**

Create `mobile/src/auth/AuthProvider.tsx`:

```tsx
import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { login as apiLogin, me as apiMe, logout as apiLogout } from "../api/auth";
import { ensureApiKey } from "../api/keys";
import { readSession, saveSession, clearSession } from "./session";

type Status = "loading" | "authenticated" | "unauthenticated";

type AuthValue = {
  status: Status;
  email: string | null;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<Status>("loading");
  const [email, setEmail] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      const s = await readSession();
      if (s.access) {
        setEmail(s.email);
        setStatus("authenticated");
      } else {
        setStatus("unauthenticated");
      }
    })();
  }, []);

  const signIn = useCallback(async (e: string, password: string) => {
    const tokens = await apiLogin(e, password);
    await saveSession({ access: tokens.access_token, refresh: tokens.refresh_token });
    const profile = await apiMe();
    await saveSession({ email: profile.email });
    await ensureApiKey();
    setEmail(profile.email);
    setStatus("authenticated");
  }, []);

  const signOut = useCallback(async () => {
    await apiLogout();
    await clearSession();
    setEmail(null);
    setStatus("unauthenticated");
  }, []);

  return (
    <AuthContext.Provider value={{ status, email, signIn, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `npm test -- AuthProvider` → PASS. `npm run typecheck` → no errors.

- [ ] **Step 5: Commit**

```bash
git add mobile/src/auth/AuthProvider.tsx mobile/src/auth/__tests__/AuthProvider.test.tsx
git commit -m "feat(mobile): AuthProvider session context (restore/signIn/signOut)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: expo-router screens + navigation guard

**Files:** replace/create under `mobile/app/`; a login component test.

- [ ] **Step 1: Write the failing login screen test**

Create `mobile/app/(auth)/__tests__/login.test.tsx` (adjust the import path to wherever the login screen lives):

```tsx
import React from "react";
import { render, fireEvent, waitFor } from "@testing-library/react-native";
import LoginScreen from "../login";
import { AuthProvider } from "../../../src/auth/AuthProvider";
import * as authApi from "../../../src/api/auth";
import * as session from "../../../src/auth/session";

jest.mock("../../../src/api/auth");
jest.mock("../../../src/api/keys");
jest.mock("../../../src/auth/session");
jest.mock("expo-router", () => ({ Link: ({ children }: any) => children, router: { replace: jest.fn() } }));

beforeEach(() => {
  jest.resetAllMocks();
  (session.readSession as jest.Mock).mockResolvedValue({ access: null, refresh: null, apiKey: null, email: null });
  (session.saveSession as jest.Mock).mockResolvedValue(undefined);
});

test("submitting shows the API error", async () => {
  (authApi.login as jest.Mock).mockRejectedValue(Object.assign(new Error("Invalid credentials"), { status: 401 }));
  const { getByTestId, findByText } = render(<AuthProvider><LoginScreen /></AuthProvider>);
  fireEvent.changeText(getByTestId("email"), "u@b.com");
  fireEvent.changeText(getByTestId("password"), "wrong");
  fireEvent.press(getByTestId("submit"));
  expect(await findByText(/Invalid credentials/)).toBeTruthy();
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `npm test -- login`
Expected: FAIL — login screen module not found.

- [ ] **Step 3: Create the routes**

Replace the generated example routes. Create `mobile/app/_layout.tsx`:

```tsx
import React from "react";
import { Slot } from "expo-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "../src/auth/AuthProvider";

const queryClient = new QueryClient();

export default function RootLayout() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <Slot />
      </AuthProvider>
    </QueryClientProvider>
  );
}
```

Create `mobile/app/index.tsx` (the navigation guard):

```tsx
import React from "react";
import { ActivityIndicator, View } from "react-native";
import { Redirect } from "expo-router";
import { useAuth } from "../src/auth/AuthProvider";

export default function Index() {
  const { status } = useAuth();
  if (status === "loading") {
    return (
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center" }}>
        <ActivityIndicator />
      </View>
    );
  }
  return <Redirect href={status === "authenticated" ? "/(app)" : "/(auth)/login"} />;
}
```

Create `mobile/app/(auth)/login.tsx`:

```tsx
import React, { useState } from "react";
import { View, Text, TextInput, Button } from "react-native";
import { Link, router } from "expo-router";
import { useAuth } from "../../src/auth/AuthProvider";

export default function LoginScreen() {
  const { signIn } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function onSubmit() {
    setError(null);
    try {
      await signIn(email, password);
      router.replace("/(app)");
    } catch (e: any) {
      setError(e?.message ?? "Login failed");
    }
  }

  return (
    <View style={{ flex: 1, padding: 24, justifyContent: "center", gap: 12 }}>
      <Text style={{ fontSize: 24, fontWeight: "600" }}>Log in</Text>
      <TextInput testID="email" placeholder="Email" autoCapitalize="none"
        keyboardType="email-address" value={email} onChangeText={setEmail}
        style={{ borderWidth: 1, borderColor: "#ccc", padding: 10, borderRadius: 6 }} />
      <TextInput testID="password" placeholder="Password" secureTextEntry
        value={password} onChangeText={setPassword}
        style={{ borderWidth: 1, borderColor: "#ccc", padding: 10, borderRadius: 6 }} />
      {error ? <Text style={{ color: "red" }}>{error}</Text> : null}
      <Button testID="submit" title="Log in" onPress={onSubmit} />
      <Link href="/(auth)/register">Need an account? Register</Link>
    </View>
  );
}
```

Create `mobile/app/(auth)/register.tsx`:

```tsx
import React, { useState } from "react";
import { View, Text, TextInput, Button } from "react-native";
import { Link, router } from "expo-router";
import { registerUser } from "../../src/api/auth";
import { useAuth } from "../../src/auth/AuthProvider";

export default function RegisterScreen() {
  const { signIn } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function onSubmit() {
    setError(null);
    try {
      await registerUser(email, password);
      await signIn(email, password);
      router.replace("/(app)");
    } catch (e: any) {
      setError(e?.message ?? "Registration failed");
    }
  }

  return (
    <View style={{ flex: 1, padding: 24, justifyContent: "center", gap: 12 }}>
      <Text style={{ fontSize: 24, fontWeight: "600" }}>Create account</Text>
      <TextInput testID="email" placeholder="Email" autoCapitalize="none"
        keyboardType="email-address" value={email} onChangeText={setEmail}
        style={{ borderWidth: 1, borderColor: "#ccc", padding: 10, borderRadius: 6 }} />
      <TextInput testID="password" placeholder="Password" secureTextEntry
        value={password} onChangeText={setPassword}
        style={{ borderWidth: 1, borderColor: "#ccc", padding: 10, borderRadius: 6 }} />
      {error ? <Text style={{ color: "red" }}>{error}</Text> : null}
      <Button testID="submit" title="Register" onPress={onSubmit} />
      <Link href="/(auth)/login">Have an account? Log in</Link>
    </View>
  );
}
```

Create `mobile/app/(app)/_layout.tsx` (the authenticated shell):

```tsx
import React from "react";
import { Redirect, Tabs } from "expo-router";
import { useAuth } from "../../src/auth/AuthProvider";

export default function AppLayout() {
  const { status } = useAuth();
  if (status === "loading") return null;
  if (status === "unauthenticated") return <Redirect href="/(auth)/login" />;
  return (
    <Tabs screenOptions={{ headerShown: true }}>
      <Tabs.Screen name="index" options={{ title: "Home" }} />
      <Tabs.Screen name="history" options={{ title: "History" }} />
      <Tabs.Screen name="settings" options={{ title: "Settings" }} />
    </Tabs>
  );
}
```

Create `mobile/app/(app)/index.tsx`:

```tsx
import React from "react";
import { View, Text } from "react-native";

export default function Home() {
  return (
    <View style={{ flex: 1, alignItems: "center", justifyContent: "center", padding: 24 }}>
      <Text style={{ fontSize: 18 }}>Scanning lands in the next sub-project.</Text>
    </View>
  );
}
```

Create `mobile/app/(app)/history.tsx`:

```tsx
import React from "react";
import { View, Text } from "react-native";

export default function History() {
  return (
    <View style={{ flex: 1, alignItems: "center", justifyContent: "center", padding: 24 }}>
      <Text style={{ fontSize: 18 }}>Scan history will appear here.</Text>
    </View>
  );
}
```

Create `mobile/app/(app)/settings.tsx`:

```tsx
import React from "react";
import { View, Text, Button } from "react-native";
import { router } from "expo-router";
import { useAuth } from "../../src/auth/AuthProvider";

export default function Settings() {
  const { email, signOut } = useAuth();
  return (
    <View style={{ flex: 1, padding: 24, gap: 16, justifyContent: "center" }}>
      <Text style={{ fontSize: 16 }}>Signed in as {email ?? "—"}</Text>
      <Button title="Log out" onPress={async () => { await signOut(); router.replace("/(auth)/login"); }} />
    </View>
  );
}
```

Delete any leftover example routes from the template (e.g. `app/(tabs)`, `app/+not-found.tsx` references) that conflict. Keep the route tree exactly as above.

- [ ] **Step 4: Run to verify it passes**

Run: `npm test` (all suites) → PASS. `npm run typecheck` → no errors.

- [ ] **Step 5: Commit**

```bash
git add mobile/app
git commit -m "feat(mobile): auth + app routes with a session navigation guard

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: README, checkpoint, final verification

- [ ] **Step 1: Full verification**

From `mobile/`: `npm test` (all green) and `npm run typecheck` (no errors). Report counts.

- [ ] **Step 2: Mobile README**

Create `mobile/README.md` documenting: prerequisites (Node, Expo Go), `npm install`, setting `EXPO_PUBLIC_API_URL` to the backend (LAN IP or `expo start --tunnel`), `npx expo start`, and `npm test` / `npm run typecheck`. Note the backend must be running and reachable.

- [ ] **Step 3: Update the project checkpoint**

Edit `docs/CHECKPOINT.md`: refresh the branch section (SP16 merged; SP17 in flight); under "What's built" add an SP17 entry (the `mobile/` Expo app: scaffold, API client + refresh, secure session, auth flow, auto-managed key, nav shell, Jest tests); note the Python test count is unchanged (mobile tests run via `cd mobile && npm test`); set the next step to SP18 (scanning screens) and note the design/vibe is still to be shared.

- [ ] **Step 4: Commit**

```bash
git add mobile/README.md docs/CHECKPOINT.md docs/superpowers/plans/2026-06-03-mobile-foundation.md
git commit -m "docs(mobile): SP17 done — Expo foundation (auth + nav shell)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Notes for the implementer

- The Python backend and its pytest suite are untouched; this sub-project is entirely under `mobile/`.
- Expo SDK versions evolve; if a generated file or an API differs from this plan, adapt — the intent (file responsibilities, tests, auth flow) is what matters.
- `mobile/node_modules` is gitignored; commit source + `package-lock.json` only.
- The app cannot be run in this environment. "Done" = `npm test` green + `npm run typecheck` clean; the user verifies on-device.
- Every commit message ends with the trailer:
  `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`
- This branch is from `main`; final `--no-ff` merge to `main` after review.
