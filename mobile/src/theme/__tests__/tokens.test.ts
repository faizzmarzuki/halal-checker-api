import { verdictColor, colors } from "../tokens";

test("verdictColor maps each verdict and falls back", () => {
  expect(verdictColor("halal")).toBe(colors.halal);
  expect(verdictColor("haram")).toBe(colors.haram);
  expect(verdictColor("shubhah")).toBe(colors.shubhah);
  expect(verdictColor("???")).toBe(colors.text);
});
