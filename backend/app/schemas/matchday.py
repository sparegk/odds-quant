from __future__ import annotations

from datetime import date as CalendarDate
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.api import EventSummary, MarketComparison
from app.schemas.builder import BetBuilderLegView, BetBuilderQuoteView
from app.schemas.lineups import ExpectedLineupScenarioView, StoredLineupView
from app.schemas.models import ModelOutputView
from app.schemas.signals import ValueSignalView


class MatchdayEventView(BaseModel):
    event: EventSummary
    market_count: int
    bookmaker_count: int
    latest_prediction_at: datetime | None
    qualified_signal_count: int


class MatchdayCompetitionView(BaseModel):
    competition_id: int
    name: str
    country: str
    season: str
    group_key: str
    group_label: str
    priority: int
    is_featured: bool
    events: list[MatchdayEventView]


class MatchdayView(BaseModel):
    date: CalendarDate
    timezone: str
    local_start: datetime
    local_end: datetime
    as_of: datetime
    total_events: int
    previous_event_date: CalendarDate | None
    next_event_date: CalendarDate | None
    competitions: list[MatchdayCompetitionView]
    data_note: str


class RecentTeamResultView(BaseModel):
    event_id: int
    kickoff_at: datetime
    opponent: str
    venue: str
    goals_for: int
    goals_against: int
    outcome: str
    observed_at: datetime


class TeamFormView(BaseModel):
    team_id: int
    team: str
    sample_size: int
    wins: int
    draws: int
    losses: int
    goals_for: int
    goals_against: int
    clean_sheets: int
    points_per_game: float | None
    results: list[RecentTeamResultView]
    warnings: list[str]


class ResearchGateView(BaseModel):
    status: str
    title: str
    available_records: int
    reasons: list[str]


class MatchSuggestionView(BaseModel):
    rank: int
    source_kind: Literal["single", "builder"]
    source_id: int
    bookmaker_code: Literal["allwyn", "novibet"]
    bookmaker: str
    market_type: str
    selection_code: str
    selection_name: str
    line: float | None
    legs: list[BetBuilderLegView]
    offered_odds: float
    model_probability: float
    lower_probability: float
    market_fair_probability: float | None
    expected_value: float
    lower_expected_value: float
    net_expected_value: float
    lower_net_expected_value: float
    cost_calculation_stake: float
    cost_calculation_cash_outlay: float
    cost_currency: str
    confidence: float | None
    conservative_score: float
    price_observed_at: datetime
    generated_at: datetime
    reasons: list[str]
    risks: list[str]


class MatchdayBookmakerOptionView(BaseModel):
    code: Literal["allwyn", "novibet"]
    name: str
    selected: bool
    has_current_prices: bool
    offered_market_types: list[str]


class SuggestionMarketStatusView(BaseModel):
    code: str
    label: str
    status: Literal["available", "price_only", "blocked"]
    reason: str


class AvailabilityAuditItemView(BaseModel):
    code: str
    label: str
    status: Literal["available", "partial", "blocked"]
    present_records: int
    research_only: bool
    evidence: list[str]
    blockers: list[str]
    unlock_requirements: list[str]


class ModelMarketComparisonView(BaseModel):
    market_id: int
    market_type: str
    line: float | None
    selection_id: int
    selection_code: str
    selection_name: str
    bookmaker_count: int
    best_bookmaker: str
    best_odds: float
    best_price_observed_at: datetime
    best_price_age_seconds: int
    model_probability: float
    lower_probability: float
    upper_probability: float
    model_fair_odds: float
    market_consensus_probability: float
    market_probability_low: float
    market_probability_high: float
    devig_method_spread: float
    bookmaker_disagreement: float
    best_price_break_even_probability: float
    probability_edge: float
    conservative_edge: float
    price_probability_edge: float
    conservative_price_edge: float
    expected_value: float
    lower_expected_value: float
    lower_fair_odds: float | None
    model_uncertainty_width: float
    market_uncertainty_width: float
    pre_cost_advantage_survives_uncertainty: bool
    cost_adjusted_expected_value: float | None
    lower_cost_adjusted_expected_value: float | None
    cost_adjusted_expected_profit: float | None
    lower_cost_adjusted_expected_profit: float | None
    cost_calculation_stake: float | None
    cost_calculation_cash_outlay: float | None
    cost_currency: str
    settlement_rule_key: str
    tax_profile_id: int | None
    tax_profile_verified_at: datetime | None
    constraint_observed_at: datetime | None
    cost_adjusted_advantage_survives_uncertainty: bool | None
    cost_evidence_blockers: list[str]
    devig_sensitivity: list[DevigSensitivityView]
    devig_conclusion_stable: bool
    research_only: Literal[True] = True
    qualification_blockers: list[str]


class DevigSensitivityView(BaseModel):
    method: Literal["proportional", "power"]
    market_consensus_probability: float
    market_probability_low: float
    market_probability_high: float
    model_probability_edge: float
    conservative_probability_edge: float
    edge_positive: bool
    conservative_edge_positive: bool
    pre_registered: Literal[True] = True
    frozen_replay_primary: bool


class CalibrationReliabilityView(BaseModel):
    status: Literal["available", "blocked"]
    calibration_method: str
    calibration_version: str
    calibration_applied: bool
    temperature: float | None
    sample_size: int
    fit_through: datetime | None
    evaluation_run_id: int | None
    prediction_inputs_as_of: datetime | None
    evaluation_test_end: datetime | None
    evaluation_fingerprint: str | None
    probability_evaluation_status: str | None
    expected_calibration_error: float | None
    brier_score: float | None
    log_loss: float | None
    chronological_out_of_sample: bool
    market_edge_evidence_included: Literal[False] = False
    return_evidence_included: Literal[False] = False
    blockers: list[str]


class MatchdayEventDetailView(BaseModel):
    event: EventSummary
    competition_group: str
    competition_group_label: str
    as_of: datetime
    team_form: list[TeamFormView]
    markets: list[MarketComparison]
    latest_prediction: ModelOutputView | None
    model_market_comparisons: list[ModelMarketComparisonView]
    calibration_reliability: CalibrationReliabilityView
    signals: list[ValueSignalView]
    builder_quotes: list[BetBuilderQuoteView]
    suggestions: list[MatchSuggestionView]
    selected_bookmakers: list[Literal["allwyn", "novibet"]]
    bookmaker_options: list[MatchdayBookmakerOptionView]
    suggestion_market_statuses: list[SuggestionMarketStatusView]
    availability_audit: list[AvailabilityAuditItemView]
    stored_lineups: list[StoredLineupView]
    lineup_projections: list[ExpectedLineupScenarioView]
    lineup_research: ResearchGateView
    player_research: ResearchGateView
    builder_value: ResearchGateView
    bookmaker_guidance: str
    evidence_note: str
