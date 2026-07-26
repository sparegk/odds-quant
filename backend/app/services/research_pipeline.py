from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Event, Market, ModelEventOutput, ModelVersion, OddsSnapshot, Provider
from app.schemas.models import PredictEventRequest
from app.services.modeling import ModelingError, predict_event


@dataclass(frozen=True)
class PredictionRefreshSummary:
    eligible_events: int
    predictions_created: int
    predictions_reused: int
    events_skipped: int


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
    skipped = 0
    for event_id in event_ids:
        event = session.get(Event, event_id)
        selected_model = (
            models_by_competition.get(event.competition_id) if event is not None else None
        )
        if event is None or selected_model is None:
            skipped += 1
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
        except ModelingError:
            skipped += 1
            continue
        if existing_id is None:
            created += 1
        else:
            reused += 1
    return PredictionRefreshSummary(
        eligible_events=len(event_ids),
        predictions_created=created,
        predictions_reused=reused,
        events_skipped=skipped,
    )


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
