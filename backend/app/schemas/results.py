from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ResultImportRow(BaseModel):
    """One final football result with point-in-time source metadata."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    provider_event_key: str = Field(min_length=1, max_length=120)
    competition: str = Field(min_length=1, max_length=120)
    country: str = Field(min_length=1, max_length=80)
    season: str = Field(min_length=1, max_length=40)
    kickoff_at: datetime
    home_team: str = Field(min_length=1, max_length=120)
    away_team: str = Field(min_length=1, max_length=120)
    home_goals: int = Field(ge=0, le=30)
    away_goals: int = Field(ge=0, le=30)
    settled_at: datetime
    observed_at: datetime
    source_updated_at: datetime | None = None

    @field_validator("source_updated_at", mode="before")
    @classmethod
    def blank_source_timestamp_is_none(cls, value: object) -> object:
        return None if value == "" else value

    @field_validator("kickoff_at", "settled_at", "observed_at", "source_updated_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("timestamp must include a UTC offset")
        return value

    @model_validator(mode="after")
    def validate_chronology_and_identity(self) -> ResultImportRow:
        if self.home_team.casefold() == self.away_team.casefold():
            raise ValueError("home_team and away_team must differ")
        if self.settled_at < self.kickoff_at:
            raise ValueError("settled_at cannot be before kickoff_at")
        if self.observed_at < self.settled_at:
            raise ValueError("observed_at cannot be before settled_at")
        if self.source_updated_at is not None and self.source_updated_at > self.observed_at:
            raise ValueError("source_updated_at cannot be after observed_at")
        return self


class ResultImportSummary(BaseModel):
    job_id: int
    status: str
    rows_received: int
    rows_imported: int
    results_created: int
