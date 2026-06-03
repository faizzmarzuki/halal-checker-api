# Sub-project 17 — Mobile App Foundation (Design)

Date: 2026-06-03

The first piece of the mobile client: a React Native + Expo (iOS + Android) app
that can register, log in, hold a session, and navigate an authenticated shell.
Built in a new `mobile/` directory inside this repo (monorepo: Python backend +
Expo app). Screens are functional with minimal styling — the visual design is a
later sub-project once the design/vibe is shared.

## Goals & non-goals

In: Expo TS scaffold, navigation shell, a typed API client (with JWT auto-refresh),
secure token storage, the auth flow (register / login / logout), automatic API-key
management, a navigation guard, and a Jest test setup with unit/component tests.

Out: scanning and history screens (SP18 / SP19), visual design/styling, backend
deployment, push notifications, and the email-verify / password-reset UI.

## Tech stack (chosen)

- **Expo** (managed workflow), **TypeScript**.
- **expo-router** — file-based navigation.
- **TanStack Query** (`@tanstack/react-query`) — server state / mutations.
- **expo-secure-store** — secure storage for tokens and the API key.
- **Jest** + **jest-expo** preset + **@testing-library/react-native** — headless
  unit/component tests (these run in this environment; the actual app is run
  on-device by the user via Expo Go).

## Constraint: no on-device run here

This environment can scaffold, typecheck (`tsc`), lint, and run Jest — but it
cannot run the app on a simulator/device. On-device verification (login working,
navigation, etc.) is the user's step: set `EXPO_PUBLIC_API_URL` to the dev
machine's LAN IP (or use `expo start --tunnel`) with the backend running, and
open it in Expo Go.

## Directory structure (`mobile/`)

```
mobile/
  app.config.ts            # Expo config; exposes EXPO_PUBLIC_API_URL
  package.json
  tsconfig.json
  babel.config.js
  jest.config.js / jest setup
  app/                     # expo-router routes
    _layout.tsx            # root: QueryClientProvider + AuthProvider; redirects by auth
    index.tsx              # entry: redirect to (app) or (auth) by session
    (auth)/_layout.tsx
    (auth)/login.tsx
    (auth)/register.tsx
    (app)/_layout.tsx      # authenticated shell (tabs: Home / History / Settings)
    (app)/index.tsx        # Home placeholder ("scanning lands in SP18")
    (app)/history.tsx      # placeholder
    (app)/settings.tsx     # shows the signed-in email + Logout
  src/
    config.ts              # reads EXPO_PUBLIC_API_URL (throws if unset)
    api/client.ts          # typed fetch wrapper (base URL, JSON, errors, Bearer, refresh)
    api/auth.ts            # register / login / logout / refresh / me
    api/keys.ts            # ensureApiKey()
    auth/session.ts        # pure session store: persist/read/clear tokens + api key
    auth/AuthProvider.tsx  # React context: restore on launch, login(), logout(), state
  __tests__/ (or co-located *.test.ts(x))
```

Each unit has one job: `client.ts` talks HTTP, `session.ts` persists secrets,
`auth.ts`/`keys.ts` are thin endpoint wrappers, `AuthProvider` holds in-memory
state and orchestrates the others. This keeps the HTTP and storage layers
independently testable with mocks.

## API client (`src/api/client.ts`)

A small typed wrapper over `fetch`:

- Reads the base URL from `config.ts`.
- `request(path, { method, body, auth })` → sets `Content-Type: application/json`,
  serializes the body, parses the JSON response, and on a non-2xx throws an
  `ApiError(status, detail)` (detail read from the API's `{"detail": ...}`).
- When `auth: "bearer"`, attaches `Authorization: Bearer <access>` from the
  session.
- **Auto-refresh:** on a 401 from a bearer call, it calls `POST /auth/refresh`
  with the stored refresh token, updates the session (the backend rotates refresh
  tokens — store the new pair), and retries the original request **once**. If the
  refresh also fails, it clears the session and surfaces the 401 so the app routes
  back to login.
- Scanning calls (later) will use `auth: "apiKey"` → `X-API-Key` header; the
  header plumbing is added now, used in SP18.

## Auth + API-key flow

1. **Register** → `POST /auth/register`, then log in.
2. **Login** → `POST /auth/login` → persist the access + refresh tokens
   (secure-store), fetch `GET /auth/me` for the user, then call `ensureApiKey()`.
3. **ensureApiKey()** (`src/api/keys.ts`): if a raw key is already in secure-store,
   reuse it; otherwise `POST /keys` (JWT) with name `"mobile-app"`, then persist the
   returned **raw key** (it is shown only once at creation). The user never sees or
   types a key — scanning in SP18 reads it from the session.
4. **Logout** → `POST /auth/logout` (best-effort), then clear secure-store and
   in-memory state.

## Session store (`src/auth/session.ts`)

A pure module over `expo-secure-store`:

- `save({ access, refresh, apiKey?, email? })`, `read()`, `clear()`.
- Stores under namespaced keys (e.g. `hs.access`, `hs.refresh`, `hs.apiKey`,
  `hs.email`). No React in this module — it's mockable in tests.

## Navigation guard

The root `app/index.tsx` (and/or `_layout.tsx`) redirects: while the session is
loading show a splash, then route to `(app)` if authenticated or `(auth)/login`
if not. Settings' Logout returns to `(auth)/login`.

## Testing (Jest + RNTL — run headless here)

- `api/client`: builds the right URL/method/headers/body (mock `fetch`); parses a
  2xx JSON; throws `ApiError` with the API detail on 4xx; the refresh path —
  a 401 triggers one refresh + one retry, and a failed refresh clears the session.
- `auth/session`: `save` then `read` round-trips; `clear` removes everything
  (mock `expo-secure-store`).
- `api/keys`: `ensureApiKey` reuses a stored key (no POST) and creates + stores
  one when absent (mock the client).
- `AuthProvider`: `login` populates state + persists; `logout` clears.
- Component: the login screen renders fields, a submit calls the login mutation,
  and an API error shows a message (`@testing-library/react-native`).

Commands: `npm run typecheck` (`tsc --noEmit`), `npm test` (jest). These define
"done" in CI/headless terms; on-device behaviour is the user's check.

## Out-of-scope reachability note

The backend is still local-only. For the user to log in from the app, point
`EXPO_PUBLIC_API_URL` at a reachable address (LAN IP or tunnel). A dedicated
"deploy the backend" sub-project comes later.

## Conventions

Branch `sub-project-17-mobile-foundation` (from `main`); spec here; plan in
`docs/superpowers/plans/`; `mobile/node_modules` is gitignored; TDD where it
applies (Jest); `--no-ff` merge to `main`; delete the branch. Commit trailer:
`Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
