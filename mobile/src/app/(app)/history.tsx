import React from "react";
import { View, FlatList, ActivityIndicator, RefreshControl } from "react-native";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listHistory, deleteHistory, clearHistory, type ScanHistoryOut } from "@/api/history";
import { timeAgo } from "@/lib/time";
import { Card } from "@/components/ui/Card";
import { Text } from "@/components/ui/Text";
import { Button } from "@/components/ui/Button";
import { colors, space, verdictColor } from "@/theme/tokens";

function Row({ item, onDelete }: { item: ScanHistoryOut; onDelete: (id: number) => void }) {
  return (
    <Card testID="history-row" style={{ marginBottom: space.md }}>
      <Text variant="h2" color={verdictColor(item.verdict)} caps>{item.verdict}</Text>
      <Text variant="body" numberOfLines={2}>{item.summary}</Text>
      <Text variant="small" color={colors.muted}>{item.scan_type} · {timeAgo(item.created_at)}</Text>
      <Button testID={`delete-${item.id}`} title="Delete" variant="secondary" onPress={() => onDelete(item.id)} />
    </Card>
  );
}

export default function HistoryScreen() {
  const qc = useQueryClient();
  const query = useQuery({ queryKey: ["history"], queryFn: () => listHistory() });
  const del = useMutation({
    mutationFn: (id: number) => deleteHistory(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["history"] }),
  });
  const clear = useMutation({
    mutationFn: () => clearHistory(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["history"] }),
  });

  if (query.isLoading) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg, alignItems: "center", justifyContent: "center" }}>
        <ActivityIndicator />
      </View>
    );
  }
  if (query.isError) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg, alignItems: "center", justifyContent: "center", padding: space.xl, gap: space.md }}>
        <Text testID="error" variant="body" color={colors.haram}>{(query.error as Error)?.message ?? "Failed to load history"}</Text>
        <Button testID="retry" title="Retry" onPress={() => query.refetch()} />
      </View>
    );
  }

  const data = query.data ?? [];
  return (
    <FlatList
      testID="history-list"
      style={{ backgroundColor: colors.bg }}
      data={data}
      keyExtractor={(it) => String(it.id)}
      contentContainerStyle={{ padding: space.lg }}
      refreshControl={<RefreshControl refreshing={query.isFetching} onRefresh={() => query.refetch()} />}
      ListHeaderComponent={
        data.length ? (
          <View style={{ marginBottom: space.md }}>
            <Button testID="clear-all" title="Clear all" variant="secondary" onPress={() => clear.mutate()} />
          </View>
        ) : null
      }
      ListEmptyComponent={
        <Text testID="empty" variant="body" color={colors.muted} style={{ textAlign: "center", marginTop: 48 }}>
          No scans yet
        </Text>
      }
      renderItem={({ item }) => <Row item={item} onDelete={del.mutate} />}
    />
  );
}
