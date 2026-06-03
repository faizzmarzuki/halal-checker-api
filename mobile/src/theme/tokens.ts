import type { TextStyle } from "react-native";

export const colors = {
  bg: "#F3F1E9",
  surface: "#FFFFFF",
  text: "#1A1A1A",
  muted: "#6B6B6B",
  border: "#E5E1D6",
  green: "#2E7D32",
  terracotta: "#E07A3E",
  halal: "#1F7A33",
  haram: "#C0362C",
  shubhah: "#B5852A",
  onDark: "#FFFFFF",
} as const;

export const space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 } as const;

export const radius = { card: 18, pill: 999, input: 0 } as const;

export const type: Record<string, TextStyle> = {
  display: { fontSize: 34, fontWeight: "800", letterSpacing: 0.5 },
  h1: { fontSize: 26, fontWeight: "800" },
  h2: { fontSize: 20, fontWeight: "700" },
  body: { fontSize: 16, fontWeight: "400" },
  small: { fontSize: 13, fontWeight: "400" },
  label: { fontSize: 12, fontWeight: "600", letterSpacing: 0.5 },
};

export function verdictColor(v: string): string {
  return (
    { halal: colors.halal, haram: colors.haram, shubhah: colors.shubhah } as Record<string, string>
  )[v] ?? colors.text;
}
