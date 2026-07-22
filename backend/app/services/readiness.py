from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    AvailabilityReport,
    BacktestObservation,
    BacktestRun,
    BookmakerConstraint,
    BookmakerTaxProfile,
    Event,
    LineupSnapshot,
    MatchResult,
    ModelEventOutput,
    ModelVersion,
    OddsSnapshot,
    PlayerStatistic,
    TacticalSnapshot,
    ValueSignal,
)
from app.schemas.api import ReadinessCounts


def readiness_counts(session: Session) -> ReadinessCounts:
    intelligence = sum(
        _count(session, model)
        for model in (PlayerStatistic, AvailabilityReport, LineupSnapshot, TacticalSnapshot)
    )
    signal_backtests = (
        session.scalar(
            select(func.count(func.distinct(BacktestObservation.run_id))).where(
                BacktestObservation.odds_snapshot_id.is_not(None),
                BacktestObservation.selection_id.is_not(None),
            )
        )
        or 0
    )
    calibrated = (
        session.scalar(
            select(func.count(BacktestRun.id)).where(
                BacktestRun.status == "completed",
                BacktestRun.evaluation_status == "calibrated",
                BacktestRun.is_demo.is_(False),
            )
        )
        or 0
    )
    return ReadinessCounts(
        events=_count(session, Event),
        odds_snapshots=_count(session, OddsSnapshot),
        final_results=_count(session, MatchResult),
        model_versions=_count(session, ModelVersion),
        predictions=_count(session, ModelEventOutput),
        non_demo_calibrated_evaluations=calibrated,
        signals=_count(session, ValueSignal),
        signal_backtests=signal_backtests,
        bookmaker_tax_mappings=_count(session, BookmakerTaxProfile),
        bookmaker_constraints=_count(session, BookmakerConstraint),
        intelligence_records=intelligence,
    )


def _count(session: Session, model: type[object]) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0
