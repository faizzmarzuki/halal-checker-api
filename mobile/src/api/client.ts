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

async function doFetch(
  path: string,
  opts: RequestOptions,
  headers: Record<string, string>,
): Promise<Response> {
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
