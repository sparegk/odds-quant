from __future__ import annotations

from collections.abc import Generator, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db.models import (
    BacktestResult,
    BacktestRun,
    Bookmaker,
    Competition,
    Event,
    Market,
    ModelEventOutput,
    ModelPrediction,
    ModelVersion,
    OddsSnapshot,
    Provider,
    Selection,
    ValueSignal,
)
from app.db.session import Base, get_db
from app.main import app
from app.schemas.models import PredictEventRequest, TrainPoissonRequest
from app.schemas.signals import GenerateSignalsRequest
from app.services.demo_seed import seed_demo_data, seed_demo_results
from app.services.modeling import predict_event, train_poisson_model
from app.services.signals import (
    SignalGenerationError,
    generate_value_signals,
    list_underdog_signals,
    list_value_signals,
)

AS_OF = datetime(2026, 7, 19, 10, 0, tzinfo=UTC)


@pytest.fixture
def session(tmp_path: Path) -> Iterator[Session]:
    engine = create_engine(
        f"sqlite:///{tmp_path}/signals.db", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    with Session(engine) as database_session:
        seed_demo_results(database_session, as_of=AS_OF, ingested_at=AS_OF)
        seed_demo_data(database_session, as_of=AS_OF, ingested_at=AS_OF)
        yield database_session


def _prepared_output(session: Session) -> tuple[ModelVersion, ModelEventOutput, Event]:
    competition_id = session.scalar(select(Competition.id))
    event = session.scalar(
        select(Event).where(Event.status == "scheduled").order_by(Event.kickoff_at)
    )
    assert competition_id is not None and event is not None
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
    output_view = predict_event(
        session,
        model_view.id,
        PredictEventRequest(event_id=event.id, predicted_at=AS_OF, inputs_as_of=AS_OF),
        now=AS_OF,
    )
    model = session.get_one(ModelVersion, model_view.id)
    output = session.get_one(ModelEventOutput, output_view.id)
    return model, output, event


def _make_live_and_calibrated(
    session: Session, model: ModelVersion, output: ModelEventOutput, event: Event
) -> BacktestRun:
    for provider in session.scalars(select(Provider)).all():
        provider.is_demo = False
    for bookmaker in session.scalars(select(Bookmaker)).all():
        bookmaker.is_demo = False
    event.is_demo = False
    model.is_demo = False
    model.evaluation_status = "calibrated"
    config = dict(model.config)
    raw_teams = config["teams"]
    assert isinstance(raw_teams, dict)
    teams = {key: dict(value) for key, value in raw_teams.items()}
    teams[str(event.home_team_id)]["home_matches"] = 20
    teams[str(event.away_team_id)]["away_matches"] = 20
    config["teams"] = teams
    model.config = config
    run = BacktestRun(
        model_version_id=model.id,
        status="completed",
        train_end=AS_OF - timedelta(days=2),
        validation_end=AS_OF - timedelta(days=2),
        test_end=AS_OF - timedelta(days=1),
        fingerprint=f"signal-evaluation-{model.id:044d}",
        config={"kind": "test"},
        policy={"decision": "calibrated"},
        evaluation_status="calibrated",
        is_demo=False,
    )
    session.add(run)
    session.flush()
    session.add(
        BacktestResult(
            run_id=run.id,
            benchmark="poisson",
            dimension="overall",
            dimension_value="all",
            metrics={
                "observations": 250,
                "coverage": 0.95,
                "brier_score": 0.55,
                "log_loss": 0.9,
                "expected_calibration_error": 0.04,
            },
        )
    )
    away_prediction = session.scalar(
        select(ModelPrediction)
        .join(Selection, Selection.id == ModelPrediction.selection_id)
        .where(ModelPrediction.output_id == output.id, Selection.code == "AWAY")
    )
    assert away_prediction is not None
    away_prediction.probability = 0.45
    away_prediction.lower_probability = 0.42
    away_prediction.upper_probability = 0.48
    away_prediction.fair_odds = 1 / 0.45
    session.commit()
    return run


def test_uncalibrated_or_demo_prediction_is_blocked(session: Session) -> None:
    _, output, _ = _prepared_output(session)

    with pytest.raises(SignalGenerationError, match="demo"):
        generate_value_signals(
            session,
            GenerateSignalsRequest(output_id=output.id, generated_at=AS_OF + timedelta(minutes=5)),
        )


def test_calibrated_signal_generation_is_persisted_and_idempotent(
    session: Session,
) -> None:
    model, output, event = _prepared_output(session)
    evaluation = _make_live_and_calibrated(session, model, output, event)
    request = GenerateSignalsRequest(output_id=output.id, generated_at=AS_OF + timedelta(minutes=5))

    batch = generate_value_signals(session, request)
    repeated = generate_value_signals(session, request)

    assert batch.evaluation_run_id == evaluation.id
    assert len(batch.signals) == 3
    assert [signal.id for signal in repeated.signals] == [signal.id for signal in batch.signals]
    assert session.scalar(select(func.count()).select_from(ValueSignal)) == 3
    assert all(signal.bookmaker_count == 2 for signal in batch.signals)
    assert all(signal.calibration_error == pytest.approx(0.04) for signal in batch.signals)
    assert all(signal.odds_age_minutes == pytest.approx(5) for signal in batch.signals)
    away = next(signal for signal in batch.signals if signal.selection_code == "AWAY")
    assert away.signal_type == "VALUE"
    assert away.expected_value > 0
    assert away.lower_expected_value > 0
    assert away.probability_edge > 0
    assert away.evaluation_run_id == evaluation.id

    stored = list_value_signals(session, event_id=event.id)
    assert len(stored) == 3
    underdogs = list_underdog_signals(session)
    assert [signal.selection_code for signal in underdogs] == ["AWAY"]


def test_stale_price_is_persisted_as_insufficient_data(session: Session) -> None:
    model, output, event = _prepared_output(session)
    _make_live_and_calibrated(session, model, output, event)

    batch = generate_value_signals(
        session,
        GenerateSignalsRequest(
            output_id=output.id,
            generated_at=AS_OF + timedelta(minutes=61),
        ),
    )

    assert all(signal.signal_type == "INSUFFICIENT_DATA" for signal in batch.signals)
    assert all(signal.odds_age_minutes == pytest.approx(61) for signal in batch.signals)


def test_stale_bookmaker_is_excluded_when_fresh_consensus_exists(
    session: Session,
) -> None:
    model, output, event = _prepared_output(session)
    _make_live_and_calibrated(session, model, output, event)
    snapshots = session.scalars(
        select(OddsSnapshot)
        .join(Market, Market.id == OddsSnapshot.market_id)
        .where(Market.event_id == event.id)
        .order_by(OddsSnapshot.id)
    ).all()
    assert len(snapshots) == 2
    snapshots[0].observed_at = AS_OF - timedelta(hours=2)
    snapshots[0].source_updated_at = AS_OF - timedelta(hours=2)
    session.commit()

    batch = generate_value_signals(
        session,
        GenerateSignalsRequest(
            output_id=output.id,
            generated_at=AS_OF + timedelta(minutes=5),
        ),
    )

    assert all(signal.bookmaker_count == 1 for signal in batch.signals)
    assert all(signal.odds_age_minutes == pytest.approx(5) for signal in batch.signals)


def test_calibration_evidence_after_prediction_cutoff_is_rejected(
    session: Session,
) -> None:
    model, output, event = _prepared_output(session)
    run = _make_live_and_calibrated(session, model, output, event)
    run.test_end = AS_OF + timedelta(minutes=1)
    session.commit()

    with pytest.raises(SignalGenerationError, match="predates"):
        generate_value_signals(
            session,
            GenerateSignalsRequest(
                output_id=output.id,
                generated_at=AS_OF + timedelta(minutes=5),
            ),
        )


def test_signal_api_generation_listing_and_underdog_view(session: Session) -> None:
    model, output, event = _prepared_output(session)
    _make_live_and_calibrated(session, model, output, event)
    engine = session.get_bind()

    def database_override() -> Generator[Session, None, None]:
        with Session(engine) as request_session:
            yield request_session

    app.dependency_overrides[get_db] = database_override
    try:
        with TestClient(app) as client:
            generated = client.post(
                "/api/v1/signals/generate",
                json={
                    "output_id": output.id,
                    "generated_at": (AS_OF + timedelta(minutes=5)).isoformat(),
                },
            )
            listed = client.get("/api/v1/signals", params={"event_id": event.id})
            recommendations = client.get("/api/v1/recommendations", params={"event_id": event.id})
            underdogs = client.get("/api/v1/signals/underdogs")
    finally:
        app.dependency_overrides.clear()

    assert generated.status_code == 201
    assert len(generated.json()["signals"]) == 3
    assert listed.status_code == 200
    assert len(listed.json()) == 3
    assert recommendations.status_code == 200
    assert len(recommendations.json()) == 1
    assert recommendations.json()[0]["signal_type"] == "VALUE"
    assert underdogs.status_code == 200
    assert [signal["selection_code"] for signal in underdogs.json()] == ["AWAY"]
