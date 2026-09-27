import os
from dataclasses import dataclass

import keyring
from keyring.errors import KeyringError

from ..core.config import AppSettings


SERVICE_NAME = "ktx-auto-booker"


@dataclass(frozen=True)
class Credentials:
    account_id: str
    password: str


class CredentialStore:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings

    def save(self, account_id: str, password: str) -> None:
        try:
            keyring.set_password(SERVICE_NAME, "account_id", account_id)
            keyring.set_password(SERVICE_NAME, "password", password)
        except KeyringError as exc:
            raise RuntimeError(
                "운영체제 자격증명 저장소를 사용할 수 없습니다. .env의 "
                "KTX_ACCOUNT_ID/KTX_ACCOUNT_PASSWORD를 개발용으로 사용하세요."
            ) from exc

    def load(self) -> Credentials | None:
        env_id = self.settings.account_id or os.getenv("KTX_ACCOUNT_ID")
        env_password = self.settings.account_password or os.getenv("KTX_ACCOUNT_PASSWORD")
        if env_id and env_password:
            return Credentials(env_id, env_password)
        try:
            account_id = keyring.get_password(SERVICE_NAME, "account_id")
            password = keyring.get_password(SERVICE_NAME, "password")
        except KeyringError:
            return None
        if account_id and password:
            return Credentials(account_id, password)
        return None

    def delete(self) -> None:
        for key in ("account_id", "password"):
            try:
                keyring.delete_password(SERVICE_NAME, key)
            except (KeyringError, keyring.errors.PasswordDeleteError):
                pass

    def hint(self) -> str | None:
        credentials = self.load()
        if credentials is None:
            return None
        value = credentials.account_id
        if "@" in value:
            local, domain = value.split("@", 1)
            return f"{local[:2]}***@{domain}"
        return f"{value[:2]}***" if len(value) > 2 else "***"

