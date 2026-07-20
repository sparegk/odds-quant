from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CalculateArbitrageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: int = Field(gt=0)
    budget: Decimal = Field(gt=0, max_digits=14, decimal_places=4)
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    calculated_at: datetime | None = None
    odds_stale_after_seconds: int = Field(default=300, ge=1, le=86_400)
    tax_max_age_days: int = Field(default=365, ge=1, le=3_650)
    constraint_max_age_minutes: int = Field(default=1_440, ge=1, le=525_600)

    @field_validator("calculated_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("timestamp must include a UTC offset")
        return value

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, value: str) -> str:
        return value.upper()


class ArbitrageLegView(BaseModel):
    id: int
    selection_id: int
    selection_code: str
    selection_name: str
    bookmaker_id: int
    bookmaker: str
    odds_snapshot_id: int
    tax_profile_id: int | None
    bookmaker_constraint_id: int | None
    decimal_odds: Decimal
    stake: Decimal
    cash_outlay: Decimal
    gross_payout: Decimal
    win_deductions: Decimal
    taxes_and_fees: Decimal
    net_payout: Decimal


class ArbitrageOpportunityView(BaseModel):
    id: int
    event_id: int
    market_id: int
    market_type: str
    line: float | None
    period: str
    settlement_rule_key: str
    calculated_at: datetime
    fingerprint: str
    status: str
    inverse_sum: float
    budget: Decimal
    total_cash_outlay: Decimal
    minimum_net_payout: Decimal
    net_profit: Decimal
    net_roi: float
    tax_status: str
    constraint_status: str
    freshness_status: str
    currency: str
    risks: list[str]
    legs: list[ArbitrageLegView]


class ArbitrageBatchView(BaseModel):
    event_id: int
    calculated_at: datetime
    opportunities: list[ArbitrageOpportunityView]
