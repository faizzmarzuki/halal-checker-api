import React from "react";
import { render, fireEvent, waitFor } from "@testing-library/react-native";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import HistoryScreen from "../history";
import * as api from "@/api/history";

jest.mock("@/api/history");

let client: QueryClient;
beforeEach(() => {
  jest.resetAllMocks();
  client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  });
});
afterEach(() => client.clear());

function wrap(ui: React.ReactElement) {
  return <QueryClientProvider client={client}>{ui}</QueryClientProvider>;
}

const rows = [
  { id: 1, scan_type: "classify", summary: "sugar, lard", verdict: "haram", created_at: "2026-06-03T11:00:00Z" },
  { id: 2, scan_type: "barcode", summary: "0123456789 (Nutella)", verdict: "halal", created_at: "2026-06-03T10:00:00Z" },
];

test("renders the user's scans", async () => {
  (api.listHistory as jest.Mock).mockResolvedValue(rows);
  const { getByText, getAllByTestId } = render(wrap(<HistoryScreen />));
  await waitFor(() => expect(getAllByTestId("history-row")).toHaveLength(2));
  expect(getByText("sugar, lard")).toBeTruthy();
});

test("deleting a row calls deleteHistory with its id", async () => {
  (api.listHistory as jest.Mock).mockResolvedValue(rows);
  (api.deleteHistory as jest.Mock).mockResolvedValue({});
  const { getByTestId } = render(wrap(<HistoryScreen />));
  await waitFor(() => getByTestId("delete-1"));
  fireEvent.press(getByTestId("delete-1"));
  await waitFor(() => expect(api.deleteHistory).toHaveBeenCalledWith(1));
});

test("an empty list shows a placeholder", async () => {
  (api.listHistory as jest.Mock).mockResolvedValue([]);
  const { getByTestId } = render(wrap(<HistoryScreen />));
  await waitFor(() => expect(getByTestId("empty")).toBeTruthy());
});

test("a load error is shown", async () => {
  (api.listHistory as jest.Mock).mockRejectedValue(new Error("Server error"));
  const { findByTestId } = render(wrap(<HistoryScreen />));
  expect((await findByTestId("error")).props.children).toContain("Server error");
});
