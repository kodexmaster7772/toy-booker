import time
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.core.config import AppSettings
from backend.app.core.schemas import BookingRequest
from backend.app.main import create_app
from backend.app.services.korail_adapter import PlaywrightKorailAdapter


def make_client(tmp_path: Path) -> TestClient:
    settings = AppSettings(
        automation_mode="mock",
        data_dir=tmp_path,
        frontend_origins=["http://localhost:5173"],
    )
    return TestClient(create_app(settings))


BOOKING = {
    "departure": "익산",
    "arrival": "서울",
    "date": "2027-02-20",
    "startTime": "06:00",
    "endTime": "12:00",
    "seatType": "GENERAL",
    "includeFirstClass": False,
    "allowStanding": False,
    "detectCancellation": True,
}


def test_health_and_settings(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        assert client.get("/api/health").json()["ok"] is True
        home = client.get("/")
        assert home.status_code == 200
        assert "KTX Auto Booker" in home.text
        settings = client.get("/api/settings").json()
        assert settings["retryCount"] == 10
        assert settings["automationMode"] == "mock"

        response = client.put(
            "/api/settings",
            json={
                "autoPayment": False,
                "cancellationDetection": True,
                "retryCount": 3,
                "retryInterval": 1,
                "browserNotification": True,
                "soundNotification": True,
                "emailNotification": False,
            },
        )
        assert response.status_code == 200
        assert response.json()["retryCount"] == 3

        with client.websocket_connect("/api/ws/events") as websocket:
            event = websocket.receive_json()
            assert event["type"] == "status"
            assert event["data"]["state"] == "IDLE"


def test_mock_booking_reaches_reserved(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        client.put(
            "/api/settings",
            json={
                "autoPayment": False,
                "cancellationDetection": True,
                "retryCount": 3,
                "retryInterval": 1,
                "browserNotification": True,
                "soundNotification": True,
                "emailNotification": False,
            },
        )
        started = client.post("/api/reservations/start", json=BOOKING)
        assert started.status_code == 202
        reservation_id = started.json()["reservation"]["id"]

        deadline = time.monotonic() + 6
        state = None
        while time.monotonic() < deadline:
            state = client.get(f"/api/reservations/{reservation_id}").json()["status"]
            if state == "RESERVED":
                break
            time.sleep(0.1)
        assert state == "RESERVED"
        assert client.get("/api/logs").json()
        exported = client.get("/api/logs/export")
        assert exported.status_code == 200
        assert "timestamp,level,reservation_id,message" in exported.text
        deleted = client.delete("/api/logs").json()
        assert deleted["deleted"] > 0
        assert client.get("/api/logs").json() == []


def test_rejects_auto_payment(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        response = client.put(
            "/api/settings",
            json={
                "autoPayment": True,
                "cancellationDetection": True,
                "retryCount": 10,
                "retryInterval": 3,
                "browserNotification": True,
                "soundNotification": True,
                "emailNotification": False,
            },
        )
        assert response.status_code == 422


def test_new_korail_train_card_parser() -> None:
    text = "KTX-산천 503 익산 07:12 서울 09:03 일반실 예매 특실 매진"
    assert PlaywrightKorailAdapter._is_train_row(text)
    assert PlaywrightKorailAdapter._extract_train_number(text, 0) == "KTX-산천-503"
    times = PlaywrightKorailAdapter._extract_times(text)
    assert [value.strftime("%H:%M") for value in times] == ["07:12", "09:03"]


def test_general_seat_button_is_preferred() -> None:
    request = BookingRequest.model_validate(BOOKING)
    chosen = PlaywrightKorailAdapter._choose_action(
        [(2, "특실 예매"), (4, "일반실 예매")],
        "KTX 101 익산 07:00 서울 09:00",
        request,
    )
    assert chosen == (4, "일반실 예매", "GENERAL")
