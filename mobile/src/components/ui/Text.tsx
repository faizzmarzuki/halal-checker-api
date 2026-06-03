import React from "react";
import { Text as RNText, TextProps } from "react-native";
import { colors, type as typeTokens } from "@/theme/tokens";

type Variant = keyof typeof typeTokens;

export function Text({
  variant = "body",
  color,
  caps,
  style,
  children,
  ...rest
}: TextProps & { variant?: Variant; color?: string; caps?: boolean }) {
  const content = caps && typeof children === "string" ? children.toUpperCase() : children;
  return (
    <RNText style={[typeTokens[variant], { color: color ?? colors.text }, style]} {...rest}>
      {content}
    </RNText>
  );
}

export function Heading(props: TextProps & { variant?: Variant; color?: string }) {
  return <Text variant="display" caps {...props} />;
}
