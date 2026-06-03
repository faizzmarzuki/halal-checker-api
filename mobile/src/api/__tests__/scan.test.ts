import { classify } from "../scan";
import { request, ApiError } from "../client";
import * as keys from "../keys";
import * as session from "../../auth/session";

jest.mock("../client", () => {
  const actual = jest.requireActual("../client");
  return { ...actual, request: jest.fn() };
});
jest.mock("../keys");
jest.mock("../../auth/session");

const verdict = {
  verdict: "haram",
  ingredients: [
    { input: "lard", canonical: "lard", status: "haram", source: "rulebook",
      confidence: "high", reason: "pork fat", citation: "x" },
  ],
  summary: "Contains haram ingredients.",
  disclaimer: "Not a religious ruling.",
};

beforeEach(() => {
  jest.resetAllMocks();
  (keys.ensureApiKey as jest.Mock).mockResolvedValue("hsk_new");
  (session.clearApiKey as jest.Mock).mockResolvedValue(undefined);
});

test("classify posts ingredients with the api key and returns the verdict", async () => {
  (request as jest.Mock).mockResolvedValue(verdict);
  const result = await classify(["lard"]);
  expect(result).toEqual(verdict);
  expect(request).toHaveBeenCalledWith("/classify", {
    method: "POST",
    auth: "apiKey",
    body: { ingredients: ["lard"], use_gemma: true, translate: false },
  });
});

test("a 401 re-mints the key and retries once", async () => {
  (request as jest.Mock)
    .mockRejectedValueOnce(new ApiError(401, "bad key"))
    .mockResolvedValueOnce(verdict);
  const result = await classify(["lard"]);
  expect(result).toEqual(verdict);
  expect(session.clearApiKey).toHaveBeenCalled();
  expect(keys.ensureApiKey).toHaveBeenCalled();
  expect(request).toHaveBeenCalledTimes(2);
});

test("a non-401 error rethrows without recovery", async () => {
  (request as jest.Mock).mockRejectedValue(new ApiError(422, "bad input"));
  await expect(classify([""])).rejects.toMatchObject({ status: 422 });
  expect(keys.ensureApiKey).not.toHaveBeenCalled();
});

test("a second 401 after recovery propagates", async () => {
  (request as jest.Mock).mockRejectedValue(new ApiError(401, "still bad"));
  await expect(classify(["lard"])).rejects.toMatchObject({ status: 401 });
  expect(request).toHaveBeenCalledTimes(2);
});
