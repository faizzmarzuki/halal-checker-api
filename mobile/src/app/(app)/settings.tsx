import React from "react";
import { router } from "expo-router";
import { useAuth } from "@/auth/AuthProvider";
import { Screen } from "@/components/ui/Screen";
import { Text } from "@/components/ui/Text";
import { Button } from "@/components/ui/Button";
import { colors } from "@/theme/tokens";

export default function Settings() {
  const { email, signOut } = useAuth();
  return (
    <Screen style={{ justifyContent: "center" }}>
      <Text variant="label" color={colors.muted}>SIGNED IN AS</Text>
      <Text variant="h2">{email ?? "—"}</Text>
      <Button title="Log out" onPress={async () => { await signOut(); router.replace("/(auth)/login"); }} />
    </Screen>
  );
}
