import React from "react";
import { render, fireEvent, waitFor } from "@testing-library/react-native";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Home from "../index";
import * as scan from "@/api/scan";

jest.mock("@/api/scan");

let client: QueryClient;

function wrap(ui: React.ReactElement) {
  return <QueryClientProvider client={client}>{ui}</QueryClientProvider>;
}

const verdict = {
  verdict: "haram",
  ingredients: [{ input: "lard", canonical: "lard", status: "haram", source: "rulebook", confidence: "high", reason: "pork fat", citation: "x" }],
  summary: "Contains haram ingredients.",
  disclaimer: "Not a religious ruling.",
};

beforeEach(() => {
  jest.resetAllMocks();
  client = new QueryClient({ defaultOptions: { mutations: { retry: false }, queries: { gcTime: 0 } } });
});

afterEach(() => client.clear());

test("checking ingredients shows the verdict", async () => {
  (scan.classify as jest.Mock).mockResolvedValue(verdict);
  const { getByTestId } = render(wrap(<Home />));
  fireEvent.changeText(getByTestId("ingredients"), "lard\nsugar");
  fireEvent.press(getByTestId("check"));
  await waitFor(() => expect(getByTestId("verdict").props.children).toContain("HARAM"));
  expect(scan.classify).toHaveBeenCalledWith(["lard", "sugar"]);
});

test("empty input does not call the API", () => {
  const { getByTestId } = render(wrap(<Home />));
  fireEvent.press(getByTestId("check"));
  expect(scan.classify).not.toHaveBeenCalled();
});

test("an API error is shown", async () => {
  (scan.classify as jest.Mock).mockRejectedValue(new Error("Server error"));
  const { getByTestId, findByTestId } = render(wrap(<Home />));
  fireEvent.changeText(getByTestId("ingredients"), "lard");
  fireEvent.press(getByTestId("check"));
  expect((await findByTestId("error")).props.children).toContain("Server error");
});
