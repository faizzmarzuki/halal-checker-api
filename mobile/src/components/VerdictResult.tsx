import React from "react";
import { View } from "react-native";
import type { VerdictOut } from "@/api/scan";
import { Card } from "@/components/ui/Card";
import { Text } from "@/components/ui/Text";
import { colors, space, verdictColor } from "@/theme/tokens";

export default function VerdictResult({ result }: { result: VerdictOut }) {
  return (
    <View style={{ gap: space.md }}>
      <Card style={{ borderLeftWidth: 6, borderLeftColor: verdictColor(result.verdict) }}>
        <Text testID="verdict" variant="h1" color={verdictColor(result.verdict)} caps>
          {result.verdict}
        </Text>
        <Text variant="body">{result.summary}</Text>
      </Card>
      <View style={{ gap: space.sm }}>
        {result.ingredients.map((ing, i) => (
          <Card key={i} testID="ingredient">
            <Text variant="h2">
              {ing.input} — <Text variant="h2" color={verdictColor(ing.status)}>{ing.status}</Text>
            </Text>
            <Text variant="small" color={colors.muted}>{ing.reason}</Text>
          </Card>
        ))}
      </View>
      <Text testID="disclaimer" variant="small" color={colors.muted}>{result.disclaimer}</Text>
    </View>
  );
}
