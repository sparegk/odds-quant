from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class TrainPoissonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    competition_id: int = Field(gt=0)
    training_start: datetime
    training_end: datetime
    minimum_matches: int = Field(default=20, ge=6, le=100_000)
    minimum_team_matches: int = Field(default=3, ge=1, le=100)
    shrinkage_matches: float = Field(default=5.0, ge=0, le=100)

    @field_validator("training_start", "training_end")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a UTC offset")
        return value

    @model_validator(mode="after")
    def validate_window(self) -> TrainPoissonRequest:
        if self.training_end <= self.training_start:
            raise ValueError("training_end must be after training_start")
        return self


class PredictEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: int = Field(gt=0)
    predicted_at: datetime | None = None
    inputs_as_of: datetime | None = None

    @field_validator("predicted_at", "inputs_as_of")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("timestamp must include a UTC offset")
        return value


class ModelVersionView(BaseModel):
    id: int
    name: str
    version: str
    kind: str
    training_start: datetime
    training_end: datetime
    data_fingerprint: str
    feature_version: str
    sample_size: int
    evaluation_status: str
    config: dict[str, object]
    metrics: dict[str, object]
    status: str
    is_demo: bool
    created_at: datetime


class SelectionPredictionView(BaseModel):
    id: int
    market_id: int
    market_type: str
    line: float | None
    selection_id: int
    selection_code: str
    selection_name: str
    probability: float
    lower_probability: float
    upper_probability: float
    fair_odds: float


class ModelOutputView(BaseModel):
    id: int
    event_id: int
    model_version_id: int
    model_version: str
    predicted_at: datetime
    inputs_as_of: datetime
    evidence_class: str
    home_lambda: float
    away_lambda: float
    sample_size: int
    score_matrix: list[list[float]]
    derived_probabilities: dict[str, dict[str, float]]
    predictions: list[SelectionPredictionView]
