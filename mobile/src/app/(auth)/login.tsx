import React, { useState } from "react";
import { View, Text, TextInput, Button } from "react-native";
import { Link, router } from "expo-router";
import { useAuth } from "@/auth/AuthProvider";

export default function LoginScreen() {
  const { signIn } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function onSubmit() {
    setError(null);
    try {
      await signIn(email, password);
      router.replace("/(app)");
    } catch (e: any) {
      setError(e?.message ?? "Login failed");
    }
  }

  return (
    <View style={{ flex: 1, padding: 24, justifyContent: "center", gap: 12 }}>
      <Text style={{ fontSize: 24, fontWeight: "600" }}>Log in</Text>
      <TextInput testID="email" placeholder="Email" autoCapitalize="none"
        keyboardType="email-address" value={email} onChangeText={setEmail}
        style={{ borderWidth: 1, borderColor: "#ccc", padding: 10, borderRadius: 6 }} />
      <TextInput testID="password" placeholder="Password" secureTextEntry
        value={password} onChangeText={setPassword}
        style={{ borderWidth: 1, borderColor: "#ccc", padding: 10, borderRadius: 6 }} />
      {error ? <Text style={{ color: "red" }}>{error}</Text> : null}
      <Button testID="submit" title="Log in" onPress={onSubmit} />
      <Link href="/(auth)/register">Need an account? Register</Link>
    </View>
  );
}
