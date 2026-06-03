import React, { useState } from "react";
import { ActivityIndicator } from "react-native";
import { router } from "expo-router";
import { useMutation } from "@tanstack/react-query";
import { classify } from "@/api/scan";
import VerdictResult from "@/components/VerdictResult";
import { Screen } from "@/components/ui/Screen";
import { Heading, Text } from "@/components/ui/Text";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { colors } from "@/theme/tokens";

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
    <Screen scroll>
      <Heading>Check ingredients</Heading>
      <Input
        testID="ingredients"
        label="Ingredients"
        placeholder="One per line, or comma-separated"
        multiline
        value={text}
        onChangeText={setText}
        style={{ minHeight: 110, textAlignVertical: "top", borderBottomWidth: 0 }}
      />
      <Button testID="check" title="Check" onPress={onCheck} loading={mutation.isPending} />
      <Button testID="go-barcode" title="Scan barcode" variant="secondary" onPress={() => router.push("/barcode")} />
      <Button testID="go-photo" title="Scan photo" variant="secondary" onPress={() => router.push("/photo")} />
      {mutation.isPending ? <ActivityIndicator /> : null}
      {mutation.isError ? (
        <Text testID="error" variant="small" color={colors.haram}>
          {(mutation.error as Error)?.message ?? "Something went wrong"}
        </Text>
      ) : null}
      {mutation.data ? <VerdictResult result={mutation.data} /> : null}
    </Screen>
  );
}
