import React from "react";
import { View, Text, Button, FlatList, ActivityIndicator, RefreshControl } from "react-native";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listHistory, deleteHistory, clearHistory, type ScanHistoryOut } from "@/api/history";
import { timeAgo } from "@/lib/time";

const COLOR: Record<string, string> = { halal: "#1a7f37", haram: "#cf222e", shubhah: "#9a6700" };

function Row({ item, onDelete }: { item: ScanHistoryOut; onDelete: (id: number) => void }) {
  return (
    <View testID="history-row" style={{ borderBottomWidth: 1, borderColor: "#eee", paddingVertical: 10, gap: 4 }}>
      <Text style={{ fontWeight: "700", color: COLOR[item.verdict] ?? "#333" }}>{item.verdict.toUpperCase()}</Text>
      <Text numberOfLines={2}>{item.summary}</Text>
      <Text style={{ color: "#777", fontSize: 12 }}>{item.scan_type} · {timeAgo(item.created_at)}</Text>
      <Button testID={`delete-${item.id}`} title="Delete" onPress={() => onDelete(item.id)} />
    </View>
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
    return <View style={{ flex: 1, alignItems: "center", justifyContent: "center" }}><ActivityIndicator /></View>;
  }
  if (query.isError) {
    return (
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center", padding: 24, gap: 12 }}>
        <Text testID="error" style={{ color: "red" }}>{(query.error as Error)?.message ?? "Failed to load history"}</Text>
        <Button testID="retry" title="Retry" onPress={() => query.refetch()} />
      </View>
    );
  }

  const data = query.data ?? [];
  return (
    <FlatList
      testID="history-list"
      data={data}
      keyExtractor={(it) => String(it.id)}
      contentContainerStyle={{ padding: 16 }}
      refreshControl={<RefreshControl refreshing={query.isFetching} onRefresh={() => query.refetch()} />}
      ListHeaderComponent={data.length ? <Button testID="clear-all" title="Clear all" onPress={() => clear.mutate()} /> : null}
      ListEmptyComponent={<Text testID="empty" style={{ textAlign: "center", marginTop: 40, color: "#777" }}>No scans yet</Text>}
      renderItem={({ item }) => <Row item={item} onDelete={del.mutate} />}
    />
  );
}
