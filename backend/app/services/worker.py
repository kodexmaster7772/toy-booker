import asyncio

from sqlalchemy.engine import Engine

from ..core.config import AppSettings
from ..core.enums import LogLevel, ReservationStatus
from ..core.schemas import BookingRequest
from ..db import repository
from ..db.models import Reservation
from .credentials import CredentialStore
from .event_bus import EventBus
from .korail_adapter import KorailAdapter, UserActionRequired, create_adapter


STATUS_LABELS = {
    ReservationStatus.QUEUED.value: "대기중",
    ReservationStatus.STARTING.value: "브라우저 시작 중",
    ReservationStatus.LOGIN.value: "로그인 중",
    ReservationStatus.SEARCHING.value: "열차 조회 중",
    ReservationStatus.WAITING.value: "좌석 대기 중",
    ReservationStatus.SEAT_FOUND.value: "좌석 발견",
    ReservationStatus.RESERVING.value: "예약 시도 중",
    ReservationStatus.RESERVED.value: "좌석 확보",
    ReservationStatus.USER_ACTION_REQUIRED.value: "사용자 확인 필요",
    ReservationStatus.STOPPED.value: "중지됨",
    ReservationStatus.FAILED.value: "실패",
    "IDLE": "대기중",
}


class BookingWorkerManager:
    def __init__(
        self,
        engine: Engine,
        settings: AppSettings,
        event_bus: EventBus,
        credential_store: CredentialStore,
    ) -> None:
        self.engine = engine
        self.settings = settings
        self.event_bus = event_bus
        self.credential_store = credential_store
        self._task: asyncio.Task[None] | None = None
        self._active_id: str | None = None
        self._adapter: KorailAdapter | None = None
        self._lock = asyncio.Lock()

    @property
    def active_id(self) -> str | None:
        return self._active_id

    async def start(self, request: BookingRequest) -> Reservation:
        async with self._lock:
            if self._task is not None and not self._task.done():
                raise RuntimeError("이미 실행 중인 예약 작업이 있습니다.")
            await self._close_adapter()
            row = repository.create_reservation(self.engine, request)
            self._active_id = row.id
            self._task = asyncio.create_task(self._run(row.id, request), name=f"booking-{row.id}")
            return row

    async def stop(self, reservation_id: str | None = None) -> bool:
        async with self._lock:
            target_id = reservation_id or self._active_id
            if target_id is None:
                return False
            if self._active_id != target_id:
                row = repository.get_reservation(self.engine, target_id)
                return bool(row and row.status == ReservationStatus.STOPPED.value)
            if self._task is not None and not self._task.done():
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
            else:
                row = repository.get_reservation(self.engine, target_id)
                if row and row.status not in {
                    ReservationStatus.RESERVED.value,
                    ReservationStatus.FAILED.value,
                    ReservationStatus.STOPPED.value,
                }:
                    await self._set_status(target_id, ReservationStatus.STOPPED, "사용자가 작업을 중지했습니다.")
            await self._close_adapter()
            self._task = None
            self._active_id = None
            return True

    async def shutdown(self) -> None:
        await self.stop()
        await self._close_adapter()

    def current_status(self) -> dict:
        if self._active_id is None:
            return {"state": "IDLE", "label": STATUS_LABELS["IDLE"], "attemptCount": 0}
        row = repository.get_reservation(self.engine, self._active_id)
        if row is None:
            return {"state": "IDLE", "label": STATUS_LABELS["IDLE"], "attemptCount": 0}
        return {
            "state": row.status,
            "label": STATUS_LABELS.get(row.status, row.status),
            "reservationId": row.id,
            "message": row.message,
            "attemptCount": row.attempt_count,
        }

    async def _log(self, level: LogLevel, message: str, reservation_id: str | None) -> None:
        row = repository.add_log(self.engine, level.value, message, reservation_id)
        self.event_bus.publish(
            "log",
            {
                "id": row.id,
                "timestamp": row.timestamp.isoformat(),
                "level": row.level,
                "message": row.message,
                "reservationId": row.reservation_id,
            },
        )

    async def _set_status(
        self,
        reservation_id: str,
        status: ReservationStatus,
        message: str,
        **values: object,
    ) -> Reservation:
        row = repository.update_reservation(
            self.engine,
            reservation_id,
            status=status.value,
            message=message,
            **values,
        )
        self.event_bus.publish(
            "status",
            {
                "state": row.status,
                "label": STATUS_LABELS.get(row.status, row.status),
                "reservationId": row.id,
                "message": row.message,
                "attemptCount": row.attempt_count,
            },
        )
        return row

    async def _run(self, reservation_id: str, request: BookingRequest) -> None:
        adapter = create_adapter(self.settings)
        self._adapter = adapter
        try:
            await self._set_status(reservation_id, ReservationStatus.STARTING, "브라우저를 시작합니다.")
            await self._log(LogLevel.INFO, "예약 자동화 작업을 시작했습니다.", reservation_id)
            await adapter.start()
            await self._log(LogLevel.INFO, "코레일 전용 Chrome 창을 열었습니다.", reservation_id)

            credentials = self.credential_store.load()
            login_message = (
                "저장된 코레일 계정으로 로그인합니다."
                if credentials is not None
                else "열린 코레일 브라우저에서 5분 안에 직접 로그인하세요."
            )
            await self._set_status(reservation_id, ReservationStatus.LOGIN, login_message)
            await self._log(LogLevel.INFO, "코레일 메인 화면을 거쳐 로그인 화면에 접속합니다.", reservation_id)
            await adapter.login(credentials)
            await self._log(LogLevel.INFO, "로그인 확인이 완료되었습니다.", reservation_id)

            settings = repository.get_settings(self.engine)
            max_attempts = settings.retry_count if request.detect_cancellation else 1
            retry_interval = settings.retry_interval
            if self.settings.automation_mode == "playwright":
                retry_interval = max(20.0, retry_interval)
            for attempt in range(1, max_attempts + 1):
                await self._set_status(
                    reservation_id,
                    ReservationStatus.SEARCHING,
                    f"열차를 조회하고 있습니다. ({attempt}/{max_attempts})",
                    attempt_count=attempt,
                )
                await self._log(
                    LogLevel.INFO if attempt == 1 else LogLevel.WARNING,
                    f"{request.departure} → {request.arrival} 열차 조회 {attempt}회",
                    reservation_id,
                )
                options = await adapter.search(request)
                if options:
                    option = options[0]
                    await self._set_status(
                        reservation_id,
                        ReservationStatus.SEAT_FOUND,
                        f"{option.train_number} 좌석을 발견했습니다.",
                        train_number=option.train_number,
                        departure_time=option.departure_time,
                        arrival_time=option.arrival_time,
                    )
                    await self._log(LogLevel.SUCCESS, f"좌석 발견: {option.train_number}", reservation_id)
                    await self._set_status(
                        reservation_id,
                        ReservationStatus.RESERVING,
                        f"{option.train_number} 예약을 시도합니다.",
                    )
                    result = await adapter.reserve(option)
                    await self._set_status(
                        reservation_id,
                        ReservationStatus.RESERVED,
                        result.message,
                        train_number=result.train_number,
                        seat=result.seat,
                    )
                    await self._log(
                        LogLevel.SUCCESS,
                        f"좌석 확보: {result.train_number} ({request.departure} → {request.arrival})",
                        reservation_id,
                    )
                    if adapter.keep_open_after_reservation:
                        await self._log(
                            LogLevel.WARNING,
                            "결제는 자동화하지 않습니다. 열린 브라우저에서 직접 완료하세요.",
                            reservation_id,
                        )
                    return

                if attempt < max_attempts:
                    await self._set_status(
                        reservation_id,
                        ReservationStatus.WAITING,
                        f"좌석이 없습니다. {retry_interval:g}초 후 다시 조회합니다.",
                    )
                    try:
                        await asyncio.sleep(retry_interval)
                    except asyncio.CancelledError:
                        raise

            await self._set_status(
                reservation_id,
                ReservationStatus.FAILED,
                f"{max_attempts}회 조회했지만 예약 가능한 좌석을 찾지 못했습니다.",
            )
            await self._log(LogLevel.ERROR, "예약 가능한 좌석을 찾지 못했습니다.", reservation_id)
        except asyncio.CancelledError:
            await self._set_status(reservation_id, ReservationStatus.STOPPED, "사용자가 작업을 중지했습니다.")
            await self._log(LogLevel.WARNING, "예약 작업이 중지되었습니다.", reservation_id)
            raise
        except UserActionRequired as exc:
            await self._set_status(reservation_id, ReservationStatus.USER_ACTION_REQUIRED, str(exc))
            await self._log(LogLevel.WARNING, str(exc), reservation_id)
        except Exception as exc:
            message = f"예약 자동화 오류: {exc}"
            await self._set_status(reservation_id, ReservationStatus.FAILED, message)
            await self._log(LogLevel.ERROR, message, reservation_id)
        finally:
            row = repository.get_reservation(self.engine, reservation_id)
            should_keep_open = bool(
                row
                and row.status in {
                    ReservationStatus.RESERVED.value,
                    ReservationStatus.USER_ACTION_REQUIRED.value,
                }
                and adapter.keep_open_after_reservation
            )
            if not should_keep_open:
                await self._close_adapter()

    async def _close_adapter(self) -> None:
        if self._adapter is not None:
            try:
                await self._adapter.close()
            finally:
                self._adapter = None
