import React from "react";
import { Pressable, ActivityIndicator, ViewStyle } from "react-native";
import { Text } from "./Text";
import { colors, radius, space } from "@/theme/tokens";

type Variant = "primary" | "secondary" | "accent";

const BG: Record<Variant, string> = {
  primary: colors.text,
  secondary: "transparent",
  accent: colors.terracotta,
};
const FG: Record<Variant, string> = {
  primary: colors.onDark,
  secondary: colors.text,
  accent: colors.onDark,
};

export function Button({
  title,
  onPress,
  variant = "primary",
  loading,
  testID,
  style,
}: {
  title: string;
  onPress: () => void;
  variant?: Variant;
  loading?: boolean;
  testID?: string;
  style?: ViewStyle;
}) {
  return (
    <Pressable
      testID={testID}
      onPress={loading ? undefined : onPress}
      disabled={loading}
      style={({ pressed }) => ({
        backgroundColor: BG[variant],
        borderRadius: radius.pill,
        borderWidth: variant === "secondary" ? 1 : 0,
        borderColor: colors.border,
        paddingVertical: space.md + 2,
        paddingHorizontal: space.xl,
        alignItems: "center",
        opacity: pressed || loading ? 0.7 : 1,
        ...style,
      })}
    >
      {loading ? (
        <ActivityIndicator color={FG[variant]} />
      ) : (
        <Text variant="h2" color={FG[variant]}>
          {title}
        </Text>
      )}
    </Pressable>
  );
}
