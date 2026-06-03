import React, { useState } from "react";
import { View } from "react-native";
import { CameraView, useCameraPermissions } from "expo-camera";
import { useMutation } from "@tanstack/react-query";
import { scanBarcode } from "@/api/scan";
import VerdictResult from "@/components/VerdictResult";
import { Screen } from "@/components/ui/Screen";
import { Heading, Text } from "@/components/ui/Text";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { colors, radius, space } from "@/theme/tokens";

export default function BarcodeScreen() {
  const [permission, requestPermission] = useCameraPermissions();
  const [manual, setManual] = useState("");
  const [scanned, setScanned] = useState(false);
  const mutation = useMutation({ mutationFn: (code: string) => scanBarcode(code) });

  function lookup(code: string) {
    if (!code) return;
    setScanned(true);
    mutation.mutate(code);
  }

  function reset() {
    setScanned(false);
    mutation.reset();
  }

  return (
    <Screen scroll>
      <Heading>Scan barcode</Heading>

      {permission?.granted ? (
        <View style={{ height: 240, borderRadius: radius.card, overflow: "hidden", backgroundColor: "#000" }}>
          <CameraView
            style={{ flex: 1 }}
            autofocus="on"
            barcodeScannerSettings={{ barcodeTypes: ["ean13", "ean8", "upc_a", "upc_e"] }}
            onBarcodeScanned={scanned ? undefined : ({ data }: { data: string }) => lookup(data)}
          />
        </View>
      ) : (
        <Button testID="allow-camera" title="Allow camera" variant="secondary" onPress={() => requestPermission()} />
      )}

      <Text variant="label" color={colors.muted}>OR ENTER MANUALLY</Text>
      <Input testID="barcode" label="Barcode" placeholder="e.g. 0123456789" keyboardType="number-pad"
        value={manual} onChangeText={setManual} />
      <Button testID="lookup" title="Look up" onPress={() => lookup(manual)} loading={mutation.isPending} />

      {mutation.isError ? (
        <Text testID="error" variant="small" color={colors.haram}>{(mutation.error as Error)?.message ?? "Lookup failed"}</Text>
      ) : null}
      {mutation.data ? (
        <View style={{ gap: space.md }}>
          <Text variant="h2">{mutation.data.product_name || mutation.data.barcode}</Text>
          <VerdictResult result={mutation.data} />
          <Button testID="scan-again" title="Scan again" variant="secondary" onPress={reset} />
        </View>
      ) : null}
    </Screen>
  );
}
