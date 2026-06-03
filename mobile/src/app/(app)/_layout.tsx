import React from "react";
import { Redirect, Tabs } from "expo-router";
import { useAuth } from "@/auth/AuthProvider";
import { colors } from "@/theme/tokens";

export default function AppLayout() {
  const { status } = useAuth();
  if (status === "loading") return null;
  if (status === "unauthenticated") return <Redirect href="/(auth)/login" />;
  return (
    <Tabs
      screenOptions={{
        headerShown: true,
        headerStyle: { backgroundColor: colors.bg },
        headerTitleStyle: { fontWeight: "800", color: colors.text },
        headerShadowVisible: false,
        tabBarActiveTintColor: colors.terracotta,
        tabBarInactiveTintColor: colors.muted,
        tabBarStyle: { backgroundColor: colors.bg, borderTopColor: colors.border },
      }}
    >
      <Tabs.Screen name="index" options={{ title: "Home" }} />
      <Tabs.Screen name="history" options={{ title: "History" }} />
      <Tabs.Screen name="settings" options={{ title: "Settings" }} />
      <Tabs.Screen name="barcode" options={{ href: null, title: "Scan barcode" }} />
    </Tabs>
  );
}
