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

export function logout(refresh: string): Promise<unknown> {
  // /auth/logout revokes the refresh token (it takes the token in the body and is
  // not JWT-protected). Best-effort: never block a local sign-out on it.
  return request("/auth/logout", { method: "POST", body: { refresh_token: refresh } })
    .catch(() => ({}));
}
