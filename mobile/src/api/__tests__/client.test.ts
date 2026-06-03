import { request } from "../client";
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
    .mockResolvedValueOnce(jsonResponse(401, { detail: "expired" }))
    .mockResolvedValueOnce(jsonResponse(200, { access_token: "new", refresh_token: "newref" }))
    .mockResolvedValueOnce(jsonResponse(200, { ok: true }));
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
    .mockResolvedValueOnce(jsonResponse(401, { detail: "no" }));
  await expect(request("/keys", { auth: "bearer" })).rejects.toMatchObject({ status: 401 });
  expect(session.clearSession).toHaveBeenCalled();
});
