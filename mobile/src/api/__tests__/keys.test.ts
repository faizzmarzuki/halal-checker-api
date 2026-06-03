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
