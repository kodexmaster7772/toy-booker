import type {
  ApiEvent,
  AppSettings,
  BookingPayload,
  LogEntry,
  Reservation,
  StatusResponse,
} from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }));
    const detail = typeof payload.detail === "string" ? payload.detail : "요청을 처리하지 못했습니다.";
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<{ ok: boolean; automationMode: string }>("/api/health"),
  startReservation: (payload: BookingPayload) =>
    request<{ success: boolean; reservation: Reservation }>("/api/reservations/start", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  stopReservation: () =>
    request<{ success: boolean; message: string }>("/api/reservations/stop", { method: "POST" }),
  getStatus: () => request<StatusResponse>("/api/status"),
  getReservations: () => request<Reservation[]>("/api/reservations"),
  getSettings: () => request<AppSettings>("/api/settings"),
  saveSettings: (payload: Omit<AppSettings, "credentialsConfigured" | "automationMode">) =>
    request<AppSettings>("/api/settings", { method: "PUT", body: JSON.stringify(payload) }),
  saveCredentials: (accountId: string, password: string) =>
    request<{ configured: boolean; accountHint: string | null }>("/api/settings/credentials", {
      method: "PUT",
      body: JSON.stringify({ accountId, password }),
    }),
  getLogs: () => request<LogEntry[]>("/api/logs?limit=500"),
  clearLogs: () => request<{ success: boolean; deleted: number }>("/api/logs", { method: "DELETE" }),
};

export function connectEvents(onEvent: (event: ApiEvent) => void): () => void {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  let socket: WebSocket | null = null;
  let reconnectTimer: number | null = null;
  let stopped = false;

  const connect = () => {
    if (stopped) return;
    socket = new WebSocket(`${protocol}//${window.location.host}/api/ws/events`);
    socket.onmessage = (message) => {
      try {
        onEvent(JSON.parse(message.data) as ApiEvent);
      } catch {
        // 서버의 비정상 메시지는 다음 정상 이벤트까지 무시합니다.
      }
    };
    socket.onclose = () => {
      if (!stopped) reconnectTimer = window.setTimeout(connect, 2000);
    };
  };

  connect();
  return () => {
    stopped = true;
    if (reconnectTimer !== null) window.clearTimeout(reconnectTimer);
    socket?.close();
  };
}
