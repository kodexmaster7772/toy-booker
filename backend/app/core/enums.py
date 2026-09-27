from enum import StrEnum


class ReservationStatus(StrEnum):
    QUEUED = "QUEUED"
    STARTING = "STARTING"
    LOGIN = "LOGIN"
    SEARCHING = "SEARCHING"
    WAITING = "WAITING"
    SEAT_FOUND = "SEAT_FOUND"
    RESERVING = "RESERVING"
    RESERVED = "RESERVED"
    USER_ACTION_REQUIRED = "USER_ACTION_REQUIRED"
    STOPPED = "STOPPED"
    FAILED = "FAILED"


class LogLevel(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    SUCCESS = "SUCCESS"


class SeatType(StrEnum):
    GENERAL = "GENERAL"
    FIRST = "FIRST"


TERMINAL_STATUSES = {
    ReservationStatus.RESERVED,
    ReservationStatus.STOPPED,
    ReservationStatus.FAILED,
}

