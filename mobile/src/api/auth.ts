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
