import React, { useState } from "react";
import { View, Image } from "react-native";
import * as ImagePicker from "expo-image-picker";
import { useMutation } from "@tanstack/react-query";
import { scanImage } from "@/api/scan";
import VerdictResult from "@/components/VerdictResult";
import { Screen } from "@/components/ui/Screen";
import { Heading, Text } from "@/components/ui/Text";
import { Button } from "@/components/ui/Button";
import { colors, radius, space } from "@/theme/tokens";

export default function PhotoScreen() {
  const [uri, setUri] = useState<string | null>(null);
  const mutation = useMutation({ mutationFn: (u: string) => scanImage(u) });

  function run(u: string) {
    setUri(u);
    mutation.mutate(u);
  }

  async function takePhoto() {
    const perm = await ImagePicker.requestCameraPermissionsAsync();
    if (!perm.granted) return;
    const res = await ImagePicker.launchCameraAsync({ quality: 0.6 });
    if (!res.canceled && res.assets?.[0]) run(res.assets[0].uri);
  }

  async function pickGallery() {
    const res = await ImagePicker.launchImageLibraryAsync({ quality: 0.6 });
    if (!res.canceled && res.assets?.[0]) run(res.assets[0].uri);
  }

  function reset() {
    setUri(null);
    mutation.reset();
  }

  return (
    <Screen scroll>
      <Heading>Scan photo</Heading>
      <Text variant="small" color={colors.muted}>
        Snap or pick a photo of the ingredient list.
      </Text>

      <Button testID="take-photo" title="Take photo" onPress={takePhoto} />
      <Button testID="pick-gallery" title="Choose from gallery" variant="secondary" onPress={pickGallery} />

      {uri ? (
        <Image
          testID="preview"
          source={{ uri }}
          style={{ height: 200, borderRadius: radius.card, backgroundColor: colors.border }}
          resizeMode="cover"
        />
      ) : null}

      {mutation.isPending ? <Text variant="small" color={colors.muted}>Reading label…</Text> : null}
      {mutation.isError ? (
        <Text testID="error" variant="small" color={colors.haram}>
          {(mutation.error as Error)?.message ?? "Scan failed"}
        </Text>
      ) : null}
      {mutation.data ? (
        <View style={{ gap: space.md }}>
          <VerdictResult result={mutation.data} />
          {mutation.data.extracted_text ? (
            <Text variant="small" color={colors.muted}>Read: {mutation.data.extracted_text}</Text>
          ) : null}
          <Button testID="scan-again" title="Scan another" variant="secondary" onPress={reset} />
        </View>
      ) : null}
    </Screen>
  );
}
