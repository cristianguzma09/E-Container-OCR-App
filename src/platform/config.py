"""Application configuration.

Loaded once from the environment (and an optional ``.env`` file) and shared
through :func:`get_settings`. This is the only place that reads env vars.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Maritime Container OCR API"
    app_version: str = "1.0.0"
    environment: str = "local"
    debug: bool = True

    # SQLAlchemy URL. Driver is psycopg (v3): postgresql+psycopg://user:pass@host:port/db
    database_url: str = "postgresql+psycopg://econtainer:econtainer@localhost:5432/econtainer"
    database_echo: bool = False

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:4200"])


@lru_cache
def get_settings() -> Settings:
    return Settings()
