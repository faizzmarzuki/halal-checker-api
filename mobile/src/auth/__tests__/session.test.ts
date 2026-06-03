import * as SecureStore from "expo-secure-store";
import { saveSession, readSession, clearSession } from "../session";

jest.mock("expo-secure-store");

const mem: Record<string, string> = {};
beforeEach(() => {
  for (const k of Object.keys(mem)) delete mem[k];
  (SecureStore.setItemAsync as jest.Mock).mockImplementation(async (k, v) => {
    mem[k] = v;
  });
  (SecureStore.getItemAsync as jest.Mock).mockImplementation(async (k) => mem[k] ?? null);
  (SecureStore.deleteItemAsync as jest.Mock).mockImplementation(async (k) => {
    delete mem[k];
  });
});

test("save then read round-trips", async () => {
  await saveSession({ access: "a", refresh: "r", apiKey: "hsk_x", email: "u@b.com" });
  expect(await readSession()).toEqual({
    access: "a", refresh: "r", apiKey: "hsk_x", email: "u@b.com",
  });
});

test("clear removes everything", async () => {
  await saveSession({ access: "a", refresh: "r" });
  await clearSession();
  expect(await readSession()).toEqual({
    access: null, refresh: null, apiKey: null, email: null,
  });
});
