from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RunSignalBacktestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_version_id: int = Field(gt=0)
    evaluation_start: datetime
    evaluation_end: datetime
    signal_types: list[str] = Field(default_factory=lambda: ["VALUE"], min_length=1)

    @field_validator("evaluation_start", "evaluation_end")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a UTC offset")
        return value

    @field_validator("signal_types")
    @classmethod
    def supported_signal_types(cls, values: list[str]) -> list[str]:
        normalized = sorted({value.upper() for value in values})
        if any(value not in {"VALUE", "WATCH", "PASS"} for value in normalized):
            raise ValueError("unsupported signal type")
        return normalized

    @model_validator(mode="after")
    def validate_window(self) -> RunSignalBacktestRequest:
        if self.evaluation_end <= self.evaluation_start:
            raise ValueError("evaluation_end must be after evaluation_start")
        return self


class SignalBacktestObservationView(BaseModel):
    id: int
    event_id: int
    selection_id: int
    prediction_id: int
    odds_snapshot_id: int
    predicted_at: datetime
    settled_at: datetime
    market_type: str
    selection_code: str
    decimal_odds: float
    model_probability: float
    lower_probability: float
    expected_value: float
    settlement: str
    stake: float
    profit_units: float
    closing_odds_snapshot_id: int | None
    closing_decimal_odds: float | None
    closing_observed_at: datetime | None
    closing_line_value: float | None


class SignalBacktestView(BaseModel):
    id: int
    model_version_id: int
    model_version: str
    status: str
    evaluation_start: datetime
    evaluation_end: datetime
    fingerprint: str
    evaluation_status: str
    is_demo: bool
    config: dict[str, object]
    policy: dict[str, object]
    metrics: dict[str, object]
    observations: list[SignalBacktestObservationView]
    created_at: datetime


class SimulateBankrollRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    backtest_run_id: int = Field(gt=0)
    strategy: Literal["flat", "percentage", "fractional_kelly"] = "flat"
    initial_bankroll: float = Field(default=1000, gt=0)
    flat_stake: float = Field(default=10, gt=0)
    stake_fraction: float = Field(default=0.01, gt=0, le=1)
    kelly_fraction: float = Field(default=0.25, gt=0, le=1)
    maximum_stake_fraction: float = Field(default=0.02, gt=0, le=1)
    maximum_daily_exposure_fraction: float = Field(default=0.05, gt=0, le=1)


class BankrollPointView(BaseModel):
    observation_id: int
    bankroll: float
    stake: float
    profit: float
    drawdown: float


class BankrollSimulationView(BaseModel):
    backtest_run_id: int
    backtest_fingerprint: str
    simulation_fingerprint: str
    strategy: str
    initial_bankroll: float
    final_bankroll: float
    total_staked: float
    net_profit: float
    roi: float
    maximum_drawdown: float
    maximum_drawdown_fraction: float
    bets_placed: int
    bets_skipped: int
    is_demo: bool
    warnings: list[str]
    points: list[BankrollPointView]
