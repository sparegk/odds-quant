from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class GenerateSignalsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output_id: int = Field(gt=0)
    generated_at: datetime | None = None

    @field_validator("generated_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("timestamp must include a UTC offset")
        return value


class ValueSignalView(BaseModel):
    id: int
    event_id: int
    output_id: int
    model_version_id: int
    model_version: str
    evaluation_run_id: int
    prediction_id: int
    market_id: int
    market_type: str
    line: float | None
    selection_id: int
    selection_code: str
    selection_name: str
    bookmaker_id: int
    bookmaker: str
    odds_snapshot_id: int
    signal_type: str
    offered_odds: float
    raw_implied_probability: float
    market_fair_probability: float
    model_probability: float
    lower_probability: float
    expected_value: float
    lower_expected_value: float
    probability_edge: float
    confidence: float
    calibration_error: float
    odds_age_minutes: float
    bookmaker_count: int
    odds_move_ratio: float
    implied_move_points: float
    generated_at: datetime
    reasons: list[str]
    risks: list[str]


class SignalBatchView(BaseModel):
    event_id: int
    output_id: int
    model_version_id: int
    evaluation_run_id: int
    generated_at: datetime
    signals: list[ValueSignalView]
