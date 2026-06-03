import React, { useState } from "react";
import { Link, router } from "expo-router";
import { useAuth } from "@/auth/AuthProvider";
import { Screen } from "@/components/ui/Screen";
import { Heading, Text } from "@/components/ui/Text";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { colors } from "@/theme/tokens";

export default function LoginScreen() {
  const { signIn } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit() {
    setError(null);
    setBusy(true);
    try {
      await signIn(email, password);
      router.replace("/(app)");
    } catch (e: any) {
      setError(e?.message ?? "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Screen scroll style={{ justifyContent: "center", flexGrow: 1 }}>
      <Heading>Log in</Heading>
      <Input testID="email" label="Email" placeholder="you@example.com" autoCapitalize="none"
        keyboardType="email-address" value={email} onChangeText={setEmail} />
      <Input testID="password" label="Password" placeholder="••••••••" secureTextEntry
        value={password} onChangeText={setPassword} />
      {error ? <Text variant="small" color={colors.haram}>{error}</Text> : null}
      <Button testID="submit" title="Log in" onPress={onSubmit} loading={busy} />
      <Link href="/(auth)/register" style={{ color: colors.terracotta, textAlign: "center" }}>
        Need an account? Register
      </Link>
    </Screen>
  );
}
