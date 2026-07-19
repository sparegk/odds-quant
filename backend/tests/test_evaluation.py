from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db.models import (
    BacktestObservation,
    BacktestResult,
    BacktestRun,
    Bookmaker,
    Competition,
    Event,
    Market,
    MatchResult,
    ModelVersion,
    OddsPrice,
    OddsSnapshot,
    Provider,
    Selection,
)
from app.db.session import Base
from app.schemas.models import EvaluateModelRequest, TrainPoissonRequest
from app.services.demo_seed import seed_demo_results
from app.services.evaluation import EvaluationError, evaluate_model
from app.services.modeling import train_poisson_model

AS_OF = datetime(2026, 7, 19, 10, 0, tzinfo=UTC)


@pytest.fixture
def session(tmp_path: Path) -> Iterator[Session]:
    engine = create_engine(f"sqlite:///{tmp_path}/evaluation.db")
    Base.metadata.create_all(engine)
    with Session(engine) as database_session:
        seed_demo_results(database_session, as_of=AS_OF, ingested_at=AS_OF)
        yield database_session


def _model(session: Session) -> ModelVersion:
    competition_id = session.scalar(select(Competition.id))
    assert competition_id is not None
    view = train_poisson_model(
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
    model = session.get(ModelVersion, view.id)
    assert model is not None
    return model


def _request() -> EvaluateModelRequest:
    return EvaluateModelRequest(
        evaluation_start=AS_OF - timedelta(days=50),
        evaluation_end=AS_OF,
        prediction_lead_minutes=60,
        minimum_training_matches=20,
        calibration_bins=5,
    )


def test_walk_forward_evaluation_persists_immutable_demo_evidence(
    session: Session,
) -> None:
    model = _model(session)

    run = evaluate_model(session, model.id, _request(), now=AS_OF)
    repeated = evaluate_model(session, model.id, _request(), now=AS_OF)

    assert repeated.id == run.id
    assert run.evaluation_status == "demo_only"
    assert run.is_demo is True
    assert run.metrics["candidate_events"] == 12
    assert run.metrics["evaluated_events"] == 8
    assert run.metrics["coverage"] == pytest.approx(2 / 3)
    assert run.metrics["excluded_events"] == {"insufficient_home_venue_history": 4}
    brier_score = run.metrics["brier_score"]
    log_loss = run.metrics["log_loss"]
    assert isinstance(brier_score, (int, float)) and brier_score >= 0
    assert isinstance(log_loss, (int, float)) and log_loss >= 0
    assert run.benchmarks["uniform"]["brier_score"] == pytest.approx(2 / 3)
    assert len(run.calibration) > 0
    session.refresh(model)
    assert model.evaluation_status == "unvalidated"
    assert session.scalar(select(func.count()).select_from(BacktestRun)) == 1
    assert session.scalar(select(func.count()).select_from(BacktestObservation)) == 8
    result_count = session.scalar(select(func.count()).select_from(BacktestResult))
    assert result_count is not None and result_count > 2

    observations = session.scalars(
        select(BacktestObservation).order_by(BacktestObservation.predicted_at)
    ).all()
    assert observations[0].training_sample_size == 24
    assert all(
        observation.training_sample_size is not None and observation.training_sample_size >= 20
        for observation in observations
    )
    assert all(
        observation.training_cutoff == observation.predicted_at for observation in observations
    )
    assert all(observation.result_id is not None for observation in observations)
    assert all(
        observation.predicted_at < session.get_one(Event, observation.event_id).kickoff_at
        for observation in observations
    )


def test_post_evaluation_correction_does_not_rewrite_existing_run(
    session: Session,
) -> None:
    model = _model(session)
    original = evaluate_model(session, model.id, _request(), now=AS_OF)
    training_result = session.scalar(select(MatchResult).order_by(MatchResult.id))
    assert training_result is not None
    session.add(
        MatchResult(
            event_id=training_result.event_id,
            provider_id=training_result.provider_id,
            home_goals=training_result.home_goals + 4,
            away_goals=training_result.away_goals,
            status="final",
            is_final=True,
            source_updated_at=AS_OF + timedelta(hours=1),
            observed_at=AS_OF + timedelta(hours=1),
            settled_at=training_result.settled_at,
            supersedes_id=training_result.id,
        )
    )
    session.commit()

    repeated = evaluate_model(session, model.id, _request(), now=AS_OF + timedelta(hours=2))

    assert repeated.id == original.id
    assert repeated.fingerprint == original.fingerprint
    assert session.scalar(select(func.count()).select_from(BacktestRun)) == 1


def test_market_benchmark_uses_only_compatible_pre_cutoff_snapshot(
    session: Session,
) -> None:
    model = _model(session)
    event = session.scalar(
        select(Event).where(Event.provider_event_key == "demo-history-20260719-25")
    )
    provider_id = session.scalar(select(Provider.id))
    assert event is not None and provider_id is not None
    bookmaker = Bookmaker(slug="benchmark-book", name="Benchmark Book", is_demo=True)
    market = Market(
        event_id=event.id,
        market_type="MATCH_RESULT",
        line=None,
        line_key="",
        period="FULL_TIME",
        currency="EUR",
        settlement_rule_key="standard_90_minutes",
    )
    session.add_all([bookmaker, market])
    session.flush()
    selections = {
        code: Selection(market_id=market.id, code=code, name=code.title())
        for code in ("HOME", "DRAW", "AWAY")
    }
    session.add_all(selections.values())
    session.flush()
    snapshot = OddsSnapshot(
        market_id=market.id,
        bookmaker_id=bookmaker.id,
        provider_id=provider_id,
        import_job_id=None,
        source_updated_at=event.kickoff_at - timedelta(hours=2),
        observed_at=event.kickoff_at - timedelta(hours=2),
        ingested_at=AS_OF,
        is_closing=False,
        is_complete=True,
        source_label="timestamped benchmark fixture",
    )
    session.add(snapshot)
    session.flush()
    for code, odds in {"HOME": "2.00", "DRAW": "3.00", "AWAY": "4.00"}.items():
        session.add(
            OddsPrice(
                snapshot_id=snapshot.id,
                selection_id=selections[code].id,
                decimal_odds=Decimal(odds),
            )
        )
    session.commit()

    run = evaluate_model(session, model.id, _request(), now=AS_OF)

    market_metrics = run.benchmarks["market_consensus"]
    assert market_metrics["observations"] == 1
    assert market_metrics["coverage"] == pytest.approx(1 / 8)
    stored = session.scalar(
        select(BacktestObservation).where(
            BacktestObservation.event_id == event.id,
            BacktestObservation.run_id == run.id,
        )
    )
    assert stored is not None
    assert stored.market_snapshot_ids == [snapshot.id]
    assert stored.market_probabilities == pytest.approx(
        {"HOME": 6 / 13, "DRAW": 4 / 13, "AWAY": 3 / 13}
    )


def test_evaluation_rejects_future_end_and_ineligible_window(session: Session) -> None:
    model = _model(session)
    with pytest.raises(EvaluationError, match="future"):
        evaluate_model(
            session,
            model.id,
            EvaluateModelRequest(
                evaluation_start=AS_OF - timedelta(days=10),
                evaluation_end=AS_OF + timedelta(days=1),
            ),
            now=AS_OF,
        )
    with pytest.raises(EvaluationError, match="eligible"):
        evaluate_model(
            session,
            model.id,
            EvaluateModelRequest(
                evaluation_start=AS_OF - timedelta(days=110),
                evaluation_end=AS_OF - timedelta(days=100),
                minimum_training_matches=20,
            ),
            now=AS_OF,
        )
