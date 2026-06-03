import React, { useState } from "react";
import { View, Text, TextInput, Button } from "react-native";
import { Link, router } from "expo-router";
import { registerUser } from "@/api/auth";
import { useAuth } from "@/auth/AuthProvider";

export default function RegisterScreen() {
  const { signIn } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function onSubmit() {
    setError(null);
    try {
      await registerUser(email, password);
      await signIn(email, password);
      router.replace("/(app)");
    } catch (e: any) {
      setError(e?.message ?? "Registration failed");
    }
  }

  return (
    <View style={{ flex: 1, padding: 24, justifyContent: "center", gap: 12 }}>
      <Text style={{ fontSize: 24, fontWeight: "600" }}>Create account</Text>
      <TextInput testID="email" placeholder="Email" autoCapitalize="none"
        keyboardType="email-address" value={email} onChangeText={setEmail}
        style={{ borderWidth: 1, borderColor: "#ccc", padding: 10, borderRadius: 6 }} />
      <TextInput testID="password" placeholder="Password" secureTextEntry
        value={password} onChangeText={setPassword}
        style={{ borderWidth: 1, borderColor: "#ccc", padding: 10, borderRadius: 6 }} />
      {error ? <Text style={{ color: "red" }}>{error}</Text> : null}
      <Button testID="submit" title="Register" onPress={onSubmit} />
      <Link href="/(auth)/login">Have an account? Log in</Link>
    </View>
  );
}
