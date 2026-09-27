from collections.abc import Sequence

from sqlalchemy import delete, update
from sqlalchemy.engine import Engine
from sqlmodel import Session, col, select

from ..core.enums import ReservationStatus
from ..core.schemas import BookingRequest, SettingsUpdate
from .models import AutomationSettings, LogEntry, Reservation, utc_now


def create_reservation(engine: Engine, request: BookingRequest) -> Reservation:
    row = Reservation(
        departure=request.departure.strip(),
        arrival=request.arrival.strip(),
        travel_date=request.travel_date,
        requested_start_time=request.start_time,
        requested_end_time=request.end_time,
        seat_type=request.seat_type.value,
        include_first_class=request.include_first_class,
        allow_standing=request.allow_standing,
        detect_cancellation=request.detect_cancellation,
    )
    with Session(engine) as session:
        session.add(row)
        session.commit()
        session.refresh(row)
        return row


def get_reservation(engine: Engine, reservation_id: str) -> Reservation | None:
    with Session(engine) as session:
        return session.get(Reservation, reservation_id)


def list_reservations(engine: Engine, limit: int = 100, offset: int = 0) -> Sequence[Reservation]:
    with Session(engine) as session:
        statement = (
            select(Reservation)
            .order_by(col(Reservation.created_at).desc())
            .offset(offset)
            .limit(limit)
        )
        return list(session.exec(statement).all())


def update_reservation(engine: Engine, reservation_id: str, **values: object) -> Reservation:
    values["updated_at"] = utc_now()
    with Session(engine) as session:
        row = session.get(Reservation, reservation_id)
        if row is None:
            raise LookupError(f"예약을 찾을 수 없습니다: {reservation_id}")
        for key, value in values.items():
            setattr(row, key, value)
        session.add(row)
        session.commit()
        session.refresh(row)
        return row


def mark_interrupted_reservations(engine: Engine) -> None:
    terminal = [status.value for status in (
        ReservationStatus.RESERVED,
        ReservationStatus.STOPPED,
        ReservationStatus.FAILED,
    )]
    with Session(engine) as session:
        statement = (
            update(Reservation)
            .where(col(Reservation.status).not_in(terminal))
            .values(
                status=ReservationStatus.STOPPED.value,
                message="백엔드가 재시작되어 작업이 중지되었습니다.",
                updated_at=utc_now(),
            )
        )
        session.exec(statement)
        session.commit()


def get_settings(engine: Engine) -> AutomationSettings:
    with Session(engine) as session:
        row = session.get(AutomationSettings, 1)
        if row is None:
            row = AutomationSettings()
            session.add(row)
            session.commit()
            session.refresh(row)
        return row


def update_settings(engine: Engine, values: SettingsUpdate) -> AutomationSettings:
    with Session(engine) as session:
        row = session.get(AutomationSettings, 1) or AutomationSettings()
        for key, value in values.model_dump().items():
            setattr(row, key, value)
        row.updated_at = utc_now()
        session.add(row)
        session.commit()
        session.refresh(row)
        return row


def add_log(engine: Engine, level: str, message: str, reservation_id: str | None = None) -> LogEntry:
    with Session(engine) as session:
        row = LogEntry(level=level, message=message, reservation_id=reservation_id)
        session.add(row)
        session.commit()
        session.refresh(row)
        return row


def list_logs(
    engine: Engine,
    limit: int = 200,
    offset: int = 0,
    level: str | None = None,
    reservation_id: str | None = None,
) -> Sequence[LogEntry]:
    with Session(engine) as session:
        statement = select(LogEntry)
        if level:
            statement = statement.where(LogEntry.level == level)
        if reservation_id:
            statement = statement.where(LogEntry.reservation_id == reservation_id)
        statement = statement.order_by(col(LogEntry.timestamp).desc()).offset(offset).limit(limit)
        return list(session.exec(statement).all())


def clear_logs(engine: Engine) -> int:
    with Session(engine) as session:
        result = session.exec(delete(LogEntry))
        session.commit()
        return int(result.rowcount or 0)
