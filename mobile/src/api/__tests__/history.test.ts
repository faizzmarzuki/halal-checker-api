import { listHistory, deleteHistory, clearHistory } from "../history";
import { request } from "../client";

jest.mock("../client", () => {
  const actual = jest.requireActual("../client");
  return { ...actual, request: jest.fn() };
});

beforeEach(() => (request as jest.Mock).mockReset());

test("listHistory fetches the latest page with the bearer token", async () => {
  const rows = [{ id: 1, scan_type: "classify", summary: "sugar", verdict: "halal", created_at: "2026-06-03T00:00:00Z" }];
  (request as jest.Mock).mockResolvedValue(rows);
  const result = await listHistory();
  expect(result).toEqual(rows);
  expect(request).toHaveBeenCalledWith("/history?limit=50&offset=0", { auth: "bearer" });
});

test("deleteHistory deletes one row", async () => {
  (request as jest.Mock).mockResolvedValue({});
  await deleteHistory(7);
  expect(request).toHaveBeenCalledWith("/history/7", { method: "DELETE", auth: "bearer" });
});

test("clearHistory deletes all rows", async () => {
  (request as jest.Mock).mockResolvedValue({});
  await clearHistory();
  expect(request).toHaveBeenCalledWith("/history", { method: "DELETE", auth: "bearer" });
});
