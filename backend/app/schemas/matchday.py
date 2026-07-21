from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel

from app.schemas.api import EventSummary, MarketComparison
from app.schemas.builder import BetBuilderQuoteView
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
    date: date
    timezone: str
    local_start: datetime
    local_end: datetime
    as_of: datetime
    total_events: int
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


class MatchdayEventDetailView(BaseModel):
    event: EventSummary
    competition_group: str
    competition_group_label: str
    as_of: datetime
    team_form: list[TeamFormView]
    markets: list[MarketComparison]
    latest_prediction: ModelOutputView | None
    signals: list[ValueSignalView]
    builder_quotes: list[BetBuilderQuoteView]
    player_research: ResearchGateView
    builder_value: ResearchGateView
    bookmaker_guidance: str
    evidence_note: str
