from datetime import datetime
from functools import lru_cache
import os
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


MINIMUM_RECORD_START_AT = datetime.fromisoformat("2026-05-07T18:30:00+08:00")


class Settings(BaseSettings):
    project_name: str = "Crypto Backtest Record System"
    api_prefix: str = "/api"
    database_url: str = Field(
        default="postgresql+psycopg://backtest:change_me@postgres:5432/backtest_records",
        alias="DATABASE_URL",
    )
    storage_root: Path = Field(default=Path("/data/storage"), alias="STORAGE_ROOT")
    max_upload_mb: int = Field(default=200, alias="MAX_UPLOAD_MB")
    backend_cors_origins: str = Field(default="*", alias="BACKEND_CORS_ORIGINS")
    default_workspace_name: str = Field(default="Personal", alias="DEFAULT_WORKSPACE_NAME")
    default_user_email: str = Field(default="local@example.local", alias="DEFAULT_USER_EMAIL")
    record_start_at: datetime = Field(default=MINIMUM_RECORD_START_AT, alias="RECORD_START_AT")
    enforce_minimum_record_start: bool = Field(default=True, alias="ENFORCE_MINIMUM_RECORD_START")
    default_timezone: str = Field(default="Asia/Taipei", alias="DEFAULT_TIMEZONE")
    bitget_api_base_url: str = Field(default="https://api.bitget.com", alias="BITGET_API_BASE_URL")
    bitget_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "BITGET_API_KEY",
            "BITGET_KEY",
            "BITGET_ACCESS_KEY",
            "BITGET_API_ACCESS_KEY",
            "EXCHANGE_API_KEY",
            "API_KEY",
            "ACCESS_KEY",
        ),
    )
    bitget_api_secret: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "BITGET_API_SECRET",
            "BITGET_SECRET",
            "BITGET_SECRET_KEY",
            "BITGET_API_SECRET_KEY",
            "EXCHANGE_API_SECRET",
            "API_SECRET",
            "SECRET_KEY",
        ),
    )
    bitget_api_passphrase: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "BITGET_API_PASSPHRASE",
            "BITGET_PASSPHRASE",
            "BITGET_PASS_PHRASE",
            "BITGET_API_PASS_PHRASE",
            "BITGET_API_PASSWORD",
            "BITGET_PASSWORD",
            "EXCHANGE_API_PASSPHRASE",
            "API_PASSPHRASE",
            "PASSPHRASE",
        ),
    )
    bitget_locale: str = Field(default="en-US", alias="BITGET_LOCALE")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    @model_validator(mode="after")
    def apply_minimum_record_start(self) -> "Settings":
        self.bitget_api_key = self.bitget_api_key or env_alias(
            "BITGET_API_KEY",
            "BITGET_KEY",
            "BITGET_ACCESS_KEY",
            "BITGET_API_ACCESS_KEY",
            "EXCHANGE_API_KEY",
            "API_KEY",
            "ACCESS_KEY",
        )
        self.bitget_api_secret = self.bitget_api_secret or env_alias(
            "BITGET_API_SECRET",
            "BITGET_SECRET",
            "BITGET_SECRET_KEY",
            "BITGET_API_SECRET_KEY",
            "EXCHANGE_API_SECRET",
            "API_SECRET",
            "SECRET_KEY",
        )
        self.bitget_api_passphrase = self.bitget_api_passphrase or env_alias(
            "BITGET_API_PASSPHRASE",
            "BITGET_PASSPHRASE",
            "BITGET_PASS_PHRASE",
            "BITGET_API_PASS_PHRASE",
            "BITGET_API_PASSWORD",
            "BITGET_PASSWORD",
            "EXCHANGE_API_PASSPHRASE",
            "API_PASSPHRASE",
            "PASSPHRASE",
        )
        self.bitget_api_key = clean_secret(self.bitget_api_key)
        self.bitget_api_secret = clean_secret(self.bitget_api_secret)
        self.bitget_api_passphrase = clean_secret(self.bitget_api_passphrase)
        if self.enforce_minimum_record_start and self.record_start_at < MINIMUM_RECORD_START_AT:
            self.record_start_at = MINIMUM_RECORD_START_AT
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]

    @property
    def allow_all_cors_origins(self) -> bool:
        return "*" in self.cors_origins


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.storage_root.mkdir(parents=True, exist_ok=True)
    return settings


def env_alias(*names: str) -> str | None:
    lookup = {key.upper(): value for key, value in os.environ.items()}
    for name in names:
        value = clean_secret(lookup.get(name.upper()))
        if value:
            return value
    return None


def clean_secret(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {'"', "'"}:
        cleaned = cleaned[1:-1].strip()
    return cleaned or None
