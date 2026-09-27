import asyncio
import csv
import io

from fastapi import APIRouter, HTTPException, Query, Request, WebSocket, WebSocketDisconnect, status
from fastapi.responses import StreamingResponse

from ..core.enums import LogLevel, ReservationStatus
from ..core.schemas import (
    BookingRequest,
    CredentialsInput,
    CredentialsStatus,
    LogRead,
    ReservationRead,
    SettingsRead,
    SettingsUpdate,
    StartReservationResponse,
    StatusResponse,
    StopResponse,
)
from ..db import repository


router = APIRouter(prefix="/api")


def _reservation_read(row) -> ReservationRead:
    return ReservationRead(
        id=row.id,
        train_number=row.train_number,
        departure=row.departure,
        arrival=row.arrival,
        travel_date=row.travel_date,
        departure_time=row.departure_time,
        arrival_time=row.arrival_time,
        seat_type=row.seat_type,
        seat=row.seat,
        status=ReservationStatus(row.status),
        message=row.message,
        attempt_count=row.attempt_count,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("/health")
async def health(request: Request) -> dict:
    return {
        "ok": True,
        "version": request.app.state.settings.app_version,
        "automationMode": request.app.state.settings.automation_mode,
    }


@router.post(
    "/reservations/start",
    response_model=StartReservationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_reservation(payload: BookingRequest, request: Request) -> StartReservationResponse:
    try:
        row = await request.app.state.worker.start(payload)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return StartReservationResponse(reservation=_reservation_read(row))


@router.post("/reservations/stop", response_model=StopResponse)
async def stop_current_reservation(request: Request) -> StopResponse:
    reservation_id = request.app.state.worker.active_id
    stopped = await request.app.state.worker.stop()
    return StopResponse(
        success=stopped,
        reservation_id=reservation_id,
        message="예약 작업을 중지했습니다." if stopped else "실행 중인 예약 작업이 없습니다.",
    )


@router.post("/reservations/{reservation_id}/stop", response_model=StopResponse)
async def stop_reservation(reservation_id: str, request: Request) -> StopResponse:
    if repository.get_reservation(request.app.state.engine, reservation_id) is None:
        raise HTTPException(status_code=404, detail="예약을 찾을 수 없습니다.")
    stopped = await request.app.state.worker.stop(reservation_id)
    return StopResponse(
        success=stopped,
        reservation_id=reservation_id,
        message="예약 작업을 중지했습니다." if stopped else "이미 종료된 예약입니다.",
    )


@router.get("/reservations", response_model=list[ReservationRead])
async def reservations(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[ReservationRead]:
    rows = repository.list_reservations(request.app.state.engine, limit=limit, offset=offset)
    return [_reservation_read(row) for row in rows]


@router.get("/reservations/{reservation_id}", response_model=ReservationRead)
async def reservation_detail(reservation_id: str, request: Request) -> ReservationRead:
    row = repository.get_reservation(request.app.state.engine, reservation_id)
    if row is None:
        raise HTTPException(status_code=404, detail="예약을 찾을 수 없습니다.")
    return _reservation_read(row)


@router.get("/status", response_model=StatusResponse)
async def current_status(request: Request) -> StatusResponse:
    return StatusResponse.model_validate(request.app.state.worker.current_status())


def _settings_read(request: Request, row) -> SettingsRead:
    store = request.app.state.credential_store
    return SettingsRead(
        auto_payment=row.auto_payment,
        cancellation_detection=row.cancellation_detection,
        retry_count=row.retry_count,
        retry_interval=row.retry_interval,
        browser_notification=row.browser_notification,
        sound_notification=row.sound_notification,
        email_notification=row.email_notification,
        credentials_configured=store.load() is not None,
        automation_mode=request.app.state.settings.automation_mode,
    )


@router.get("/settings", response_model=SettingsRead)
async def get_settings(request: Request) -> SettingsRead:
    row = repository.get_settings(request.app.state.engine)
    return _settings_read(request, row)


@router.put("/settings", response_model=SettingsRead)
async def put_settings(payload: SettingsUpdate, request: Request) -> SettingsRead:
    if payload.auto_payment:
        raise HTTPException(
            status_code=422,
            detail="자동 결제는 지원하지 않습니다. 좌석 확보 후 열린 브라우저에서 직접 결제하세요.",
        )
    row = repository.update_settings(request.app.state.engine, payload)
    return _settings_read(request, row)


@router.get("/settings/credentials", response_model=CredentialsStatus)
async def credentials_status(request: Request) -> CredentialsStatus:
    store = request.app.state.credential_store
    return CredentialsStatus(configured=store.load() is not None, account_hint=store.hint())


@router.put("/settings/credentials", response_model=CredentialsStatus)
async def save_credentials(payload: CredentialsInput, request: Request) -> CredentialsStatus:
    store = request.app.state.credential_store
    try:
        store.save(payload.account_id, payload.password)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return CredentialsStatus(configured=True, account_hint=store.hint())


@router.delete("/settings/credentials", response_model=CredentialsStatus)
async def delete_credentials(request: Request) -> CredentialsStatus:
    request.app.state.credential_store.delete()
    return CredentialsStatus(configured=False)


@router.get("/logs", response_model=list[LogRead])
async def logs(
    request: Request,
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    level: LogLevel | None = None,
    reservation_id: str | None = Query(default=None, alias="reservationId"),
) -> list[LogRead]:
    rows = repository.list_logs(
        request.app.state.engine,
        limit=limit,
        offset=offset,
        level=level.value if level else None,
        reservation_id=reservation_id,
    )
    return [LogRead.model_validate(row) for row in rows]


@router.delete("/logs")
async def delete_logs(request: Request) -> dict:
    deleted = repository.clear_logs(request.app.state.engine)
    request.app.state.event_bus.publish("logsCleared", {"deleted": deleted})
    return {"success": True, "deleted": deleted}


@router.get("/logs/export")
async def export_logs(request: Request) -> StreamingResponse:
    rows = repository.list_logs(request.app.state.engine, limit=10_000)
    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow(["timestamp", "level", "reservation_id", "message"])
    for row in reversed(rows):
        writer.writerow([row.timestamp.isoformat(), row.level, row.reservation_id or "", row.message])
    headers = {"Content-Disposition": 'attachment; filename="ktx-activity-logs.csv"'}
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv; charset=utf-8", headers=headers)


async def _websocket_events(websocket: WebSocket) -> None:
    await websocket.accept()
    app = websocket.scope["app"]
    await websocket.send_json(
        {
            "type": "status",
            "data": app.state.worker.current_status(),
        }
    )
    try:
        async with app.state.event_bus.subscribe() as queue:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=20)
                    await websocket.send_json(event)
                except asyncio.TimeoutError:
                    await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        return


@router.websocket("/ws/events")
async def websocket_events(websocket: WebSocket) -> None:
    await _websocket_events(websocket)


@router.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket) -> None:
    await _websocket_events(websocket)

