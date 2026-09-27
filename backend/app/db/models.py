from datetime import date, datetime, time, timezone
from uuid import uuid4

from sqlmodel import Field, SQLModel

from ..core.enums import LogLevel, ReservationStatus, SeatType


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Reservation(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    train_number: str | None = Field(default=None, index=True)
    departure: str = Field(index=True)
    arrival: str = Field(index=True)
    travel_date: date = Field(index=True)
    requested_start_time: time
    requested_end_time: time
    departure_time: time | None = None
    arrival_time: time | None = None
    seat_type: str = Field(default=SeatType.GENERAL.value)
    include_first_class: bool = False
    allow_standing: bool = False
    detect_cancellation: bool = True
    seat: str | None = None
    status: str = Field(default=ReservationStatus.QUEUED.value, index=True)
    message: str | None = None
    attempt_count: int = 0
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now)


class AutomationSettings(SQLModel, table=True):
    id: int = Field(default=1, primary_key=True)
    auto_payment: bool = False
    cancellation_detection: bool = True
    retry_count: int = 10
    retry_interval: float = 20.0
    browser_notification: bool = True
    sound_notification: bool = True
    email_notification: bool = False
    updated_at: datetime = Field(default_factory=utc_now)


class LogEntry(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    timestamp: datetime = Field(default_factory=utc_now, index=True)
    level: str = Field(default=LogLevel.INFO.value, index=True)
    message: str
    reservation_id: str | None = Field(default=None, foreign_key="reservation.id", index=True)
