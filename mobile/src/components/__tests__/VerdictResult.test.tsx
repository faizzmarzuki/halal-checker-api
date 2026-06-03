import React from "react";
import { render } from "@testing-library/react-native";
import VerdictResult from "../VerdictResult";
import type { VerdictOut } from "@/api/scan";

const sample: VerdictOut = {
  verdict: "haram",
  ingredients: [
    { input: "lard", canonical: "lard", status: "haram", source: "rulebook", confidence: "high", reason: "pork fat", citation: "x" },
    { input: "sugar", canonical: "sugar", status: "halal", source: "rulebook", confidence: "high", reason: "permitted", citation: "y" },
  ],
  summary: "Contains haram ingredients.",
  disclaimer: "Not a religious ruling.",
};

test("renders the verdict, ingredients, and disclaimer", () => {
  const { getByTestId, getAllByTestId, getByText } = render(<VerdictResult result={sample} />);
  expect(getByTestId("verdict").props.children).toContain("HARAM");
  expect(getAllByTestId("ingredient")).toHaveLength(2);
  expect(getByText("pork fat")).toBeTruthy();
  expect(getByTestId("disclaimer").props.children).toContain("Not a religious ruling.");
});
