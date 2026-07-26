from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Event,
    LineupMember,
    LineupSnapshot,
    Market,
    ModelEventOutput,
    ModelVersion,
    OddsSnapshot,
    Provider,
)
from app.schemas.models import PredictEventRequest
from app.services.modeling import ModelingError, predict_event
from app.services.signals import list_research_value_candidates


@dataclass(frozen=True)
class PredictionRefreshSummary:
    eligible_events: int
    predictions_created: int
    predictions_reused: int
    events_skipped: int
    research_candidates_available: int = 0
    skip_reasons: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class ConfirmedLineupRefreshSummary:
    eligible_events: int
    predictions_created: int
    predictions_reused: int
    events_skipped: int
    research_candidates_available: int = 0


def refresh_upcoming_predictions(
    session: Session,
    *,
    as_of: datetime,
    horizon_hours: int = 168,
) -> PredictionRefreshSummary:
    """Persist point-in-time baseline predictions for upcoming priced fixtures."""
    cutoff = _utc(as_of)
    horizon = cutoff + timedelta(hours=horizon_hours)
    event_ids = list(
        session.scalars(
            select(Event.id)
            .join(Market, Market.event_id == Event.id)
            .join(OddsSnapshot, OddsSnapshot.market_id == Market.id)
            .join(Provider, Provider.id == OddsSnapshot.provider_id)
            .where(
                Event.status == "scheduled",
                Event.is_demo.is_(False),
                Event.kickoff_at > cutoff,
                Event.kickoff_at <= horizon,
                Provider.is_demo.is_(False),
                OddsSnapshot.observed_at <= cutoff,
            )
            .distinct()
            .order_by(Event.kickoff_at, Event.id)
        )
    )
    models = list(
        session.scalars(
            select(ModelVersion)
            .where(
                ModelVersion.status == "trained",
                ModelVersion.is_demo.is_(False),
                ModelVersion.training_end <= cutoff,
            )
            .order_by(ModelVersion.created_at.desc(), ModelVersion.id.desc())
        )
    )
    models_by_competition: dict[int, ModelVersion] = {}
    for model in models:
        competition_id = model.config.get("competition_id")
        if isinstance(competition_id, int):
            models_by_competition.setdefault(competition_id, model)

    created = 0
    reused = 0
    skip_reasons: Counter[str] = Counter()
    for event_id in event_ids:
        event = session.get(Event, event_id)
        selected_model = (
            models_by_competition.get(event.competition_id) if event is not None else None
        )
        if event is None:
            skip_reasons["event_not_found"] += 1
            continue
        if selected_model is None:
            skip_reasons["no_cutoff_valid_trained_model"] += 1
            continue
        existing_id = session.scalar(
            select(ModelEventOutput.id).where(
                ModelEventOutput.event_id == event.id,
                ModelEventOutput.model_version_id == selected_model.id,
                ModelEventOutput.predicted_at == cutoff,
                ModelEventOutput.inputs_as_of == cutoff,
                ModelEventOutput.evidence_class == "team_baseline",
            )
        )
        try:
            predict_event(
                session,
                selected_model.id,
                PredictEventRequest(
                    event_id=event.id,
                    predicted_at=cutoff,
                    inputs_as_of=cutoff,
                ),
                now=cutoff,
            )
        except ModelingError as exc:
            skip_reasons[_modeling_skip_reason(exc)] += 1
            continue
        if existing_id is None:
            created += 1
        else:
            reused += 1
    return PredictionRefreshSummary(
        eligible_events=len(event_ids),
        predictions_created=created,
        predictions_reused=reused,
        events_skipped=sum(skip_reasons.values()),
        research_candidates_available=_research_candidate_count(session, cutoff, horizon_hours),
        skip_reasons=dict(sorted(skip_reasons.items())),
    )


def _modeling_skip_reason(exc: ModelingError) -> str:
    message = str(exc)
    if message.startswith("insufficient home team at home history:"):
        return "insufficient_home_team_home_history"
    if message.startswith("insufficient away team away history:"):
        return "insufficient_away_team_away_history"
    return {
        "model version not found": "model_version_not_found",
        "model version is not an active Poisson team-strength model": "model_not_active",
        "event not found": "event_not_found",
        "prediction must be generated before kickoff": "cutoff_not_before_kickoff",
        "inputs_as_of cannot be after predicted_at": "inputs_after_prediction",
        "model training window ends after the prediction input cutoff": (
            "model_training_after_cutoff"
        ),
        "event competition does not match the model competition": ("model_competition_mismatch"),
    }.get(message, "modeling_validation_failed")


def refresh_confirmed_lineup_predictions(
    session: Session,
    *,
    as_of: datetime,
    horizon_hours: int = 168,
) -> ConfirmedLineupRefreshSummary:
    cutoff = _utc(as_of)
    horizon = cutoff + timedelta(hours=horizon_hours)
    event_ids = list(
        session.scalars(
            select(Event.id)
            .join(LineupSnapshot, LineupSnapshot.event_id == Event.id)
            .where(
                Event.status == "scheduled",
                Event.is_demo.is_(False),
                Event.kickoff_at > cutoff,
                Event.kickoff_at <= horizon,
                LineupSnapshot.lineup_type == "confirmed",
                LineupSnapshot.observed_at <= cutoff,
                LineupSnapshot.source_updated_at.is_not(None),
                LineupSnapshot.source_updated_at <= cutoff,
            )
            .distinct()
            .order_by(Event.kickoff_at, Event.id)
        )
    )
    models = _latest_models_by_competition(session, cutoff)
    created = 0
    reused = 0
    skipped = 0
    for event_id in event_ids:
        event = session.get(Event, event_id)
        model = models.get(event.competition_id) if event is not None else None
        if event is None or model is None:
            skipped += 1
            continue
        lineup_ids = _latest_complete_confirmed_lineups(session, event, cutoff)
        if lineup_ids is None:
            skipped += 1
            continue
        existing = session.scalar(
            select(ModelEventOutput.id).where(
                ModelEventOutput.event_id == event.id,
                ModelEventOutput.model_version_id == model.id,
                ModelEventOutput.predicted_at == cutoff,
                ModelEventOutput.evidence_class == "confirmed_lineup_context_unadjusted",
            )
        )
        output = predict_event(
            session,
            model.id,
            PredictEventRequest(event_id=event.id, predicted_at=cutoff, inputs_as_of=cutoff),
            now=cutoff,
            lineup_snapshot_ids=lineup_ids,
        )
        if output.evidence_class != "confirmed_lineup_context_unadjusted":
            skipped += 1
        elif existing is None:
            created += 1
        else:
            reused += 1
    return ConfirmedLineupRefreshSummary(
        len(event_ids),
        created,
        reused,
        skipped,
        _research_candidate_count(session, cutoff, horizon_hours),
    )


def _research_candidate_count(session: Session, cutoff: datetime, horizon_hours: int) -> int:
    return len(
        list_research_value_candidates(
            session,
            as_of=cutoff,
            horizon_hours=horizon_hours,
            limit=1000,
        )
    )


def _latest_models_by_competition(session: Session, cutoff: datetime) -> dict[int, ModelVersion]:
    models = session.scalars(
        select(ModelVersion)
        .where(
            ModelVersion.status == "trained",
            ModelVersion.is_demo.is_(False),
            ModelVersion.training_end <= cutoff,
        )
        .order_by(ModelVersion.created_at.desc(), ModelVersion.id.desc())
    )
    result: dict[int, ModelVersion] = {}
    for model in models:
        competition_id = model.config.get("competition_id")
        if isinstance(competition_id, int):
            result.setdefault(competition_id, model)
    return result


def _latest_complete_confirmed_lineups(
    session: Session, event: Event, cutoff: datetime
) -> list[int] | None:
    candidates = session.scalars(
        select(LineupSnapshot)
        .join(Provider, Provider.id == LineupSnapshot.provider_id)
        .where(
            LineupSnapshot.event_id == event.id,
            LineupSnapshot.lineup_type == "confirmed",
            LineupSnapshot.observed_at <= cutoff,
            LineupSnapshot.source_updated_at.is_not(None),
            LineupSnapshot.source_updated_at <= cutoff,
            Provider.is_demo.is_(False),
        )
        .order_by(
            LineupSnapshot.team_id,
            LineupSnapshot.observed_at.desc(),
            LineupSnapshot.id.desc(),
        )
    )
    latest: dict[int, int] = {}
    for lineup in candidates:
        if lineup.team_id in latest:
            continue
        starters = session.scalar(
            select(func.count())
            .select_from(LineupMember)
            .where(
                LineupMember.lineup_snapshot_id == lineup.id,
                LineupMember.starter.is_(True),
            )
        )
        if starters == 11:
            latest[lineup.team_id] = lineup.id
    if set(latest) != {event.home_team_id, event.away_team_id}:
        return None
    return [latest[event.home_team_id], latest[event.away_team_id]]


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
