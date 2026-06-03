import React from "react";
import { View, Text } from "react-native";
import type { VerdictOut } from "@/api/scan";

const COLOR: Record<string, string> = {
  halal: "#1a7f37",
  haram: "#cf222e",
  shubhah: "#9a6700",
};

export default function VerdictResult({ result }: { result: VerdictOut }) {
  return (
    <View style={{ gap: 12 }}>
      <Text testID="verdict" style={{ fontSize: 22, fontWeight: "700", color: COLOR[result.verdict] ?? "#333" }}>
        {result.verdict.toUpperCase()}
      </Text>
      <Text>{result.summary}</Text>
      <View style={{ gap: 8 }}>
        {result.ingredients.map((ing, i) => (
          <View key={i} testID="ingredient" style={{ borderTopWidth: 1, borderColor: "#eee", paddingTop: 6 }}>
            <Text style={{ fontWeight: "600" }}>
              {ing.input} — <Text style={{ color: COLOR[ing.status] ?? "#333" }}>{ing.status}</Text>
            </Text>
            <Text style={{ color: "#555" }}>{ing.reason}</Text>
          </View>
        ))}
      </View>
      <Text testID="disclaimer" style={{ fontSize: 12, color: "#777" }}>{result.disclaimer}</Text>
    </View>
  );
}
