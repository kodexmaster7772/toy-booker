from datetime import date, datetime, time
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .enums import LogLevel, ReservationStatus, SeatType


def to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(word.capitalize() for word in rest)


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class BookingRequest(ApiModel):
    departure: str = Field(min_length=1, max_length=30)
    arrival: str = Field(min_length=1, max_length=30)
    travel_date: date = Field(alias="date")
    start_time: time
    end_time: time
    seat_type: SeatType = SeatType.GENERAL
    include_first_class: bool = False
    allow_standing: bool = False
    detect_cancellation: bool = True

    @model_validator(mode="after")
    def validate_route_and_time(self) -> "BookingRequest":
        if self.departure.strip() == self.arrival.strip():
            raise ValueError("출발역과 도착역은 달라야 합니다.")
        if self.start_time >= self.end_time:
            raise ValueError("시작 시간은 종료 시간보다 빨라야 합니다.")
        return self


class ReservationRead(ApiModel):
    id: str
    train_number: str | None
    departure: str
    arrival: str
    travel_date: date
    departure_time: time | None
    arrival_time: time | None
    seat_type: str
    seat: str | None
    status: ReservationStatus
    message: str | None
    attempt_count: int
    created_at: datetime
    updated_at: datetime


class StartReservationResponse(ApiModel):
    success: bool = True
    reservation: ReservationRead


class StatusResponse(ApiModel):
    state: ReservationStatus | str
    label: str
    reservation_id: str | None = None
    message: str | None = None
    attempt_count: int = 0


class StopResponse(ApiModel):
    success: bool
    reservation_id: str | None = None
    message: str


class SettingsUpdate(ApiModel):
    auto_payment: bool = False
    cancellation_detection: bool = True
    retry_count: int = Field(default=10, ge=1, le=1000)
    retry_interval: float = Field(default=20.0, ge=1.0, le=300.0)
    browser_notification: bool = True
    sound_notification: bool = True
    email_notification: bool = False


class SettingsRead(SettingsUpdate):
    credentials_configured: bool = False
    automation_mode: str


class CredentialsInput(ApiModel):
    account_id: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class CredentialsStatus(ApiModel):
    configured: bool
    account_hint: str | None = None


class LogRead(ApiModel):
    id: int
    timestamp: datetime
    level: LogLevel
    message: str
    reservation_id: str | None


class EventMessage(ApiModel):
    type: str
    timestamp: datetime
    data: dict[str, Any]
