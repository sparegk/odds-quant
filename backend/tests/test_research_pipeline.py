from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Bookmaker,
    Competition,
    Event,
    ModelEventOutput,
    ModelVersion,
    OddsSnapshot,
    Provider,
)
from app.db.session import Base
from app.schemas.models import TrainPoissonRequest
from app.services.demo_seed import seed_demo_data, seed_demo_results
from app.services.modeling import train_poisson_model
from app.services.research_pipeline import refresh_upcoming_predictions

AS_OF = datetime(2026, 7, 19, 10, 0, tzinfo=UTC)


@pytest.fixture
def session(tmp_path: Path) -> Iterator[Session]:
    engine = create_engine(f"sqlite:///{tmp_path}/research-pipeline.db")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_demo_results(session, as_of=AS_OF, ingested_at=AS_OF)
        seed_demo_data(session, as_of=AS_OF, ingested_at=AS_OF)
        yield session


def _make_research_data_live(session: Session) -> ModelVersion:
    competition_id = session.scalar(select(Competition.id))
    assert competition_id is not None
    model_view = train_poisson_model(
        session,
        TrainPoissonRequest(
            competition_id=competition_id,
            training_start=AS_OF - timedelta(days=150),
            training_end=AS_OF,
            minimum_matches=20,
            minimum_team_matches=3,
            shrinkage_matches=5,
        ),
        now=AS_OF,
    )
    model = session.get_one(ModelVersion, model_view.id)
    model.is_demo = False
    for event in session.scalars(select(Event).where(Event.status == "scheduled")):
        event.is_demo = False
    for provider in session.scalars(select(Provider)):
        provider.is_demo = False
    for bookmaker in session.scalars(select(Bookmaker)):
        bookmaker.is_demo = False
    session.commit()
    return model


def test_refresh_rejects_future_prices_and_is_idempotent_at_exact_cutoff(
    session: Session,
) -> None:
    _make_research_data_live(session)
    available_at = AS_OF + timedelta(seconds=1)
    for snapshot in session.scalars(select(OddsSnapshot)):
        snapshot.observed_at = available_at
        snapshot.ingested_at = available_at
    session.commit()

    before_price = refresh_upcoming_predictions(session, as_of=AS_OF)
    first = refresh_upcoming_predictions(session, as_of=available_at)
    repeated = refresh_upcoming_predictions(session, as_of=available_at)

    scheduled = session.scalar(
        select(func.count()).select_from(Event).where(Event.status == "scheduled")
    )
    assert before_price.eligible_events == 0
    assert before_price.predictions_created == 0
    assert first.eligible_events == scheduled
    assert first.predictions_created == scheduled
    assert first.predictions_reused == 0
    assert repeated.predictions_created == 0
    assert repeated.predictions_reused == scheduled
    assert session.scalar(select(func.count()).select_from(ModelEventOutput)) == scheduled
