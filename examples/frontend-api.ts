const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export type BookingPayload = {
  departure: string;
  arrival: string;
  date: string;
  startTime: string;
  endTime: string;
  seatType: "GENERAL" | "FIRST";
  includeFirstClass: boolean;
  allowStanding: boolean;
  detectCancellation: boolean;
};

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail ?? "요청에 실패했습니다.");
  }
  return response.json() as Promise<T>;
}

export const ktxApi = {
  startReservation: (payload: BookingPayload) =>
    api("/api/reservations/start", { method: "POST", body: JSON.stringify(payload) }),
  stopReservation: () => api("/api/reservations/stop", { method: "POST" }),
  getStatus: () => api("/api/status"),
  getReservations: () => api("/api/reservations"),
  getSettings: () => api("/api/settings"),
  saveSettings: (payload: unknown) =>
    api("/api/settings", { method: "PUT", body: JSON.stringify(payload) }),
  saveCredentials: (accountId: string, password: string) =>
    api("/api/settings/credentials", {
      method: "PUT",
      body: JSON.stringify({ accountId, password }),
    }),
  getLogs: () => api("/api/logs"),
  clearLogs: () => api("/api/logs", { method: "DELETE" }),
  logExportUrl: `${API_URL}/api/logs/export`,
};

export function connectKtxEvents(onEvent: (event: unknown) => void): () => void {
  const wsUrl = API_URL.replace(/^http/, "ws") + "/api/ws/events";
  const socket = new WebSocket(wsUrl);
  socket.onmessage = (message) => onEvent(JSON.parse(message.data));
  return () => socket.close();
}

