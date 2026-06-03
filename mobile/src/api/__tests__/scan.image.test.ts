import { uploadAsync, FileSystemUploadType } from "expo-file-system/legacy";
import { scanImage } from "../scan";
import { ApiError } from "../client";

jest.mock("expo-file-system/legacy", () => ({
  uploadAsync: jest.fn(),
  FileSystemUploadType: { BINARY_CONTENT: 0 },
}));
jest.mock("../../auth/session", () => ({
  readSession: jest.fn(async () => ({ apiKey: "key-123" })),
  clearApiKey: jest.fn(async () => {}),
}));
jest.mock("../keys", () => ({ ensureApiKey: jest.fn(async () => {}) }));

const session = require("../../auth/session");
const keys = require("../keys");

const ok = {
  verdict: "halal",
  ingredients: [],
  summary: "All clear.",
  disclaimer: "Not a religious ruling.",
  extracted_text: "sugar, salt",
};

beforeEach(() => jest.clearAllMocks());

test("uploads raw bytes with the api key and returns the verdict", async () => {
  (uploadAsync as jest.Mock).mockResolvedValue({ status: 200, body: JSON.stringify(ok) });
  const result = await scanImage("file:///tmp/label.jpg");
  expect(result).toEqual(ok);
  const [url, fileUri, options] = (uploadAsync as jest.Mock).mock.calls[0];
  expect(url).toContain("/scan-image");
  expect(fileUri).toBe("file:///tmp/label.jpg");
  expect(options.httpMethod).toBe("POST");
  expect(options.uploadType).toBe(FileSystemUploadType.BINARY_CONTENT);
  expect(options.headers["X-API-Key"]).toBe("key-123");
});

test("throws ApiError with the backend detail on non-2xx", async () => {
  (uploadAsync as jest.Mock).mockResolvedValue({
    status: 422,
    body: JSON.stringify({ detail: "Could not read any text" }),
  });
  await expect(scanImage("file:///tmp/blurry.jpg")).rejects.toMatchObject({
    name: "ApiError",
    status: 422,
    message: "Could not read any text",
  });
});

test("on 401 it re-mints the key and retries once", async () => {
  (uploadAsync as jest.Mock)
    .mockResolvedValueOnce({ status: 401, body: JSON.stringify({ detail: "Invalid API key" }) })
    .mockResolvedValueOnce({ status: 200, body: JSON.stringify(ok) });
  const result = await scanImage("file:///tmp/label.jpg");
  expect(result).toEqual(ok);
  expect(session.clearApiKey).toHaveBeenCalledTimes(1);
  expect(keys.ensureApiKey).toHaveBeenCalledTimes(1);
  expect((uploadAsync as jest.Mock).mock.calls.length).toBe(2);
});
