import React from "react";
import { View, ViewStyle } from "react-native";
import { colors, radius, space } from "@/theme/tokens";

export function Card({
  children,
  style,
  testID,
}: {
  children: React.ReactNode;
  style?: ViewStyle;
  testID?: string;
}) {
  return (
    <View
      testID={testID}
      style={{
        backgroundColor: colors.surface,
        borderRadius: radius.card,
        padding: space.lg,
        gap: space.sm,
        shadowColor: "#000",
        shadowOpacity: 0.06,
        shadowRadius: 8,
        shadowOffset: { width: 0, height: 2 },
        elevation: 2,
        ...style,
      }}
    >
      {children}
    </View>
  );
}
