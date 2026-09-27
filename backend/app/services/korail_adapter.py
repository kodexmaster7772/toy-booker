from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from datetime import date, time
from pathlib import Path
from typing import Protocol

from playwright.async_api import BrowserContext, Locator, Page, Playwright, async_playwright

from ..core.config import AppSettings
from ..core.schemas import BookingRequest
from .credentials import Credentials
from .image_matcher import TemplateMatcher


class AutomationError(RuntimeError):
    pass


class UserActionRequired(AutomationError):
    pass


@dataclass(frozen=True)
class TrainOption:
    train_number: str
    departure_time: time
    arrival_time: time | None = None
    seat_type: str = "GENERAL"
    seat_label: str | None = None
    row_index: int | None = None
    button_index: int | None = None
    button_text: str | None = None


@dataclass(frozen=True)
class ReservationResult:
    train_number: str
    seat: str | None
    message: str


class KorailAdapter(Protocol):
    keep_open_after_reservation: bool

    async def start(self) -> None: ...

    async def login(self, credentials: Credentials | None) -> None: ...

    async def search(self, request: BookingRequest) -> list[TrainOption]: ...

    async def reserve(self, option: TrainOption) -> ReservationResult: ...

    async def close(self) -> None: ...


class MockKorailAdapter:
    keep_open_after_reservation = False

    def __init__(self) -> None:
        self.attempt = 0

    async def start(self) -> None:
        await asyncio.sleep(0.05)

    async def login(self, credentials: Credentials | None) -> None:
        await asyncio.sleep(0.05)

    async def search(self, request: BookingRequest) -> list[TrainOption]:
        self.attempt += 1
        await asyncio.sleep(0.1)
        if self.attempt < 3:
            return []
        return [
            TrainOption(
                train_number="KTX-DEMO-101",
                departure_time=request.start_time,
                seat_type=request.seat_type.value,
                seat_label="자동 배정",
                row_index=0,
                button_index=0,
                button_text="데모 예매",
            )
        ]

    async def reserve(self, option: TrainOption) -> ReservationResult:
        await asyncio.sleep(0.1)
        return ReservationResult(
            train_number=option.train_number,
            seat=option.seat_label,
            message="데모 예약이 완료되었습니다. 실제 코레일 예약은 생성되지 않았습니다.",
        )

    async def close(self) -> None:
        return None


class PlaywrightKorailAdapter:
    """2026년 코레일 승차권 사이트용 브라우저 어댑터.

    공개 DOM과 접근성 이름을 우선 사용하며 CAPTCHA, 본인인증, 결제는 자동화하지 않는다.
    """

    keep_open_after_reservation = True

    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self.profile = self._load_profile(settings.selector_profile)
        self.playwright: Playwright | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None

    @staticmethod
    def _load_profile(path: Path) -> dict:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AutomationError(f"선택자 설정 파일을 읽을 수 없습니다: {path}") from exc

    async def start(self) -> None:
        self.playwright = await async_playwright().start()
        profile_dir = self.settings.data_dir / "korail-browser-profile"
        profile_dir.mkdir(parents=True, exist_ok=True)
        context_options = {
            "user_data_dir": str(profile_dir),
            "headless": self.settings.headless,
            "locale": "ko-KR",
            "timezone_id": "Asia/Seoul",
            "viewport": {"width": 1440, "height": 1000},
        }
        try:
            self.context = await self.playwright.chromium.launch_persistent_context(
                channel="chrome",
                **context_options,
            )
        except Exception:
            self.context = await self.playwright.chromium.launch_persistent_context(
                **context_options,
            )
        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        self.page.set_default_timeout(self.settings.browser_timeout_ms)

    async def _first_visible(self, selectors: list[str], timeout: int = 900) -> Locator | None:
        assert self.page is not None
        for selector in selectors:
            locator = self.page.locator(selector).first
            try:
                if await locator.is_visible(timeout=timeout):
                    return locator
            except Exception:
                continue
        return None

    async def _body_text(self) -> str:
        assert self.page is not None
        try:
            return " ".join((await self.page.locator("body").inner_text(timeout=3000)).split())
        except Exception:
            return ""

    async def _has_any_text(self, values: list[str]) -> bool:
        body = await self._body_text()
        return any(value.lower() in body.lower() for value in values)

    async def _logged_in(self) -> bool:
        assert self.page is not None
        selectors = self.profile.get(
            "login_success_selectors",
            ["a:has-text('로그아웃')", "button:has-text('로그아웃')"],
        )
        return await self._first_visible(selectors, timeout=400) is not None

    async def _wait_until_logged_in(self, timeout_seconds: int) -> bool:
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        while asyncio.get_running_loop().time() < deadline:
            await self._guard_security_challenge()
            if await self._logged_in():
                return True
            await asyncio.sleep(1)
        return False

    async def _guard_security_challenge(self) -> None:
        challenge_words = self.profile.get(
            "security_challenge_texts",
            ["자동입력 방지", "보안문자", "CAPTCHA", "로봇이 아닙니다", "본인인증"],
        )
        if await self._has_any_text(challenge_words):
            raise UserActionRequired(
                "보안 인증이 표시되었습니다. 열린 코레일 브라우저에서 직접 처리한 뒤 예약 시작을 다시 누르세요."
            )

    async def _wait_page_ready(self) -> None:
        assert self.page is not None
        try:
            await self.page.wait_for_load_state("domcontentloaded")
        except Exception:
            pass
        await asyncio.sleep(1)

    async def _dismiss_communication_error(self) -> bool:
        assert self.page is not None
        body_text = await self._body_text()
        if "통신 중 에러" not in body_text and "잠시 후 다시 이용" not in body_text:
            return False

        buttons = self.page.get_by_role("button", name="확인", exact=True)
        for index in range(await buttons.count() - 1, -1, -1):
            button = buttons.nth(index)
            try:
                if await button.is_visible(timeout=300):
                    await button.click()
                    await asyncio.sleep(0.7)
                    return True
            except Exception:
                continue

        fallback = self.page.locator("button:has-text('확인'), a:has-text('확인')")
        for index in range(await fallback.count() - 1, -1, -1):
            candidate = fallback.nth(index)
            try:
                if await candidate.is_visible(timeout=300):
                    await candidate.click()
                    await asyncio.sleep(0.7)
                    return True
            except Exception:
                continue
        return False

    async def _navigate_to_login_from_main(self) -> None:
        assert self.page is not None
        await self.page.goto(self.profile["main_url"], wait_until="domcontentloaded")
        await self._wait_page_ready()
        await self._dismiss_communication_error()

        login_candidates = [
            self.page.get_by_role("link", name="로그인", exact=True),
            self.page.locator("a[href*='/ticket/login']"),
        ]
        for candidate in login_candidates:
            try:
                if await candidate.count() and await candidate.first.is_visible(timeout=700):
                    await candidate.first.click()
                    await self.page.wait_for_url(re.compile(r"/ticket/login"), timeout=7000)
                    await self._wait_page_ready()
                    return
            except Exception:
                continue

        await self.page.goto(self.profile["login_url"], wait_until="domcontentloaded")
        await self._wait_page_ready()

    async def _open_login_page(self) -> None:
        assert self.page is not None
        for attempt in range(1, 4):
            await self._navigate_to_login_from_main()
            if not await self._dismiss_communication_error():
                return
            if attempt < 3:
                await asyncio.sleep(2)

        raise UserActionRequired(
            "코레일 로그인 화면에서 통신 오류가 3회 반복되었습니다. "
            "열린 창에서 일반 로그인 접속 여부를 확인한 뒤 잠시 후 다시 시도하세요."
        )

    async def login(self, credentials: Credentials | None) -> None:
        assert self.page is not None
        await self._open_login_page()
        await self._guard_security_challenge()
        if await self._logged_in():
            return

        if credentials is not None:
            if "@" in credentials.account_id:
                email_tab = self.page.get_by_role("button", name="이메일 주소", exact=True)
                if await email_tab.count():
                    await email_tab.click()
            elif re.fullmatch(r"01[016789]-?\d{3,4}-?\d{4}", credentials.account_id):
                phone_tab = self.page.get_by_role("button", name="휴대폰 번호", exact=True)
                if await phone_tab.count():
                    await phone_tab.click()
            account = await self._first_visible(self.profile["selectors"]["account_id"])
            password = await self._first_visible(self.profile["selectors"]["password"])
            submit = await self._first_visible(self.profile["selectors"]["login_submit"])
            if account is None or password is None or submit is None:
                raise AutomationError("새 코레일 로그인 입력 요소를 찾지 못했습니다.")
            await account.fill(credentials.account_id)
            await password.fill(credentials.password)
            await submit.click()
            await self._wait_page_ready()
            await self._guard_security_challenge()
            if await self._logged_in():
                return

        if await self._wait_until_logged_in(self.settings.manual_action_timeout_seconds):
            return
        raise UserActionRequired(
            "로그인 제한 시간이 지났습니다. 열린 브라우저에서 로그인한 뒤 예약 시작을 다시 누르세요."
        )

    async def _open_station_dialog(self, selector_key: str) -> Locator:
        assert self.page is not None
        field = await self._first_visible(self.profile["selectors"][selector_key])
        if field is None:
            raise AutomationError(f"역 선택 입력칸을 찾지 못했습니다: {selector_key}")
        await field.click()
        dialog = self.page.locator("[role='dialog']").last
        try:
            await dialog.wait_for(state="visible", timeout=self.settings.browser_timeout_ms)
        except Exception as exc:
            raise AutomationError("기차역 선택 창을 열지 못했습니다.") from exc
        return dialog

    async def _select_station(self, selector_key: str, station: str) -> None:
        dialog = await self._open_station_dialog(selector_key)
        exact_link = dialog.get_by_role("link", name=station, exact=True)
        if await exact_link.count() and await exact_link.first.is_visible():
            await exact_link.first.click()
            return

        search_input = dialog.get_by_placeholder(re.compile("역 이름|역명"))
        if not await search_input.count():
            raise AutomationError(f"역 검색 입력칸을 찾지 못했습니다: {station}")
        await search_input.fill(station)
        search_button = dialog.get_by_role("button", name="검색", exact=True)
        await search_button.click()
        result = dialog.get_by_role("link", name=station, exact=True)
        try:
            await result.first.wait_for(state="visible", timeout=self.settings.browser_timeout_ms)
            await result.first.click()
        except Exception as exc:
            raise AutomationError(f"코레일에서 역을 찾지 못했습니다: {station}") from exc

    async def _select_departure_datetime(self, travel_date: date, start_time: time) -> None:
        assert self.page is not None
        field = await self._first_visible(self.profile["selectors"]["date"])
        if field is None:
            raise AutomationError("출발일 입력칸을 찾지 못했습니다.")
        await field.click()
        dialog = self.page.locator("[role='dialog']").last
        await dialog.wait_for(state="visible", timeout=self.settings.browser_timeout_ms)

        payload = {
            "month": travel_date.strftime("%Y. %m."),
            "day": str(travel_date.day),
            "hour": f"{start_time.hour:02d}시",
        }
        selected = await dialog.evaluate(
            """(dialog, target) => {
                const normalize = value => (value || '').replace(/\\s+/g, ' ').trim();
                const calendars = Array.from(dialog.querySelectorAll('.datepicker'));
                const calendar = calendars.find(item =>
                    normalize(item.querySelector('.date')?.textContent) === target.month
                );
                if (!calendar) return { ok: false, reason: 'month' };
                const dayLinks = Array.from(calendar.querySelectorAll('td:not(.disabled) a'));
                const dayLink = dayLinks.find(link =>
                    normalize(link.querySelector('.day')?.textContent) === target.day
                );
                if (!dayLink) return { ok: false, reason: 'day' };
                dayLink.click();
                const hourLinks = Array.from(dialog.querySelectorAll('.timeSelect a'));
                const hourLink = hourLinks.find(link => normalize(link.textContent) === target.hour);
                if (!hourLink) return { ok: false, reason: 'hour' };
                hourLink.click();
                return { ok: true };
            }""",
            payload,
        )
        if not selected.get("ok"):
            reason = selected.get("reason", "unknown")
            raise AutomationError(f"날짜/시간을 선택하지 못했습니다: {reason}")

        apply_button = dialog.get_by_role("button", name="적용", exact=True)
        await apply_button.click()
        try:
            await dialog.wait_for(state="hidden", timeout=self.settings.browser_timeout_ms)
        except Exception:
            pass

    async def _prepare_search_form(self, request: BookingRequest) -> None:
        assert self.page is not None
        await self.page.goto(self.profile["search_url"], wait_until="domcontentloaded")
        await self._wait_page_ready()
        await self._guard_security_challenge()
        await self._select_station("departure", request.departure)
        await self._select_station("arrival", request.arrival)
        await self._select_departure_datetime(request.travel_date, request.start_time)

    @staticmethod
    def _extract_train_number(text_value: str, index: int) -> str:
        match = re.search(r"(KTX(?:-산천)?|KTX-이음|ITX-[가-힣]+)\s*[- ]?\s*(\d+)", text_value, re.IGNORECASE)
        if match:
            return f"{match.group(1).upper()}-{match.group(2)}"
        return f"TRAIN-{index + 1}"

    @staticmethod
    def _extract_times(text_value: str) -> list[time]:
        matches = re.findall(r"(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?!\d)", text_value)
        return [time(hour=int(hour), minute=int(minute)) for hour, minute in matches]

    @staticmethod
    def _is_train_row(text_value: str) -> bool:
        return bool(re.search(r"\bKTX(?:-산천|-이음)?\b", text_value, re.IGNORECASE)) and len(
            PlaywrightKorailAdapter._extract_times(text_value)
        ) >= 1

    @staticmethod
    def _button_is_available(text_value: str) -> bool:
        compact = " ".join(text_value.split())
        blocked = ["매진", "예약대기", "신청불가", "운행중지"]
        allowed = ["예매", "예약", "좌석선택"]
        return any(word in compact for word in allowed) and not any(word in compact for word in blocked)

    async def _available_actions(self, row: Locator) -> list[tuple[int, str]]:
        controls = row.locator("button, a")
        actions: list[tuple[int, str]] = []
        for index in range(await controls.count()):
            control = controls.nth(index)
            try:
                text_value = " ".join((await control.inner_text()).split())
                if not text_value or not self._button_is_available(text_value):
                    continue
                if not await control.is_visible() or not await control.is_enabled():
                    continue
                aria_disabled = await control.get_attribute("aria-disabled")
                if aria_disabled == "true":
                    continue
                actions.append((index, text_value))
            except Exception:
                continue
        return actions

    @staticmethod
    def _choose_action(
        actions: list[tuple[int, str]],
        row_text: str,
        request: BookingRequest,
    ) -> tuple[int, str, str] | None:
        def rank(item: tuple[int, str]) -> tuple[int, int]:
            text_value = item[1]
            direct = 0 if "예매" in text_value or "예약" in text_value else 1
            if request.seat_type.value == "FIRST":
                seat = 0 if "특실" in text_value else 1
            else:
                seat = 0 if "일반" in text_value else 1
            return seat, direct

        for button_index, button_text in sorted(actions, key=rank):
            combined = f"{row_text} {button_text}"
            is_first = "특실" in button_text and "일반" not in button_text
            is_standing = "입석" in button_text or "입석" in combined and "일반실" not in combined
            if is_standing and not request.allow_standing:
                continue
            if request.seat_type.value == "FIRST" and not (is_first or "특실" in combined):
                continue
            if is_first and not (request.seat_type.value == "FIRST" or request.include_first_class):
                continue
            seat_type = "FIRST" if is_first else "GENERAL"
            return button_index, button_text, seat_type
        return None

    async def search(self, request: BookingRequest) -> list[TrainOption]:
        assert self.page is not None
        await self._prepare_search_form(request)
        submit = await self._first_visible(self.profile["selectors"]["search_submit"])
        if submit is None:
            raise AutomationError("열차 조회 버튼을 찾지 못했습니다.")
        await submit.click()
        try:
            await self.page.wait_for_url(re.compile(r".*/ticket/search/list.*"), timeout=self.settings.browser_timeout_ms)
        except Exception:
            await self._wait_page_ready()
        await asyncio.sleep(2)
        await self._guard_security_challenge()

        if await self._has_any_text(["접속자가 많아", "잠시 후 다시", "서비스 이용이 원활하지"]):
            raise UserActionRequired("코레일 접속이 혼잡합니다. 잠시 후 다시 시작하세요.")

        rows = self.page.locator(self.profile["selectors"]["result_rows"])
        options: list[TrainOption] = []
        for index in range(await rows.count()):
            row = rows.nth(index)
            try:
                text_value = " ".join((await row.inner_text()).split())
            except Exception:
                continue
            if not self._is_train_row(text_value):
                continue
            times = self._extract_times(text_value)
            departure_time = times[0]
            arrival_time = times[1] if len(times) > 1 else None
            if not (request.start_time <= departure_time <= request.end_time):
                continue
            actions = await self._available_actions(row)
            action = self._choose_action(actions, text_value, request)
            if action is None:
                continue
            button_index, button_text, seat_type = action
            options.append(
                TrainOption(
                    train_number=self._extract_train_number(text_value, index),
                    departure_time=departure_time,
                    arrival_time=arrival_time,
                    seat_type=seat_type,
                    seat_label="특실 자동 배정" if seat_type == "FIRST" else "일반실 자동 배정",
                    row_index=index,
                    button_index=button_index,
                    button_text=button_text,
                )
            )
        return sorted(options, key=lambda option: option.departure_time)

    async def _confirm_reservation_dialog(self) -> None:
        assert self.page is not None
        dialogs = self.page.locator("[role='dialog']")
        if not await dialogs.count():
            return
        dialog = dialogs.last
        try:
            if not await dialog.is_visible(timeout=1000):
                return
            text_value = " ".join((await dialog.inner_text()).split())
            if any(word in text_value for word in ["보안문자", "본인인증", "자동입력"]):
                raise UserActionRequired("예약 과정에서 보안 인증이 표시되었습니다. 직접 처리하세요.")
            for label in ["예매", "예약", "확인"]:
                button = dialog.get_by_role("button", name=label, exact=True)
                if await button.count() and await button.first.is_visible():
                    await button.first.click()
                    await asyncio.sleep(1)
                    return
        except UserActionRequired:
            raise
        except Exception:
            return

    async def reserve(self, option: TrainOption) -> ReservationResult:
        assert self.page is not None
        await self._guard_security_challenge()
        rows = self.page.locator(self.profile["selectors"]["result_rows"])
        if option.row_index is not None and option.row_index < await rows.count():
            row = rows.nth(option.row_index)
            controls = row.locator("button, a")
            if option.button_index is not None and option.button_index < await controls.count():
                button = controls.nth(option.button_index)
                try:
                    if await button.is_visible() and await button.is_enabled():
                        await button.click()
                        await asyncio.sleep(1)
                        await self._confirm_reservation_dialog()
                        await self._guard_security_challenge()
                        body = await self._body_text()
                        if any(word in body for word in self.profile["reservation_success_texts"]):
                            return ReservationResult(
                                train_number=option.train_number,
                                seat=option.seat_label,
                                message="좌석을 확보했습니다. 열린 코레일 브라우저에서 결제 제한시간 안에 직접 결제하세요.",
                            )
                        if "/ticket/search/list" not in self.page.url:
                            return ReservationResult(
                                train_number=option.train_number,
                                seat=option.seat_label,
                                message="예약 단계로 이동했습니다. 열린 코레일 브라우저에서 예약 상태를 확인하고 직접 결제하세요.",
                            )
                except UserActionRequired:
                    raise
                except Exception:
                    pass

        template_value = self.profile.get("reservation_button_template")
        if template_value:
            template_path = self.settings.selector_profile.parent / template_value
            if template_path.exists():
                screenshot = await self.page.screenshot()
                match = TemplateMatcher.find(screenshot, template_path)
                if match:
                    await self.page.mouse.click(match.center_x, match.center_y)
                    await asyncio.sleep(1)
                    await self._guard_security_challenge()
                    return ReservationResult(
                        train_number=option.train_number,
                        seat=option.seat_label,
                        message="예약 단계로 이동했습니다. 열린 브라우저에서 상태를 확인하고 직접 결제하세요.",
                    )
        raise AutomationError(
            "예약 버튼을 눌렀지만 예약 완료 화면을 확인하지 못했습니다. 열린 코레일 브라우저를 확인하세요."
        )

    async def close(self) -> None:
        if self.context is not None:
            await self.context.close()
            self.context = None
        if self.playwright is not None:
            await self.playwright.stop()
            self.playwright = None


def create_adapter(settings: AppSettings) -> KorailAdapter:
    if settings.automation_mode == "playwright":
        return PlaywrightKorailAdapter(settings)
    return MockKorailAdapter()
