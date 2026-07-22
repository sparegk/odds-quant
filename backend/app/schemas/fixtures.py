from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator


class FixtureImportRow(BaseModel):
    provider_event_key: str = Field(min_length=1, max_length=120)
    competition: str = Field(min_length=1, max_length=120)
    country: str = Field(min_length=1, max_length=80)
    season: str = Field(min_length=1, max_length=40)
    kickoff_at: datetime
    home_team: str = Field(min_length=1, max_length=120)
    away_team: str = Field(min_length=1, max_length=120)
    status: str = Field(default="scheduled", min_length=1, max_length=30)
    observed_at: datetime
    source_updated_at: datetime | None = None

    @field_validator("kickoff_at", "observed_at", "source_updated_at")
    @classmethod
    def require_offset(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("timestamp must include a UTC offset")
        return value

    @model_validator(mode="after")
    def validate_identity_and_time(self) -> FixtureImportRow:
        if self.home_team.casefold() == self.away_team.casefold():
            raise ValueError("home and away teams must differ")
        if self.observed_at >= self.kickoff_at:
            raise ValueError("fixture must be observed before kickoff")
        if self.source_updated_at is not None and self.source_updated_at > self.observed_at:
            raise ValueError("source update cannot be later than observation")
        return self


class FixtureImportSummary(BaseModel):
    fixtures_received: int
    events_created: int
    observations_created: int
