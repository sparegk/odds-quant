from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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


class CreateTaxProfileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    bookmaker_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=120)
    jurisdiction: str = Field(min_length=1, max_length=80)
    currency: str = Field(min_length=3, max_length=3)
    tax_basis: str = Field(default="per_bet", min_length=1, max_length=30)
    stake_tax_rate: Decimal = Field(default=Decimal("0"), ge=0, le=1)
    winnings_tax_rate: Decimal = Field(default=Decimal("0"), ge=0, le=1)
    payout_withholding_rate: Decimal = Field(default=Decimal("0"), ge=0, le=1)
    commission_rate: Decimal = Field(default=Decimal("0"), ge=0, le=1)
    fixed_fee: Decimal = Field(default=Decimal("0"), ge=0)
    effective_from: datetime
    effective_to: datetime | None = None
    verified_at: datetime
    source_url: str | None = Field(default=None, max_length=500)
    source_label: str = Field(min_length=1, max_length=160)

    @field_validator("effective_from", "effective_to", "verified_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("timestamp must include a UTC offset")
        return value

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, value: str) -> str:
        return value.upper()

    @model_validator(mode="after")
    def validate_period(self) -> CreateTaxProfileRequest:
        if self.effective_to is not None and self.effective_to <= self.effective_from:
            raise ValueError("effective_to must be after effective_from")
        return self


class CreateBookmakerConstraintRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    bookmaker_id: int = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    minimum_stake: Decimal = Field(default=Decimal("0"), ge=0)
    maximum_stake: Decimal | None = Field(default=None, gt=0)
    stake_increment: Decimal = Field(default=Decimal("1"), gt=0)
    observed_at: datetime
    source_label: str = Field(min_length=1, max_length=160)

    @field_validator("observed_at")
    @classmethod
    def require_observed_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a UTC offset")
        return value

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()

    @model_validator(mode="after")
    def validate_limits(self) -> CreateBookmakerConstraintRequest:
        if self.maximum_stake is not None and self.maximum_stake < self.minimum_stake:
            raise ValueError("maximum_stake cannot be below minimum_stake")
        return self


class BookmakerSettingsView(BaseModel):
    id: int
    slug: str
    name: str
    is_demo: bool


class TaxProfileView(BaseModel):
    id: int
    bookmaker_id: int
    bookmaker: str
    name: str
    jurisdiction: str
    currency: str
    stake_tax_rate: Decimal
    winnings_tax_rate: Decimal
    payout_withholding_rate: Decimal
    commission_rate: Decimal
    fixed_fee: Decimal
    effective_from: datetime
    effective_to: datetime | None
    verified_at: datetime
    source_url: str | None
    source_label: str
    status: str


class BookmakerConstraintView(BaseModel):
    id: int
    bookmaker_id: int
    bookmaker: str
    currency: str
    minimum_stake: Decimal
    maximum_stake: Decimal | None
    stake_increment: Decimal
    observed_at: datetime
    source_label: str


class ArbitrageSettingsView(BaseModel):
    bookmakers: list[BookmakerSettingsView]
    tax_profiles: list[TaxProfileView]
    constraints: list[BookmakerConstraintView]
