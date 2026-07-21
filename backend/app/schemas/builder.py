from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SUPPORTED_MARKETS = {
    "MATCH_RESULT",
    "TOTAL_GOALS",
    "BTTS",
    "BOTH_TEAMS_TO_SCORE",
    "DOUBLE_CHANCE",
    "HOME_TEAM_TOTAL",
    "AWAY_TEAM_TOTAL",
    "TEAM_TOTAL_HOME",
    "TEAM_TOTAL_AWAY",
}


class BetBuilderLeg(BaseModel):
    model_config = ConfigDict(extra="forbid")

    market_type: str
    selection: str
    line: float | None = None

    @field_validator("market_type", "selection")
    @classmethod
    def uppercase_code(cls, value: str) -> str:
        return value.upper()

    @field_validator("market_type")
    @classmethod
    def supported_market(cls, value: str) -> str:
        if value not in SUPPORTED_MARKETS:
            raise ValueError("unsupported bet-builder market")
        return value


class CreateBetBuilderQuoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: int = Field(gt=0)
    prediction_output_id: int = Field(gt=0)
    legs: list[BetBuilderLeg] = Field(min_length=2, max_length=4)
    offered_odds: float | None = Field(default=None, gt=1)
    offered_odds_source: str | None = Field(default=None, min_length=1, max_length=120)
    offered_odds_observed_at: datetime | None = None
    quoted_at: datetime | None = None

    @field_validator("offered_odds_observed_at", "quoted_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("timestamp must include a UTC offset")
        return value

    @model_validator(mode="after")
    def require_complete_offered_price_provenance(self) -> CreateBetBuilderQuoteRequest:
        price_fields = (
            self.offered_odds,
            self.offered_odds_source,
            self.offered_odds_observed_at,
        )
        if any(value is not None for value in price_fields) and not all(
            value is not None for value in price_fields
        ):
            raise ValueError("offered odds require source and original observation timestamp")
        return self


class BetBuilderLegView(BaseModel):
    market_type: str
    selection: str
    line: float | None
    marginal_probability: float


class BetBuilderQuoteView(BaseModel):
    id: int
    event_id: int
    model_version_id: int
    model_version: str
    is_demo: bool
    evidence_class: str
    prediction_output_id: int
    predicted_at: datetime
    inputs_as_of: datetime
    quoted_at: datetime
    fingerprint: str
    feature_version: str
    input_fingerprint: str
    legs: list[BetBuilderLegView]
    joint_probability: float
    lower_joint_probability: float
    upper_joint_probability: float
    independent_product: float
    dependence_ratio: float
    fair_odds: float
    offered_odds: float | None
    offered_odds_source: str | None
    offered_odds_observed_at: datetime | None
    expected_value: float | None
    lower_expected_value: float | None
    warnings: list[str]
