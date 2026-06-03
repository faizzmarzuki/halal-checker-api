# Halal Checker — Mobile app

React Native + Expo (iOS + Android) client for the Halal Checker API. This is the
**foundation** (SP17): auth, secure session, an auto-managed API key, and an
authenticated navigation shell. Screens are functional with minimal styling — the
visual design and the scanning / history screens come in later sub-projects.

## Stack

- Expo (SDK 55, managed) + TypeScript
- expo-router (file-based routes under `src/app/`)
- @tanstack/react-query (server state)
- expo-secure-store (tokens + API key)
- Jest + jest-expo + @testing-library/react-native (tests)

## Prerequisites

- Node 18+ and npm
- The [Expo Go](https://expo.dev/go) app on your phone (or an iOS/Android simulator)
- The **backend running and reachable** (see the repo root README to start the API)

## Setup

```bash
cd mobile
npm install
```

## Point the app at the backend

The app reads `EXPO_PUBLIC_API_URL` (default `http://localhost:8000`). A phone
cannot reach the dev machine's `localhost`, so set it to a reachable address:

```bash
# LAN: use your dev machine's IP, with the backend bound to 0.0.0.0
EXPO_PUBLIC_API_URL="http://192.168.1.50:8000" npx expo start

# or a tunnel (works off-LAN):
npx expo start --tunnel
```

The backend must be running with `HALAL_JWT_SECRET` set. If a device origin needs
CORS, set `HALAL_CORS_ORIGINS` on the backend.

## Run

```bash
npx expo start            # then scan the QR with Expo Go, or press i / a
```

Register or log in; the app stores your tokens securely and transparently creates
an API key for scanning (used by the scanning screens in a later sub-project).

## Develop

```bash
npm test          # Jest (unit + component tests)
npm run typecheck # tsc --noEmit
```

## Layout

```
src/
  config.ts              # EXPO_PUBLIC_API_URL
  api/client.ts          # typed fetch + JWT auto-refresh
  api/auth.ts            # register / login / logout / me
  api/keys.ts            # ensureApiKey() (auto-managed)
  auth/session.ts        # secure-store token + key storage
  auth/AuthProvider.tsx  # session context
  app/                   # expo-router routes (root layout, (auth), (app) shell)
```
