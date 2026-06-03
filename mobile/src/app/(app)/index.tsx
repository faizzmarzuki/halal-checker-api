import React, { useState } from "react";
import { Text, TextInput, Button, ScrollView, ActivityIndicator } from "react-native";
import { useMutation } from "@tanstack/react-query";
import { classify } from "@/api/scan";
import VerdictResult from "@/components/VerdictResult";

function parseIngredients(text: string): string[] {
  return text.split(/[\n,]+/).map((s) => s.trim()).filter(Boolean);
}

export default function Home() {
  const [text, setText] = useState("");
  const mutation = useMutation({ mutationFn: (items: string[]) => classify(items) });

  function onCheck() {
    const parsed = parseIngredients(text);
    if (parsed.length === 0) return;
    mutation.mutate(parsed);
  }

  return (
    <ScrollView contentContainerStyle={{ padding: 20, gap: 12 }}>
      <Text style={{ fontSize: 18, fontWeight: "600" }}>Check ingredients</Text>
      <TextInput
        testID="ingredients"
        multiline
        placeholder="One ingredient per line (or comma-separated)"
        value={text}
        onChangeText={setText}
        style={{ borderWidth: 1, borderColor: "#ccc", borderRadius: 6, padding: 10, minHeight: 100, textAlignVertical: "top" }}
      />
      <Button testID="check" title="Check" onPress={onCheck} />
      {mutation.isPending ? <ActivityIndicator /> : null}
      {mutation.isError ? (
        <Text testID="error" style={{ color: "red" }}>
          {(mutation.error as Error)?.message ?? "Something went wrong"}
        </Text>
      ) : null}
      {mutation.data ? <VerdictResult result={mutation.data} /> : null}
    </ScrollView>
  );
}
