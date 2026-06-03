import React from "react";
import { View, Text, Button } from "react-native";
import { router } from "expo-router";
import { useAuth } from "@/auth/AuthProvider";

export default function Settings() {
  const { email, signOut } = useAuth();
  return (
    <View style={{ flex: 1, padding: 24, gap: 16, justifyContent: "center" }}>
      <Text style={{ fontSize: 16 }}>Signed in as {email ?? "—"}</Text>
      <Button title="Log out" onPress={async () => { await signOut(); router.replace("/(auth)/login"); }} />
    </View>
  );
}
