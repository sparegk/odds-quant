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


class Provider(Base):
    __tablename__ = "providers"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(30))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    terms_url: Mapped[str | None] = mapped_column(String(500))
    capabilities: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


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


class Bookmaker(Base):
    __tablename__ = "bookmakers"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class Market(Base):
    __tablename__ = "markets"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    market_type: Mapped[str] = mapped_column(String(40))
    line: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    __table_args__ = (UniqueConstraint("event_id", "market_type", "line"),)


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
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_closing: Mapped[bool] = mapped_column(Boolean, default=False)
    is_complete: Mapped[bool] = mapped_column(Boolean, default=True)
    source_label: Mapped[str] = mapped_column(String(160))
    __table_args__ = (
        UniqueConstraint("market_id", "bookmaker_id", "provider_id", "captured_at"),
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
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), primary_key=True)
    home_goals: Mapped[int] = mapped_column(Integer)
    away_goals: Mapped[int] = mapped_column(Integer)
    settled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TeamStatistic(Base):
    __tablename__ = "team_statistics"
    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    competition_id: Mapped[int] = mapped_column(ForeignKey("competitions.id"))
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    matches: Mapped[int] = mapped_column(Integer)
    goals_for: Mapped[float] = mapped_column(Float)
    goals_against: Mapped[float] = mapped_column(Float)


class ModelVersion(Base, TimestampMixin):
    __tablename__ = "model_versions"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    version: Mapped[str] = mapped_column(String(40), unique=True)
    kind: Mapped[str] = mapped_column(String(60))
    training_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    training_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    config: Mapped[dict[str, object]] = mapped_column(JSON)
    metrics: Mapped[dict[str, object]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class ModelEventOutput(Base):
    __tablename__ = "model_event_outputs"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"))
    model_version_id: Mapped[int] = mapped_column(ForeignKey("model_versions.id"))
    predicted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    inputs_as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    home_lambda: Mapped[float] = mapped_column(Float)
    away_lambda: Mapped[float] = mapped_column(Float)
    score_matrix: Mapped[list[list[float]]] = mapped_column(JSON)
    sample_size: Mapped[int] = mapped_column(Integer)
    __table_args__ = (UniqueConstraint("event_id", "model_version_id", "predicted_at"),)


class ModelPrediction(Base):
    __tablename__ = "model_predictions"
    id: Mapped[int] = mapped_column(primary_key=True)
    output_id: Mapped[int] = mapped_column(ForeignKey("model_event_outputs.id", ondelete="CASCADE"))
    selection_id: Mapped[int] = mapped_column(ForeignKey("selections.id"))
    probability: Mapped[float] = mapped_column(Float)
    lower_probability: Mapped[float] = mapped_column(Float)
    upper_probability: Mapped[float] = mapped_column(Float)
    fair_odds: Mapped[float] = mapped_column(Float)
    __table_args__ = (UniqueConstraint("output_id", "selection_id"),)


class ValueSignal(Base):
    __tablename__ = "value_signals"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"))
    selection_id: Mapped[int] = mapped_column(ForeignKey("selections.id"))
    bookmaker_id: Mapped[int] = mapped_column(ForeignKey("bookmakers.id"))
    odds_snapshot_id: Mapped[int] = mapped_column(ForeignKey("odds_snapshots.id"))
    prediction_id: Mapped[int] = mapped_column(ForeignKey("model_predictions.id"))
    signal_type: Mapped[str] = mapped_column(String(40))
    offered_odds: Mapped[float] = mapped_column(Float)
    raw_implied_probability: Mapped[float] = mapped_column(Float)
    market_fair_probability: Mapped[float] = mapped_column(Float)
    model_probability: Mapped[float] = mapped_column(Float)
    expected_value: Mapped[float] = mapped_column(Float)
    probability_edge: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    reasons: Mapped[list[str]] = mapped_column(JSON)
    risks: Mapped[list[str]] = mapped_column(JSON)


class BetBuilderQuote(Base, TimestampMixin):
    __tablename__ = "bet_builder_quotes"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"))
    model_version_id: Mapped[int] = mapped_column(ForeignKey("model_versions.id"))
    legs: Mapped[list[dict[str, object]]] = mapped_column(JSON)
    joint_probability: Mapped[float] = mapped_column(Float)
    fair_odds: Mapped[float] = mapped_column(Float)
    offered_odds: Mapped[float | None] = mapped_column(Float)
    expected_value: Mapped[float | None] = mapped_column(Float)


class BacktestRun(Base, TimestampMixin):
    __tablename__ = "backtest_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    model_version_id: Mapped[int] = mapped_column(ForeignKey("model_versions.id"))
    status: Mapped[str] = mapped_column(String(30))
    train_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    validation_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    test_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    config: Mapped[dict[str, object]] = mapped_column(JSON)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class BacktestResult(Base):
    __tablename__ = "backtest_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("backtest_runs.id", ondelete="CASCADE"))
    benchmark: Mapped[str] = mapped_column(String(80))
    dimension: Mapped[str] = mapped_column(String(60), default="overall")
    dimension_value: Mapped[str] = mapped_column(String(120), default="all")
    metrics: Mapped[dict[str, object]] = mapped_column(JSON)
    __table_args__ = (UniqueConstraint("run_id", "benchmark", "dimension", "dimension_value"),)


class ProviderJob(Base, TimestampMixin):
    __tablename__ = "provider_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("providers.id"))
    job_type: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(30))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    message: Mapped[str] = mapped_column(Text, default="")
