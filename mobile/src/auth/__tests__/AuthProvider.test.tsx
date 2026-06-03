import React from "react";
import { Text } from "react-native";
import { render, waitFor, act } from "@testing-library/react-native";
import { AuthProvider, useAuth } from "../AuthProvider";
import * as authApi from "../../api/auth";
import * as keysApi from "../../api/keys";
import * as session from "../session";

jest.mock("../../api/auth");
jest.mock("../../api/keys");
jest.mock("../session");

function Probe() {
  const { status, email, signIn, signOut } = useAuth();
  return (
    <>
      <Text testID="status">{status}</Text>
      <Text testID="email">{email ?? "none"}</Text>
      <Text testID="signin" onPress={() => signIn("u@b.com", "pw")}>signin</Text>
      <Text testID="signout" onPress={() => signOut()}>signout</Text>
    </>
  );
}

beforeEach(() => {
  jest.resetAllMocks();
  (session.readSession as jest.Mock).mockResolvedValue({ access: null, refresh: null, apiKey: null, email: null });
  (session.saveSession as jest.Mock).mockResolvedValue(undefined);
  (session.clearSession as jest.Mock).mockResolvedValue(undefined);
});

test("starts unauthenticated when no stored session", async () => {
  const { getByTestId } = render(<AuthProvider><Probe /></AuthProvider>);
  await waitFor(() => expect(getByTestId("status").props.children).toBe("unauthenticated"));
});

test("signIn logs in, ensures a key, and stores email", async () => {
  (authApi.login as jest.Mock).mockResolvedValue({ access_token: "a", refresh_token: "r" });
  (authApi.me as jest.Mock).mockResolvedValue({ id: 1, email: "u@b.com", role: "user" });
  (keysApi.ensureApiKey as jest.Mock).mockResolvedValue("hsk_x");
  const { getByTestId } = render(<AuthProvider><Probe /></AuthProvider>);
  await waitFor(() => expect(getByTestId("status").props.children).toBe("unauthenticated"));
  await act(async () => { getByTestId("signin").props.onPress(); });
  await waitFor(() => expect(getByTestId("status").props.children).toBe("authenticated"));
  expect(getByTestId("email").props.children).toBe("u@b.com");
  // Tokens are persisted before /auth/me runs, then the email in a second save.
  expect(session.saveSession).toHaveBeenCalledWith(expect.objectContaining({ access: "a", refresh: "r" }));
  expect(session.saveSession).toHaveBeenCalledWith({ email: "u@b.com" });
  expect(keysApi.ensureApiKey).toHaveBeenCalled();
});
