export type PageKey = "booking" | "reservations" | "settings" | "logs";

export type ReservationStatus =
  | "QUEUED"
  | "STARTING"
  | "LOGIN"
  | "SEARCHING"
  | "WAITING"
  | "SEAT_FOUND"
  | "RESERVING"
  | "RESERVED"
  | "USER_ACTION_REQUIRED"
  | "STOPPED"
  | "FAILED";

export interface BookingPayload {
  departure: string;
  arrival: string;
  date: string;
  startTime: string;
  endTime: string;
  seatType: "GENERAL" | "FIRST";
  includeFirstClass: boolean;
  allowStanding: boolean;
  detectCancellation: boolean;
}

export interface Reservation {
  id: string;
  trainNumber: string | null;
  departure: string;
  arrival: string;
  travelDate: string;
  departureTime: string | null;
  arrivalTime: string | null;
  seatType: string;
  seat: string | null;
  status: ReservationStatus;
  message: string | null;
  attemptCount: number;
  createdAt: string;
  updatedAt: string;
}

export interface StatusResponse {
  state: ReservationStatus | "IDLE";
  label: string;
  reservationId?: string | null;
  message?: string | null;
  attemptCount: number;
}

export interface AppSettings {
  autoPayment: boolean;
  cancellationDetection: boolean;
  retryCount: number;
  retryInterval: number;
  browserNotification: boolean;
  soundNotification: boolean;
  emailNotification: boolean;
  credentialsConfigured: boolean;
  automationMode: "mock" | "playwright";
}

export interface LogEntry {
  id: number;
  timestamp: string;
  level: "INFO" | "WARNING" | "ERROR" | "SUCCESS";
  message: string;
  reservationId: string | null;
}

export interface ApiEvent {
  type: "status" | "log" | "logsCleared" | "ping";
  timestamp?: string;
  data?: Record<string, unknown>;
}

