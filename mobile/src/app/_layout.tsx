import { Stack } from "expo-router";

// Minimal root layout for the foundation scaffold. SP17 Task 6 replaces this with
// the provider stack (QueryClient + AuthProvider) and the real route tree.
export default function RootLayout() {
  return <Stack screenOptions={{ headerShown: false }} />;
}
