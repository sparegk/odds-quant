from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.matchday import RecommendationQualityView


class CaptureRecommendationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signal_id: int = Field(gt=0)
    captured_at: datetime | None = None

    @field_validator("captured_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("timestamp must include a UTC offset")
        return value


class RefreshRecommendationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    as_of: datetime | None = None

    @field_validator("as_of")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("timestamp must include a UTC offset")
        return value


class RecommendationTrackingView(BaseModel):
    closing_line_status: str
    closing_odds_snapshot_id: int | None
    closing_odds: float | None
    closing_observed_at: datetime | None
    closing_recorded_at: datetime | None
    closing_line_value: float | None
    settlement_status: str
    result_id: int | None
    settlement: str | None
    settled_at: datetime | None
    profit_units: float | None
    updated_at: datetime


class RecommendationSnapshotView(BaseModel):
    id: int
    signal_id: int
    event_id: int
    selection_id: int
    bookmaker_id: int
    odds_snapshot_id: int
    prediction_id: int
    model_version_id: int
    evaluation_run_id: int
    tax_profile_id: int
    captured_at: datetime
    kickoff_at: datetime
    price_observed_at: datetime
    tax_profile_verified_at: datetime
    constraint_observed_at: datetime
    market_type: str
    line: float | None
    selection_code: str
    settlement_rule_key: str
    currency: str
    offered_odds: float
    model_probability: float
    lower_probability: float
    lower_expected_value: float
    net_expected_value: float
    lower_net_expected_value: float
    stake: float
    cash_outlay: float
    minimum_acceptable_odds: float
    recommendation_quality: RecommendationQualityView
    model_input_fingerprint: str
    feature_version: str
    fingerprint: str
    tracking: RecommendationTrackingView
