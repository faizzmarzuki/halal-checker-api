import React from "react";
import { render, fireEvent, waitFor } from "@testing-library/react-native";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import BarcodeScreen from "../barcode";
import * as scan from "@/api/scan";
import { useCameraPermissions } from "expo-camera";

jest.mock("@/api/scan");
jest.mock("expo-camera", () => ({
  CameraView: () => null,
  useCameraPermissions: jest.fn(() => [{ granted: true }, jest.fn()]),
}));

let client: QueryClient;
beforeEach(() => {
  jest.clearAllMocks();
  (useCameraPermissions as jest.Mock).mockReturnValue([{ granted: true }, jest.fn()]);
  client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
});
afterEach(() => client.clear());

function wrap(ui: React.ReactElement) {
  return <QueryClientProvider client={client}>{ui}</QueryClientProvider>;
}

const bv = {
  verdict: "haram",
  ingredients: [{ input: "lard", canonical: "lard", status: "haram", source: "rulebook", confidence: "high", reason: "pork fat", citation: "x" }],
  summary: "Contains haram ingredients.",
  disclaimer: "Not a religious ruling.",
  barcode: "0123456789",
  product_name: "Nutella",
};

test("manual look up shows the verdict", async () => {
  (scan.scanBarcode as jest.Mock).mockResolvedValue(bv);
  const { getByTestId } = render(wrap(<BarcodeScreen />));
  fireEvent.changeText(getByTestId("barcode"), "0123456789");
  fireEvent.press(getByTestId("lookup"));
  await waitFor(() => expect(getByTestId("verdict").props.children).toContain("HARAM"));
  expect(scan.scanBarcode).toHaveBeenCalledWith("0123456789");
});

test("a lookup error is shown", async () => {
  (scan.scanBarcode as jest.Mock).mockRejectedValue(new Error("Product not found"));
  const { getByTestId, findByTestId } = render(wrap(<BarcodeScreen />));
  fireEvent.changeText(getByTestId("barcode"), "0000000000");
  fireEvent.press(getByTestId("lookup"));
  expect((await findByTestId("error")).props.children).toContain("Product not found");
});

test("shows Allow camera when permission is undetermined", () => {
  (useCameraPermissions as jest.Mock).mockReturnValue([{ granted: false, status: "undetermined" }, jest.fn()]);
  const { getByTestId } = render(wrap(<BarcodeScreen />));
  expect(getByTestId("allow-camera")).toBeTruthy();
});
