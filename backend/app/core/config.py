"""Application settings, loaded from the environment and validated at boot."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from fastapi import Request
from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

Environment = Literal["development", "test", "production"]

_WEAK_SECRET_MARKERS = ("change-me", "changeme")
_MIN_SECRET_LENGTH = 32


class Settings(BaseSettings):
    """Every runtime option. Documented one-for-one in `.env.example`."""

    model_config = SettingsConfigDict(extra="ignore", case_sensitive=False)

    app_env: Environment = "development"
    app_name: str = "Delphin CRM"
    app_version: str = "0.1.0"
    app_base_url: str = "http://localhost:5173"

    database_url: str = Field(description="postgresql+asyncpg://user:pass@host:5432/db")
    database_pool_size: int = Field(default=10, ge=1)
    database_max_overflow: int = Field(default=10, ge=0)
    database_echo: bool = False

    secret_key: SecretStr
    cron_secret: SecretStr

    # Firebase Auth is the identity provider (ADR-0009). The SDK also reads
    # FIREBASE_AUTH_EMULATOR_HOST and GOOGLE_APPLICATION_CREDENTIALS from the environment.
    firebase_project_id: str = Field(min_length=1)

    allowed_hosts: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["localhost", "127.0.0.1"]
    )
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)
    expose_docs: bool = False

    session_cookie_name: str = "delphin_session"
    csrf_cookie_name: str = "delphin_csrf"
    csrf_header_name: str = "X-CSRF-Token"
    session_ttl_hours: int = Field(default=12, ge=1)
    max_request_body_bytes: int = Field(default=12 * 1024 * 1024, ge=1024)
    #: Private file storage root (local backend). Never served directly.
    storage_dir: str = "/data/uploads"
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, ge=1024)

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_json: bool | None = None

    @field_validator("allowed_hosts", "cors_origins", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("log_level", mode="before")
    @classmethod
    def _upper(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator("database_url")
    @classmethod
    def _async_driver(cls, value: str) -> str:
        if not value.startswith("postgresql+asyncpg://"):
            msg = "DATABASE_URL must use the postgresql+asyncpg:// driver"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def _production_guards(self) -> Settings:
        if not self.is_production:
            return self
        for name in ("secret_key", "cron_secret"):
            value: str = getattr(self, name).get_secret_value()
            if len(value) < _MIN_SECRET_LENGTH or any(
                marker in value.lower() for marker in _WEAK_SECRET_MARKERS
            ):
                msg = f"{name.upper()} is too weak for production (openssl rand -hex 32)"
                raise ValueError(msg)
        if self.cors_origins:
            msg = "CORS_ORIGINS must be empty in production: the SPA is served same-origin"
            raise ValueError(msg)
        if "*" in self.allowed_hosts:
            msg = "ALLOWED_HOSTS must list explicit hosts in production"
            raise ValueError(msg)
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def docs_enabled(self) -> bool:
        return not self.is_production or self.expose_docs

    @property
    def json_logs(self) -> bool:
        return self.is_production if self.log_json is None else self.log_json


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide settings, read once from the environment."""
    return Settings()  # required fields come from the environment


def get_app_settings(request: Request) -> Settings:
    """FastAPI dependency: the settings the running app was created with."""
    settings: Settings = request.app.state.settings
    return settings
