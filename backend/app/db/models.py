from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class Sport(Base):
    __tablename__ = "sports"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(80))


class Competition(Base):
    __tablename__ = "competitions"
    id: Mapped[int] = mapped_column(primary_key=True)
    sport_id: Mapped[int] = mapped_column(ForeignKey("sports.id"))
    name: Mapped[str] = mapped_column(String(120))
    country: Mapped[str] = mapped_column(String(80))
    season: Mapped[str] = mapped_column(String(40))
    __table_args__ = (UniqueConstraint("sport_id", "name", "season"),)


class Team(Base):
    __tablename__ = "teams"
    id: Mapped[int] = mapped_column(primary_key=True)
    sport_id: Mapped[int] = mapped_column(ForeignKey("sports.id"))
    name: Mapped[str] = mapped_column(String(120))
    __table_args__ = (UniqueConstraint("sport_id", "name"),)


class Player(Base):
    __tablename__ = "players"
    id: Mapped[int] = mapped_column(primary_key=True)
    sport_id: Mapped[int] = mapped_column(ForeignKey("sports.id"))
    provider_id: Mapped[int] = mapped_column(ForeignKey("providers.id"))
    provider_player_key: Mapped[str] = mapped_column(String(120))
    name: Mapped[str] = mapped_column(String(160))
    position: Mapped[str] = mapped_column(String(40))
    preferred_side: Mapped[str | None] = mapped_column(String(20))
    birth_year: Mapped[int | None] = mapped_column(Integer)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (
        UniqueConstraint("provider_id", "provider_player_key"),
        Index("ix_players_name", "name"),
    )


class Coach(Base):
    __tablename__ = "coaches"
    id: Mapped[int] = mapped_column(primary_key=True)
    sport_id: Mapped[int] = mapped_column(ForeignKey("sports.id"))
    provider_id: Mapped[int] = mapped_column(ForeignKey("providers.id"))
    provider_coach_key: Mapped[str] = mapped_column(String(120))
    name: Mapped[str] = mapped_column(String(160))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (UniqueConstraint("provider_id", "provider_coach_key"),)


class Provider(Base):
    __tablename__ = "providers"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(30))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    terms_url: Mapped[str | None] = mapped_column(String(500))
    capabilities: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


class RawIngestion(Base, TimestampMixin):
    __tablename__ = "raw_ingestions"
    id: Mapped[int] = mapped_column(primary_key=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("providers.id"))
    import_job_id: Mapped[int | None] = mapped_column(ForeignKey("import_jobs.id"))
    source_key: Mapped[str] = mapped_column(String(255))
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    content_sha256: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, object] | list[object]] = mapped_column(JSON)
    schema_version: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(30), default="accepted")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (
        UniqueConstraint("provider_id", "source_key", "content_sha256"),
        CheckConstraint("ingested_at >= observed_at"),
    )


class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(primary_key=True)
    competition_id: Mapped[int] = mapped_column(ForeignKey("competitions.id"))
    home_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    away_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    provider_id: Mapped[int] = mapped_column(ForeignKey("providers.id"))
    provider_event_key: Mapped[str] = mapped_column(String(120))
    kickoff_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(30), default="scheduled")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (
        UniqueConstraint("provider_id", "provider_event_key"),
        CheckConstraint("home_team_id <> away_team_id"),
    )


class FixtureObservation(Base):
    __tablename__ = "fixture_observations"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    provider_id: Mapped[int] = mapped_column(ForeignKey("providers.id"))
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30))
    __table_args__ = (
        UniqueConstraint("event_id", "provider_id", "observed_at"),
        CheckConstraint("ingested_at >= observed_at"),
    )


class PlayerRegistration(Base):
    __tablename__ = "player_registrations"
    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    competition_id: Mapped[int | None] = mapped_column(ForeignKey("competitions.id"))
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    squad_number: Mapped[int | None] = mapped_column(Integer)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("player_id", "team_id", "valid_from"),
        CheckConstraint("valid_to IS NULL OR valid_to > valid_from"),
    )


class CoachTenure(Base):
    __tablename__ = "coach_tenures"
    id: Mapped[int] = mapped_column(primary_key=True)
    coach_id: Mapped[int] = mapped_column(ForeignKey("coaches.id"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("coach_id", "team_id", "valid_from"),
        CheckConstraint("valid_to IS NULL OR valid_to > valid_from"),
    )


class PlayerAppearance(Base):
    __tablename__ = "player_appearances"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    provider_id: Mapped[int] = mapped_column(ForeignKey("providers.id"))
    starter: Mapped[bool] = mapped_column(Boolean)
    minutes: Mapped[int] = mapped_column(Integer)
    position: Mapped[str] = mapped_column(String(40))
    role: Mapped[str | None] = mapped_column(String(80))
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("event_id", "player_id", "provider_id"),
        CheckConstraint("minutes >= 0 AND minutes <= 130"),
    )


class PlayerStatistic(Base):
    __tablename__ = "player_statistics"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    provider_id: Mapped[int] = mapped_column(ForeignKey("providers.id"))
    metric_schema_version: Mapped[str] = mapped_column(String(60))
    minutes: Mapped[int] = mapped_column(Integer)
    metrics: Mapped[dict[str, object]] = mapped_column(JSON)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint(
            "event_id",
            "player_id",
            "provider_id",
            "metric_schema_version",
        ),
        CheckConstraint("minutes >= 0 AND minutes <= 130"),
    )


class AvailabilityReport(Base):
    __tablename__ = "availability_reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id"))
    provider_id: Mapped[int] = mapped_column(ForeignKey("providers.id"))
    status: Mapped[str] = mapped_column(String(40))
    reason: Mapped[str | None] = mapped_column(String(255))
    evidence_class: Mapped[str] = mapped_column(String(30))
    confidence: Mapped[float] = mapped_column(Float)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    supersedes_id: Mapped[int | None] = mapped_column(ForeignKey("availability_reports.id"))
    __table_args__ = (
        CheckConstraint("confidence >= 0 AND confidence <= 1"),
        CheckConstraint("effective_to IS NULL OR effective_to > effective_from"),
    )


class LineupSnapshot(Base):
    __tablename__ = "lineup_snapshots"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    coach_id: Mapped[int | None] = mapped_column(ForeignKey("coaches.id"))
    provider_id: Mapped[int] = mapped_column(ForeignKey("providers.id"))
    lineup_type: Mapped[str] = mapped_column(String(30))
    formation: Mapped[str | None] = mapped_column(String(30))
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    confidence: Mapped[float] = mapped_column(Float)
    __table_args__ = (
        UniqueConstraint("event_id", "team_id", "lineup_type", "observed_at"),
        CheckConstraint("confidence >= 0 AND confidence <= 1"),
    )


class LineupMember(Base):
    __tablename__ = "lineup_members"
    id: Mapped[int] = mapped_column(primary_key=True)
    lineup_snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("lineup_snapshots.id", ondelete="CASCADE")
    )
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"))
    starter: Mapped[bool] = mapped_column(Boolean)
    position: Mapped[str] = mapped_column(String(40))
    role: Mapped[str | None] = mapped_column(String(80))
    expected_probability: Mapped[float | None] = mapped_column(Float)
    __table_args__ = (
        UniqueConstraint("lineup_snapshot_id", "player_id"),
        CheckConstraint(
            "expected_probability IS NULL OR "
            "(expected_probability >= 0 AND expected_probability <= 1)"
        ),
    )


class TacticalSnapshot(Base):
    __tablename__ = "tactical_snapshots"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    coach_id: Mapped[int | None] = mapped_column(ForeignKey("coaches.id"))
    provider_id: Mapped[int] = mapped_column(ForeignKey("providers.id"))
    formation: Mapped[str | None] = mapped_column(String(30))
    metrics: Mapped[dict[str, object]] = mapped_column(JSON)
    labels: Mapped[list[str]] = mapped_column(JSON, default=list)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MatchupFeatureSnapshot(Base):
    __tablename__ = "matchup_feature_snapshots"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    feature_version: Mapped[str] = mapped_column(String(60))
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    features: Mapped[dict[str, object]] = mapped_column(JSON)
    sensitivity: Mapped[dict[str, object]] = mapped_column(JSON)
    missing_inputs: Mapped[list[str]] = mapped_column(JSON, default=list)
    __table_args__ = (UniqueConstraint("event_id", "feature_version", "as_of"),)


class Bookmaker(Base):
    __tablename__ = "bookmakers"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class TaxProfile(Base, TimestampMixin):
    __tablename__ = "tax_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    jurisdiction: Mapped[str] = mapped_column(String(80))
    currency: Mapped[str] = mapped_column(String(3))
    tax_basis: Mapped[str] = mapped_column(String(30))
    stake_tax_rate: Mapped[Decimal] = mapped_column(Numeric(9, 6), default=0)
    winnings_tax_rate: Mapped[Decimal] = mapped_column(Numeric(9, 6), default=0)
    payout_withholding_rate: Mapped[Decimal] = mapped_column(Numeric(9, 6), default=0)
    commission_rate: Mapped[Decimal] = mapped_column(Numeric(9, 6), default=0)
    fixed_fee: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=0)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_url: Mapped[str | None] = mapped_column(String(500))
    source_label: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(30), default="verified")
    __table_args__ = (
        CheckConstraint(
            "stake_tax_rate >= 0 AND stake_tax_rate <= 1 "
            "AND winnings_tax_rate >= 0 AND winnings_tax_rate <= 1 "
            "AND payout_withholding_rate >= 0 AND payout_withholding_rate <= 1 "
            "AND commission_rate >= 0 AND commission_rate <= 1"
        ),
        CheckConstraint("fixed_fee >= 0"),
        CheckConstraint("effective_to IS NULL OR effective_to > effective_from"),
    )


class BookmakerTaxProfile(Base):
    __tablename__ = "bookmaker_tax_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    bookmaker_id: Mapped[int] = mapped_column(ForeignKey("bookmakers.id"))
    tax_profile_id: Mapped[int] = mapped_column(ForeignKey("tax_profiles.id"))
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("bookmaker_id", "tax_profile_id", "valid_from"),
        CheckConstraint("valid_to IS NULL OR valid_to > valid_from"),
    )


class BookmakerConstraint(Base):
    __tablename__ = "bookmaker_constraints"
    id: Mapped[int] = mapped_column(primary_key=True)
    bookmaker_id: Mapped[int] = mapped_column(ForeignKey("bookmakers.id"))
    currency: Mapped[str] = mapped_column(String(3))
    minimum_stake: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=0)
    maximum_stake: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    stake_increment: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=1)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_label: Mapped[str] = mapped_column(String(160))
    __table_args__ = (
        UniqueConstraint("bookmaker_id", "currency", "observed_at"),
        CheckConstraint("minimum_stake >= 0"),
        CheckConstraint("maximum_stake IS NULL OR maximum_stake > 0"),
        CheckConstraint("stake_increment > 0"),
    )


class Market(Base):
    __tablename__ = "markets"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    market_type: Mapped[str] = mapped_column(String(40))
    line: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    line_key: Mapped[str] = mapped_column(String(20), default="")
    period: Mapped[str] = mapped_column(String(30), default="FULL_TIME")
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    settlement_rule_key: Mapped[str] = mapped_column(String(80), default="standard_90_minutes")
    __table_args__ = (
        UniqueConstraint(
            "event_id",
            "market_type",
            "line_key",
            "period",
            "currency",
            "settlement_rule_key",
        ),
    )


class Selection(Base):
    __tablename__ = "selections"
    id: Mapped[int] = mapped_column(primary_key=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(120))
    __table_args__ = (UniqueConstraint("market_id", "code"),)


class ImportJob(Base, TimestampMixin):
    __tablename__ = "import_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(30))
    rows_received: Mapped[int] = mapped_column(Integer, default=0)
    rows_imported: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)


class OddsSnapshot(Base):
    __tablename__ = "odds_snapshots"
    id: Mapped[int] = mapped_column(primary_key=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id", ondelete="CASCADE"))
    bookmaker_id: Mapped[int] = mapped_column(ForeignKey("bookmakers.id"))
    provider_id: Mapped[int] = mapped_column(ForeignKey("providers.id"))
    import_job_id: Mapped[int | None] = mapped_column(ForeignKey("import_jobs.id"))
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_closing: Mapped[bool] = mapped_column(Boolean, default=False)
    is_complete: Mapped[bool] = mapped_column(Boolean, default=True)
    source_label: Mapped[str] = mapped_column(String(160))
    __table_args__ = (
        UniqueConstraint("market_id", "bookmaker_id", "provider_id", "observed_at"),
        CheckConstraint("ingested_at >= observed_at"),
    )


class OddsPrice(Base):
    __tablename__ = "odds_prices"
    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("odds_snapshots.id", ondelete="CASCADE"))
    selection_id: Mapped[int] = mapped_column(ForeignKey("selections.id"))
    decimal_odds: Mapped[Decimal] = mapped_column(Numeric(12, 5))
    __table_args__ = (
        UniqueConstraint("snapshot_id", "selection_id"),
        CheckConstraint("decimal_odds > 1"),
    )


class MatchResult(Base):
    __tablename__ = "match_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"))
    provider_id: Mapped[int] = mapped_column(ForeignKey("providers.id"))
    home_goals: Mapped[int] = mapped_column(Integer)
    away_goals: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="final")
    is_final: Mapped[bool] = mapped_column(Boolean, default=True)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    settled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    supersedes_id: Mapped[int | None] = mapped_column(ForeignKey("match_results.id"))
    __table_args__ = (
        UniqueConstraint("event_id", "provider_id", "observed_at"),
        CheckConstraint("home_goals >= 0 AND away_goals >= 0"),
        CheckConstraint("settled_at <= observed_at"),
    )


class TeamStatistic(Base):
    __tablename__ = "team_statistics"
    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    competition_id: Mapped[int] = mapped_column(ForeignKey("competitions.id"))
    provider_id: Mapped[int] = mapped_column(ForeignKey("providers.id"))
    metric_schema_version: Mapped[str] = mapped_column(String(60))
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    matches: Mapped[int] = mapped_column(Integer)
    goals_for: Mapped[float] = mapped_column(Float)
    goals_against: Mapped[float] = mapped_column(Float)
    metrics: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    __table_args__ = (
        UniqueConstraint(
            "team_id",
            "competition_id",
            "provider_id",
            "metric_schema_version",
            "as_of",
        ),
        CheckConstraint("matches >= 0"),
    )


class ModelVersion(Base, TimestampMixin):
    __tablename__ = "model_versions"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    version: Mapped[str] = mapped_column(String(40), unique=True)
    kind: Mapped[str] = mapped_column(String(60))
    training_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    training_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    data_fingerprint: Mapped[str] = mapped_column(String(64))
    feature_version: Mapped[str] = mapped_column(String(60))
    sample_size: Mapped[int] = mapped_column(Integer)
    evaluation_status: Mapped[str] = mapped_column(String(30), default="unvalidated")
    config: Mapped[dict[str, object]] = mapped_column(JSON)
    metrics: Mapped[dict[str, object]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (
        CheckConstraint("training_end > training_start"),
        CheckConstraint("sample_size > 0"),
    )


class ModelEventOutput(Base):
    __tablename__ = "model_event_outputs"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"))
    model_version_id: Mapped[int] = mapped_column(ForeignKey("model_versions.id"))
    lineup_snapshot_id: Mapped[int | None] = mapped_column(ForeignKey("lineup_snapshots.id"))
    matchup_feature_snapshot_id: Mapped[int | None] = mapped_column(
        ForeignKey("matchup_feature_snapshots.id")
    )
    predicted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    inputs_as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    evidence_class: Mapped[str] = mapped_column(String(30), default="team_baseline")
    home_lambda: Mapped[float] = mapped_column(Float)
    away_lambda: Mapped[float] = mapped_column(Float)
    score_matrix: Mapped[list[list[float]]] = mapped_column(JSON)
    sample_size: Mapped[int] = mapped_column(Integer)
    __table_args__ = (
        UniqueConstraint("event_id", "model_version_id", "predicted_at"),
        CheckConstraint("inputs_as_of <= predicted_at"),
        CheckConstraint("home_lambda > 0 AND away_lambda > 0"),
        CheckConstraint("sample_size > 0"),
    )


class ModelPrediction(Base):
    __tablename__ = "model_predictions"
    id: Mapped[int] = mapped_column(primary_key=True)
    output_id: Mapped[int] = mapped_column(ForeignKey("model_event_outputs.id", ondelete="CASCADE"))
    selection_id: Mapped[int] = mapped_column(ForeignKey("selections.id"))
    probability: Mapped[float] = mapped_column(Float)
    lower_probability: Mapped[float] = mapped_column(Float)
    upper_probability: Mapped[float] = mapped_column(Float)
    fair_odds: Mapped[float] = mapped_column(Float)
    __table_args__ = (
        UniqueConstraint("output_id", "selection_id"),
        CheckConstraint(
            "probability >= 0 AND probability <= 1 "
            "AND lower_probability >= 0 AND lower_probability <= probability "
            "AND upper_probability >= probability AND upper_probability <= 1"
        ),
        CheckConstraint("fair_odds >= 1"),
    )


class ValueSignal(Base):
    __tablename__ = "value_signals"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"))
    selection_id: Mapped[int] = mapped_column(ForeignKey("selections.id"))
    bookmaker_id: Mapped[int] = mapped_column(ForeignKey("bookmakers.id"))
    odds_snapshot_id: Mapped[int] = mapped_column(ForeignKey("odds_snapshots.id"))
    prediction_id: Mapped[int] = mapped_column(ForeignKey("model_predictions.id"))
    evaluation_run_id: Mapped[int | None] = mapped_column(ForeignKey("backtest_runs.id"))
    signal_type: Mapped[str] = mapped_column(String(40))
    offered_odds: Mapped[float] = mapped_column(Float)
    raw_implied_probability: Mapped[float] = mapped_column(Float)
    market_fair_probability: Mapped[float] = mapped_column(Float)
    model_probability: Mapped[float] = mapped_column(Float)
    expected_value: Mapped[float] = mapped_column(Float)
    lower_expected_value: Mapped[float] = mapped_column(Float)
    probability_edge: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    calibration_error: Mapped[float] = mapped_column(Float)
    odds_age_minutes: Mapped[float] = mapped_column(Float)
    bookmaker_count: Mapped[int] = mapped_column(Integer)
    odds_move_ratio: Mapped[float] = mapped_column(Float, default=0)
    implied_move_points: Mapped[float] = mapped_column(Float, default=0)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    reasons: Mapped[list[str]] = mapped_column(JSON)
    risks: Mapped[list[str]] = mapped_column(JSON)
    __table_args__ = (
        UniqueConstraint("odds_snapshot_id", "prediction_id", "generated_at"),
        CheckConstraint("offered_odds > 1"),
        CheckConstraint(
            "raw_implied_probability > 0 AND raw_implied_probability < 1 "
            "AND market_fair_probability > 0 AND market_fair_probability < 1 "
            "AND model_probability >= 0 AND model_probability <= 1 "
            "AND confidence >= 0 AND confidence <= 1"
        ),
        CheckConstraint("calibration_error >= 0 AND odds_age_minutes >= 0"),
        CheckConstraint("bookmaker_count > 0"),
    )


class ArbitrageOpportunity(Base):
    __tablename__ = "arbitrage_opportunities"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"))
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id"))
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    fingerprint: Mapped[str | None] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(40))
    inverse_sum: Mapped[float] = mapped_column(Float)
    total_cash_outlay: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    minimum_net_payout: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    net_profit: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    net_roi: Mapped[float] = mapped_column(Float)
    tax_status: Mapped[str] = mapped_column(String(30))
    constraint_status: Mapped[str] = mapped_column(String(30))
    freshness_status: Mapped[str] = mapped_column(String(30))
    currency: Mapped[str] = mapped_column(String(3))
    budget: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    risks: Mapped[list[str]] = mapped_column(JSON, default=list)
    __table_args__ = (
        CheckConstraint("inverse_sum > 0"),
        CheckConstraint("total_cash_outlay > 0"),
        CheckConstraint("budget > 0"),
    )


class ArbitrageLeg(Base):
    __tablename__ = "arbitrage_legs"
    id: Mapped[int] = mapped_column(primary_key=True)
    opportunity_id: Mapped[int] = mapped_column(
        ForeignKey("arbitrage_opportunities.id", ondelete="CASCADE")
    )
    selection_id: Mapped[int] = mapped_column(ForeignKey("selections.id"))
    bookmaker_id: Mapped[int] = mapped_column(ForeignKey("bookmakers.id"))
    odds_snapshot_id: Mapped[int] = mapped_column(ForeignKey("odds_snapshots.id"))
    tax_profile_id: Mapped[int | None] = mapped_column(ForeignKey("tax_profiles.id"))
    bookmaker_constraint_id: Mapped[int | None] = mapped_column(
        ForeignKey("bookmaker_constraints.id")
    )
    decimal_odds: Mapped[Decimal] = mapped_column(Numeric(12, 5))
    stake: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    cash_outlay: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    gross_payout: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    win_deductions: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    taxes_and_fees: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    net_payout: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    __table_args__ = (
        UniqueConstraint("opportunity_id", "selection_id"),
        CheckConstraint("decimal_odds > 1"),
        CheckConstraint("stake > 0"),
        CheckConstraint("cash_outlay >= stake"),
        CheckConstraint("win_deductions >= 0"),
        CheckConstraint("taxes_and_fees >= 0"),
    )


class BetBuilderQuote(Base, TimestampMixin):
    __tablename__ = "bet_builder_quotes"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"))
    model_version_id: Mapped[int] = mapped_column(ForeignKey("model_versions.id"))
    prediction_output_id: Mapped[int | None] = mapped_column(
        ForeignKey("model_event_outputs.id", ondelete="CASCADE")
    )
    fingerprint: Mapped[str | None] = mapped_column(String(64), unique=True)
    feature_version: Mapped[str | None] = mapped_column(String(80))
    input_fingerprint: Mapped[str | None] = mapped_column(String(64))
    legs: Mapped[list[dict[str, object]]] = mapped_column(JSON)
    joint_probability: Mapped[float] = mapped_column(Float)
    lower_joint_probability: Mapped[float | None] = mapped_column(Float)
    upper_joint_probability: Mapped[float | None] = mapped_column(Float)
    independent_product: Mapped[float | None] = mapped_column(Float)
    dependence_ratio: Mapped[float | None] = mapped_column(Float)
    fair_odds: Mapped[float] = mapped_column(Float)
    offered_odds: Mapped[float | None] = mapped_column(Float)
    offered_odds_source: Mapped[str | None] = mapped_column(String(120))
    offered_odds_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expected_value: Mapped[float | None] = mapped_column(Float)
    lower_expected_value: Mapped[float | None] = mapped_column(Float)
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list)
    __table_args__ = (
        CheckConstraint("joint_probability >= 0 AND joint_probability <= 1"),
        CheckConstraint(
            "lower_joint_probability IS NULL OR "
            "(lower_joint_probability >= 0 AND lower_joint_probability <= joint_probability)"
        ),
        CheckConstraint(
            "upper_joint_probability IS NULL OR "
            "(upper_joint_probability >= joint_probability AND upper_joint_probability <= 1)"
        ),
        CheckConstraint("fair_odds >= 1"),
        CheckConstraint("offered_odds IS NULL OR offered_odds > 1"),
    )


class BacktestRun(Base, TimestampMixin):
    __tablename__ = "backtest_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    model_version_id: Mapped[int] = mapped_column(ForeignKey("model_versions.id"))
    status: Mapped[str] = mapped_column(String(30))
    train_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    validation_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    test_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fingerprint: Mapped[str | None] = mapped_column(String(64), unique=True)
    config: Mapped[dict[str, object]] = mapped_column(JSON)
    policy: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    evaluation_status: Mapped[str] = mapped_column(String(30), default="unvalidated")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (
        CheckConstraint("validation_end >= train_end"),
        CheckConstraint("test_end >= validation_end"),
    )


class BacktestResult(Base):
    __tablename__ = "backtest_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("backtest_runs.id", ondelete="CASCADE"))
    benchmark: Mapped[str] = mapped_column(String(80))
    dimension: Mapped[str] = mapped_column(String(60), default="overall")
    dimension_value: Mapped[str] = mapped_column(String(120), default="all")
    metrics: Mapped[dict[str, object]] = mapped_column(JSON)
    __table_args__ = (UniqueConstraint("run_id", "benchmark", "dimension", "dimension_value"),)


class BacktestObservation(Base):
    __tablename__ = "backtest_observations"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("backtest_runs.id", ondelete="CASCADE"))
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"))
    selection_id: Mapped[int | None] = mapped_column(ForeignKey("selections.id"))
    odds_snapshot_id: Mapped[int | None] = mapped_column(ForeignKey("odds_snapshots.id"))
    prediction_id: Mapped[int | None] = mapped_column(ForeignKey("model_predictions.id"))
    result_id: Mapped[int | None] = mapped_column(ForeignKey("match_results.id"))
    predicted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    training_cutoff: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    training_sample_size: Mapped[int | None] = mapped_column(Integer)
    training_fingerprint: Mapped[str | None] = mapped_column(String(64))
    market_type: Mapped[str | None] = mapped_column(String(40))
    probabilities: Mapped[dict[str, float] | None] = mapped_column(JSON)
    actual_outcome: Mapped[str | None] = mapped_column(String(40))
    brier_score: Mapped[float | None] = mapped_column(Float)
    log_loss: Mapped[float | None] = mapped_column(Float)
    market_snapshot_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    market_probabilities: Mapped[dict[str, float] | None] = mapped_column(JSON)
    market_brier_score: Mapped[float | None] = mapped_column(Float)
    market_log_loss: Mapped[float | None] = mapped_column(Float)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    settlement: Mapped[str | None] = mapped_column(String(20))
    stake: Mapped[float] = mapped_column(Float, default=1.0)
    profit_units: Mapped[float | None] = mapped_column(Float)
    closing_line_value: Mapped[float | None] = mapped_column(Float)
    __table_args__ = (
        UniqueConstraint("run_id", "event_id", "selection_id", "predicted_at"),
        CheckConstraint("stake >= 0"),
        CheckConstraint("training_sample_size IS NULL OR training_sample_size > 0"),
        CheckConstraint("training_cutoff IS NULL OR training_cutoff <= predicted_at"),
        CheckConstraint("brier_score IS NULL OR brier_score >= 0"),
        CheckConstraint("log_loss IS NULL OR log_loss >= 0"),
    )


class ProviderJob(Base, TimestampMixin):
    __tablename__ = "provider_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("providers.id"))
    job_type: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(30))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    message: Mapped[str] = mapped_column(Text, default="")
