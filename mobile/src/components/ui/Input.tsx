import React from "react";
import { View, TextInput, TextInputProps } from "react-native";
import { Text } from "./Text";
import { colors, space } from "@/theme/tokens";

export function Input({
  label,
  error,
  style,
  ...rest
}: TextInputProps & { label?: string; error?: string }) {
  return (
    <View style={{ gap: space.xs }}>
      {label ? (
        <Text variant="label" color={colors.muted}>
          {label}
        </Text>
      ) : null}
      <TextInput
        placeholderTextColor={colors.muted}
        style={[
          {
            borderBottomWidth: 1,
            borderColor: colors.border,
            paddingVertical: space.sm,
            fontSize: 16,
            color: colors.text,
          },
          style,
        ]}
        {...rest}
      />
      {error ? (
        <Text variant="small" color={colors.haram}>
          {error}
        </Text>
      ) : null}
    </View>
  );
}
