from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class MarketType(StrEnum):
    MATCH_RESULT = "MATCH_RESULT"
    TOTAL_GOALS = "TOTAL_GOALS"
    BOTH_TEAMS_TO_SCORE = "BOTH_TEAMS_TO_SCORE"
    DOUBLE_CHANCE = "DOUBLE_CHANCE"
    TEAM_TOTAL_HOME = "TEAM_TOTAL_HOME"
    TEAM_TOTAL_AWAY = "TEAM_TOTAL_AWAY"
    TOTAL_CORNERS = "TOTAL_CORNERS"


EXPECTED_SELECTIONS: dict[MarketType, frozenset[str]] = {
    MarketType.MATCH_RESULT: frozenset({"HOME", "DRAW", "AWAY"}),
    MarketType.TOTAL_GOALS: frozenset({"OVER", "UNDER"}),
    MarketType.BOTH_TEAMS_TO_SCORE: frozenset({"YES", "NO"}),
    MarketType.DOUBLE_CHANCE: frozenset({"HOME_OR_DRAW", "AWAY_OR_DRAW", "HOME_OR_AWAY"}),
    MarketType.TEAM_TOTAL_HOME: frozenset({"OVER", "UNDER"}),
    MarketType.TEAM_TOTAL_AWAY: frozenset({"OVER", "UNDER"}),
    MarketType.TOTAL_CORNERS: frozenset({"OVER", "UNDER"}),
}

LINE_MARKETS = {
    MarketType.TOTAL_GOALS,
    MarketType.TEAM_TOTAL_HOME,
    MarketType.TEAM_TOTAL_AWAY,
    MarketType.TOTAL_CORNERS,
}


class OddsImportRow(BaseModel):
    """One selection price in a coherent pre-match bookmaker snapshot."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    provider_event_key: str = Field(min_length=1, max_length=120)
    competition: str = Field(min_length=1, max_length=120)
    country: str = Field(min_length=1, max_length=80)
    season: str = Field(min_length=1, max_length=40)
    kickoff_at: datetime
    home_team: str = Field(min_length=1, max_length=120)
    away_team: str = Field(min_length=1, max_length=120)
    bookmaker: str = Field(min_length=1, max_length=120)
    market_type: MarketType
    line: Decimal | None = Field(default=None, gt=0, max_digits=8, decimal_places=2)
    selection_code: str = Field(min_length=1, max_length=40)
    selection_name: str = Field(min_length=1, max_length=120)
    decimal_odds: Decimal = Field(gt=1, le=1_000, max_digits=12, decimal_places=5)
    observed_at: datetime
    source_updated_at: datetime | None = None
    period: str = Field(default="FULL_TIME", min_length=1, max_length=30)
    currency: str = Field(default="EUR", pattern=r"^[A-Z]{3}$")
    settlement_rule_key: str = Field(default="standard_90_minutes", min_length=1, max_length=80)
    is_closing: bool = False

    @field_validator("line", "source_updated_at", mode="before")
    @classmethod
    def blank_optional_values_are_none(cls, value: object) -> object:
        return None if value == "" else value

    @field_validator("is_closing", mode="before")
    @classmethod
    def blank_closing_value_is_false(cls, value: object) -> object:
        return False if value == "" else value

    @field_validator("kickoff_at", "observed_at", "source_updated_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("timestamp must include a UTC offset")
        return value

    @field_validator("selection_code", "period", mode="after")
    @classmethod
    def normalize_codes(cls, value: str) -> str:
        return value.upper()

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_market_semantics(self) -> OddsImportRow:
        if self.home_team.casefold() == self.away_team.casefold():
            raise ValueError("home_team and away_team must differ")
        if self.market_type in LINE_MARKETS and self.line is None:
            raise ValueError(f"line is required for {self.market_type}")
        if self.market_type not in LINE_MARKETS and self.line is not None:
            raise ValueError(f"line is not valid for {self.market_type}")
        if self.selection_code not in EXPECTED_SELECTIONS[self.market_type]:
            raise ValueError(
                f"selection_code {self.selection_code!r} is not valid for {self.market_type}"
            )
        if self.source_updated_at is not None and self.source_updated_at > self.observed_at:
            raise ValueError("source_updated_at cannot be after observed_at")
        if self.observed_at > self.kickoff_at:
            raise ValueError("pre-match odds cannot be observed after kickoff")
        return self

    @property
    def line_key(self) -> str:
        if self.line is None:
            return ""
        return format(self.line.normalize(), "f")


class ImportSummary(BaseModel):
    job_id: int
    status: str
    rows_received: int
    rows_imported: int
    snapshots_created: int
