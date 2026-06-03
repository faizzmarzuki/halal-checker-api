import React from "react";
import { View, ScrollView, ViewStyle } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { colors, space } from "@/theme/tokens";

export function Screen({
  children,
  scroll,
  style,
}: {
  children: React.ReactNode;
  scroll?: boolean;
  style?: ViewStyle;
}) {
  const inner = { padding: space.xl, gap: space.lg, ...style } as ViewStyle;
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }}>
      {scroll ? (
        <ScrollView contentContainerStyle={inner} keyboardShouldPersistTaps="handled">
          {children}
        </ScrollView>
      ) : (
        <View style={{ flex: 1, ...inner }}>{children}</View>
      )}
    </SafeAreaView>
  );
}
