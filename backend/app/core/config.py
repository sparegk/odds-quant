from functools import lru_cache
from typing import Self

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ODDSQUANT_",
        env_file="../.env",
        extra="ignore",
    )

    app_name: str = "OddsQuant API"
    environment: str = "development"
    database_url: str = "sqlite:///./data/oddsquant.db"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    admin_api_key: str | None = None
    seed_demo: bool = True
    odds_stale_after_seconds: int = Field(default=300, ge=1)
    provider_poll_seconds: int = Field(default=900, ge=30)
    provider_near_kickoff_poll_seconds: int = Field(default=300, ge=30)
    provider_near_kickoff_window_seconds: int = Field(default=21600, ge=60)
    odds_api_io_key: str | None = None
    odds_api_io_base_url: str = "https://api.odds-api.io/v3"
    matchday_timezone: str = "Europe/Athens"
    matchday_form_matches: int = Field(default=5, ge=1, le=20)

    @field_validator("admin_api_key", "odds_api_io_key", mode="before")
    @classmethod
    def empty_admin_key_is_unset(cls, value: object) -> object:
        return None if value == "" else value

    @property
    def cors_origin_list(self) -> list[str]:
        return [part.strip() for part in self.cors_origins.split(",") if part.strip()]

    @field_validator("database_url", mode="after")
    @classmethod
    def use_psycopg_three(cls, value: str) -> str:
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value

    @model_validator(mode="after")
    def validate_provider_poll_intervals(self) -> Self:
        if self.provider_near_kickoff_poll_seconds > self.provider_poll_seconds:
            raise ValueError("near-kickoff provider polling cannot be slower than base polling")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
