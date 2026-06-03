import { timeAgo } from "../time";

const now = Date.parse("2026-06-03T12:00:00Z");
const at = (iso: string) => timeAgo(iso, now);

test("formats relative times", () => {
  expect(at("2026-06-03T11:59:40Z")).toBe("just now"); // 20s
  expect(at("2026-06-03T11:55:00Z")).toBe("5m ago");
  expect(at("2026-06-03T09:00:00Z")).toBe("3h ago");
  expect(at("2026-06-01T12:00:00Z")).toBe("2d ago");
});
