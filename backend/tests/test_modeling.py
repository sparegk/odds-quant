from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db.models import Competition, Event, MatchResult, ModelPrediction
from app.db.session import Base
from app.schemas.models import PredictEventRequest, TrainPoissonRequest
from app.services.demo_seed import build_demo_results_csv, seed_demo_data, seed_demo_results
from app.services.modeling import ModelingError, predict_event, train_poisson_model
from app.services.results_import import import_results_csv

AS_OF = datetime(2026, 7, 19, 10, 0, tzinfo=UTC)


@pytest.fixture
def session(tmp_path: Path) -> Iterator[Session]:
    engine = create_engine(f"sqlite:///{tmp_path}/modeling.db")
    Base.metadata.create_all(engine)
    with Session(engine) as database_session:
        seed_demo_results(database_session, as_of=AS_OF, ingested_at=AS_OF)
        seed_demo_data(database_session, as_of=AS_OF, ingested_at=AS_OF)
        yield database_session


def _training_request(session: Session) -> TrainPoissonRequest:
    competition_id = session.scalar(select(Competition.id))
    assert competition_id is not None
    return TrainPoissonRequest(
        competition_id=competition_id,
        training_start=AS_OF - timedelta(days=150),
        training_end=AS_OF,
        minimum_matches=20,
        minimum_team_matches=3,
        shrinkage_matches=5,
    )


def test_training_and_prediction_are_versioned_and_persisted(session: Session) -> None:
    model = train_poisson_model(session, _training_request(session), now=AS_OF)
    target = session.scalar(
        select(Event).where(Event.status == "scheduled").order_by(Event.kickoff_at)
    )
    assert target is not None

    output = predict_event(
        session,
        model.id,
        PredictEventRequest(event_id=target.id, predicted_at=AS_OF, inputs_as_of=AS_OF),
        now=AS_OF,
    )
    repeated = predict_event(
        session,
        model.id,
        PredictEventRequest(event_id=target.id, predicted_at=AS_OF, inputs_as_of=AS_OF),
        now=AS_OF,
    )

    assert model.sample_size == 32
    assert model.evaluation_status == "unvalidated"
    assert model.metrics["held_out_evaluation"] is False
    assert output.id == repeated.id
    assert output.home_lambda > 0 and output.away_lambda > 0
    assert sum(output.derived_probabilities["MATCH_RESULT"].values()) == pytest.approx(1)
    assert sum(output.derived_probabilities["TOTAL_GOALS_2.5"].values()) == pytest.approx(1)
    assert len(output.predictions) == 3
    assert session.scalar(select(func.count()).select_from(ModelPrediction)) == 3


def test_post_cutoff_correction_cannot_change_training_data(session: Session) -> None:
    request = _training_request(session)
    original = train_poisson_model(session, request, now=AS_OF)
    result = session.scalar(select(MatchResult).order_by(MatchResult.id))
    assert result is not None
    session.add(
        MatchResult(
            event_id=result.event_id,
            provider_id=result.provider_id,
            home_goals=result.home_goals + 5,
            away_goals=result.away_goals,
            status="final",
            is_final=True,
            source_updated_at=AS_OF + timedelta(hours=1),
            observed_at=AS_OF + timedelta(hours=1),
            settled_at=result.settled_at,
            supersedes_id=result.id,
        )
    )
    session.commit()

    repeated = train_poisson_model(session, request, now=AS_OF + timedelta(hours=2))

    assert repeated.id == original.id
    assert repeated.data_fingerprint == original.data_fingerprint
    assert repeated.sample_size == 32


def test_prediction_at_or_after_kickoff_is_rejected(session: Session) -> None:
    model = train_poisson_model(session, _training_request(session), now=AS_OF)
    target = session.scalar(
        select(Event).where(Event.status == "scheduled").order_by(Event.kickoff_at)
    )
    assert target is not None

    with pytest.raises(ModelingError, match="before kickoff"):
        predict_event(
            session,
            model.id,
            PredictEventRequest(
                event_id=target.id,
                predicted_at=target.kickoff_at.replace(tzinfo=UTC),
                inputs_as_of=AS_OF,
            ),
        )


def test_duplicate_result_provider_does_not_double_count_matches(session: Session) -> None:
    import_results_csv(
        session,
        filename="second-provider.csv",
        content=build_demo_results_csv(AS_OF),
        provider_slug="second-results-provider",
        provider_name="Second synthetic result source",
        is_demo=True,
        now=AS_OF,
    )

    model = train_poisson_model(session, _training_request(session), now=AS_OF)

    assert model.sample_size == 32


def test_current_season_model_uses_only_same_canonical_competition_history(
    session: Session,
) -> None:
    prior_season = session.scalar(select(Competition))
    assert prior_season is not None
    current_season = Competition(
        sport_id=prior_season.sport_id,
        name=prior_season.name,
        country=prior_season.country,
        season="2027/2028",
    )
    session.add(current_season)
    session.flush()
    target = session.scalar(
        select(Event).where(Event.status == "scheduled").order_by(Event.kickoff_at)
    )
    assert target is not None
    target.competition_id = current_season.id
    session.commit()

    request = _training_request(session).model_copy(update={"competition_id": current_season.id})
    model = train_poisson_model(session, request, now=AS_OF)
    output = predict_event(
        session,
        model.id,
        PredictEventRequest(event_id=target.id, predicted_at=AS_OF, inputs_as_of=AS_OF),
        now=AS_OF,
    )

    assert model.sample_size == 32
    assert model.feature_version == "final-score-home-away-v2-cross-season"
    assert model.config["competition_id"] == current_season.id
    assert model.config["training_competition_ids"] == [
        prior_season.id,
        current_season.id,
    ]
    assert model.config["training_competition_scope"] == ("same_sport_name_country_all_seasons")
    assert output.event_id == target.id
