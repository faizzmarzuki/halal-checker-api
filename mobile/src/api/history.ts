import { request } from "./client";

export type ScanHistoryOut = {
  id: number;
  scan_type: string; // classify | barcode | image
  summary: string;
  verdict: string; // halal | haram | shubhah
  created_at: string; // ISO timestamp
};

export function listHistory(limit = 50, offset = 0): Promise<ScanHistoryOut[]> {
  return request<ScanHistoryOut[]>(`/history?limit=${limit}&offset=${offset}`, { auth: "bearer" });
}

export function deleteHistory(id: number): Promise<unknown> {
  return request(`/history/${id}`, { method: "DELETE", auth: "bearer" });
}

export function clearHistory(): Promise<unknown> {
  return request("/history", { method: "DELETE", auth: "bearer" });
}
