from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent


def read_app_version() -> str:
    try:
        return (PROJECT_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "1.1.0"


class AppSettings(BaseSettings):
    app_name: str = "KTX Auto Booker API"
    app_version: str = Field(default_factory=read_app_version)
    automation_mode: Literal["mock", "playwright"] = "mock"
    headless: bool = False
    data_dir: Path = PROJECT_ROOT / "data"
    selector_profile: Path = BACKEND_ROOT / "selectors" / "korail.json"
    frontend_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:5173"]
    )
    browser_timeout_ms: int = 15_000
    manual_action_timeout_seconds: int = 300
    account_id: str | None = None
    account_password: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="KTX_",
        extra="ignore",
    )

    @property
    def database_url(self) -> str:
        return f"sqlite:///{(self.data_dir / 'ktx.db').as_posix()}"


@lru_cache
def get_settings() -> AppSettings:
    return AppSettings()
