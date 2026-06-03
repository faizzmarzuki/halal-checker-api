import React from "react";
import { render, fireEvent } from "@testing-library/react-native";
import LoginScreen from "../login";
import { AuthProvider } from "@/auth/AuthProvider";
import * as authApi from "@/api/auth";
import * as session from "@/auth/session";

jest.mock("@/api/auth");
jest.mock("@/api/keys");
jest.mock("@/auth/session");
jest.mock("expo-router", () => ({
  Link: ({ children }: any) => children,
  router: { replace: jest.fn() },
}));

beforeEach(() => {
  jest.resetAllMocks();
  (session.readSession as jest.Mock).mockResolvedValue({ access: null, refresh: null, apiKey: null, email: null });
  (session.saveSession as jest.Mock).mockResolvedValue(undefined);
});

test("submitting shows the API error", async () => {
  (authApi.login as jest.Mock).mockRejectedValue(
    Object.assign(new Error("Invalid credentials"), { status: 401 }),
  );
  const { getByTestId, findByText } = render(
    <AuthProvider><LoginScreen /></AuthProvider>,
  );
  fireEvent.changeText(getByTestId("email"), "u@b.com");
  fireEvent.changeText(getByTestId("password"), "wrong");
  fireEvent.press(getByTestId("submit"));
  expect(await findByText(/Invalid credentials/)).toBeTruthy();
});
