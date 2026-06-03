import React from "react";
import { render, fireEvent, waitFor } from "@testing-library/react-native";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import PhotoScreen from "../photo";
import * as scan from "@/api/scan";
import * as ImagePicker from "expo-image-picker";

jest.mock("@/api/scan");
jest.mock("expo-image-picker", () => ({
  requestCameraPermissionsAsync: jest.fn(async () => ({ granted: true })),
  launchCameraAsync: jest.fn(async () => ({ canceled: false, assets: [{ uri: "file:///cam.jpg" }] })),
  launchImageLibraryAsync: jest.fn(async () => ({ canceled: false, assets: [{ uri: "file:///lib.jpg" }] })),
}));

let client: QueryClient;
beforeEach(() => {
  jest.clearAllMocks();
  (ImagePicker.requestCameraPermissionsAsync as jest.Mock).mockResolvedValue({ granted: true });
  (ImagePicker.launchCameraAsync as jest.Mock).mockResolvedValue({ canceled: false, assets: [{ uri: "file:///cam.jpg" }] });
  (ImagePicker.launchImageLibraryAsync as jest.Mock).mockResolvedValue({ canceled: false, assets: [{ uri: "file:///lib.jpg" }] });
  client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
});
afterEach(() => client.clear());

function wrap(ui: React.ReactElement) {
  return <QueryClientProvider client={client}>{ui}</QueryClientProvider>;
}

const iv = {
  verdict: "halal",
  ingredients: [{ input: "sugar", canonical: "sugar", status: "halal", source: "rulebook", confidence: "high", reason: "ok", citation: "x" }],
  summary: "All clear.",
  disclaimer: "Not a religious ruling.",
  extracted_text: "sugar, salt",
};

test("taking a photo scans it and shows the verdict", async () => {
  (scan.scanImage as jest.Mock).mockResolvedValue(iv);
  const { getByTestId } = render(wrap(<PhotoScreen />));
  fireEvent.press(getByTestId("take-photo"));
  await waitFor(() => expect(getByTestId("verdict").props.children).toContain("HALAL"));
  expect(scan.scanImage).toHaveBeenCalledWith("file:///cam.jpg");
});

test("choosing from gallery scans the picked image", async () => {
  (scan.scanImage as jest.Mock).mockResolvedValue(iv);
  const { getByTestId } = render(wrap(<PhotoScreen />));
  fireEvent.press(getByTestId("pick-gallery"));
  await waitFor(() => expect(scan.scanImage).toHaveBeenCalledWith("file:///lib.jpg"));
});

test("a cancelled pick does not scan", async () => {
  (ImagePicker.launchImageLibraryAsync as jest.Mock).mockResolvedValue({ canceled: true, assets: null });
  (scan.scanImage as jest.Mock).mockResolvedValue(iv);
  const { getByTestId } = render(wrap(<PhotoScreen />));
  fireEvent.press(getByTestId("pick-gallery"));
  await waitFor(() => expect(ImagePicker.launchImageLibraryAsync).toHaveBeenCalled());
  expect(scan.scanImage).not.toHaveBeenCalled();
});

test("a scan error is shown", async () => {
  (scan.scanImage as jest.Mock).mockRejectedValue(new Error("Could not read any text"));
  const { getByTestId, findByTestId } = render(wrap(<PhotoScreen />));
  fireEvent.press(getByTestId("pick-gallery"));
  expect((await findByTestId("error")).props.children).toContain("Could not read any text");
});
