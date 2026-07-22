from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EventSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider_event_key: str
    competition_id: int
    competition: str
    country: str
    season: str
    home_team: str
    away_team: str
    kickoff_at: datetime
    status: str
    is_demo: bool
    latest_odds_at: datetime | None


class ProviderSummary(BaseModel):
    id: int
    slug: str
    name: str
    kind: str
    is_demo: bool
    terms_url: str | None
    capabilities: dict[str, object]
    event_count: int
    snapshot_count: int


class ImportJobView(BaseModel):
    id: int
    filename: str
    status: str
    rows_received: int
    rows_imported: int
    errors: list[dict[str, object]]
    created_at: datetime


class ProviderJobView(BaseModel):
    id: int
    provider_id: int
    provider: str
    job_type: str
    status: str
    message: str
    created_at: datetime
    finished_at: datetime | None


class PriceComparison(BaseModel):
    selection_code: str
    selection_name: str
    decimal_odds: float
    raw_implied_probability: float
    proportional_fair_probability: float
    proportional_fair_odds: float
    power_fair_probability: float
    power_fair_odds: float


class SnapshotComparison(BaseModel):
    snapshot_id: int
    bookmaker_id: int
    bookmaker: str
    provider: str
    observed_at: datetime
    source_updated_at: datetime | None
    is_closing: bool
    is_demo: bool
    source_label: str
    freshness_seconds: int
    is_stale: bool
    overround: float
    bookmaker_margin: float
    prices: list[PriceComparison]


class BestPrice(BaseModel):
    selection_code: str
    selection_name: str
    bookmaker: str
    decimal_odds: float
    observed_at: datetime
    freshness_seconds: int


class MarketComparison(BaseModel):
    market_id: int
    market_type: str
    line: float | None
    period: str
    currency: str
    settlement_rule_key: str
    snapshots: list[SnapshotComparison]
    best_prices: list[BestPrice]


class EventDetail(BaseModel):
    event: EventSummary
    markets: list[MarketComparison]


class ProblemDetail(BaseModel):
    type: str = "about:blank"
    title: str
    status: int
    detail: str | None = None
    errors: list[dict[str, object]] = Field(default_factory=list)
    import_job_id: int | None = None
