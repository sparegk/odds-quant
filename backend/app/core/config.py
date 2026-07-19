from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ODDSQUANT_", env_file="../.env")

    app_name: str = "OddsQuant API"
    environment: str = "development"
    database_url: str = "sqlite:///./data/oddsquant.db"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    admin_api_key: str | None = None
    seed_demo: bool = True
    odds_stale_after_seconds: int = Field(default=300, ge=1)

    @field_validator("admin_api_key", mode="before")
    @classmethod
    def empty_admin_key_is_unset(cls, value: object) -> object:
        return None if value == "" else value

    @property
    def cors_origin_list(self) -> list[str]:
        return [part.strip() for part in self.cors_origins.split(",") if part.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
