from __future__ import annotations

from collections.abc import Generator, Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.models import (
    BacktestResult,
    BacktestRun,
    Bookmaker,
    Competition,
    Event,
    MatchResult,
    ModelEventOutput,
    ModelPrediction,
    ModelVersion,
    OddsPrice,
    OddsSnapshot,
    Provider,
    Selection,
    ValueSignal,
)
from app.db.session import Base, get_db
from app.main import app
from app.schemas.backtesting import RunSignalBacktestRequest, SimulateBankrollRequest
from app.schemas.models import PredictEventRequest, TrainPoissonRequest
from app.schemas.signals import GenerateSignalsRequest
from app.services.backtesting import (
    BacktestingError,
    _return_metrics,
    run_signal_backtest,
    simulate_backtest_bankroll,
)
from app.services.demo_seed import seed_demo_data, seed_demo_results
from app.services.modeling import predict_event, train_poisson_model
from app.services.signals import generate_value_signals

AS_OF = datetime(2026, 7, 19, 10, 0, tzinfo=UTC)


@pytest.fixture
def session(tmp_path: Path) -> Iterator[Session]:
    engine = create_engine(
        f"sqlite:///{tmp_path}/backtesting.db", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    with Session(engine) as database_session:
        seed_demo_results(database_session, as_of=AS_OF, ingested_at=AS_OF)
        seed_demo_data(database_session, as_of=AS_OF, ingested_at=AS_OF)
        yield database_session


def _prepared_backtest(session: Session) -> tuple[ModelVersion, Event, RunSignalBacktestRequest]:
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
    teams: dict[str, dict[str, object]] = {}
    for key, value in raw_teams.items():
        assert isinstance(key, str) and isinstance(value, dict)
        teams[key] = dict(value)
    teams[str(event.home_team_id)]["home_matches"] = 20
    teams[str(event.away_team_id)]["away_matches"] = 20
    config["teams"] = teams
    model.config = config
    calibration = BacktestRun(
        model_version_id=model.id,
        status="completed",
        train_end=AS_OF - timedelta(days=2),
        validation_end=AS_OF - timedelta(days=2),
        test_end=AS_OF - timedelta(days=1),
        fingerprint=f"backtest-calibration-{model.id:043d}",
        config={"evaluation_kind": "expanding_window_match_result"},
        policy={"decision": "calibrated"},
        evaluation_status="calibrated",
        is_demo=False,
    )
    session.add(calibration)
    session.flush()
    session.add(
        BacktestResult(
            run_id=calibration.id,
            benchmark="poisson",
            dimension="overall",
            dimension_value="all",
            metrics={
                "observations": 250,
                "coverage": 0.95,
                "brier_score": 0.5,
                "log_loss": 0.8,
                "expected_calibration_error": 0.03,
            },
        )
    )
    away = session.scalar(
        select(ModelPrediction)
        .join(Selection, Selection.id == ModelPrediction.selection_id)
        .where(ModelPrediction.output_id == output.id, Selection.code == "AWAY")
    )
    assert away is not None
    away.probability = 0.45
    away.lower_probability = 0.42
    away.upper_probability = 0.48
    away.fair_odds = 1 / 0.45
    session.commit()
    generate_value_signals(
        session,
        GenerateSignalsRequest(output_id=output.id, generated_at=AS_OF + timedelta(minutes=5)),
    )
    provider_id = session.scalar(select(Provider.id))
    assert provider_id is not None
    kickoff_at = event.kickoff_at.replace(tzinfo=UTC)
    settled_at = kickoff_at + timedelta(hours=2)
    session.add(
        MatchResult(
            event_id=event.id,
            provider_id=provider_id,
            home_goals=0,
            away_goals=1,
            status="final",
            is_final=True,
            source_updated_at=settled_at,
            observed_at=settled_at,
            settled_at=settled_at,
            supersedes_id=None,
        )
    )
    session.commit()
    return (
        model,
        event,
        RunSignalBacktestRequest(
            model_version_id=model.id,
            evaluation_start=AS_OF,
            evaluation_end=kickoff_at + timedelta(days=1),
        ),
    )


def test_signal_backtest_is_idempotent_and_bankroll_uses_settled_units(
    session: Session,
) -> None:
    model, event, request = _prepared_backtest(session)
    kickoff_at = event.kickoff_at.replace(tzinfo=UTC)
    known_at = kickoff_at + timedelta(days=2)

    run = run_signal_backtest(session, request, now=known_at)
    repeated = run_signal_backtest(session, request, now=known_at)

    assert repeated.id == run.id
    assert run.model_version_id == model.id
    assert run.evaluation_status == "research_only"
    assert run.metrics["bet_count"] == 1
    assert run.metrics["wins"] == 1
    assert run.metrics["hit_rate"] == 1
    assert run.metrics["expected_profit_units"] == pytest.approx(run.observations[0].expected_value)
    assert run.metrics["average_decimal_odds"] == pytest.approx(run.observations[0].decimal_odds)
    assert run.metrics["binary_brier_score"] == pytest.approx(
        (1 - run.observations[0].model_probability) ** 2
    )
    assert run.metrics["maximum_losing_streak"] == 0
    assert run.config["metrics_version"] == "recommendation-returns-v3"
    assert run.policy["version"] == "stored-value-signal-replay-v3"
    assert run.observations[0].settlement == "WIN"
    assert run.observations[0].predicted_at < kickoff_at
    assert run.metrics["closing_line_value_coverage"] == 0
    assert run.metrics["average_closing_line_value"] is None

    simulation = simulate_backtest_bankroll(
        session,
        SimulateBankrollRequest(
            backtest_run_id=run.id,
            strategy="flat",
            initial_bankroll=100,
            flat_stake=10,
            maximum_stake_fraction=0.2,
        ),
    )
    assert simulation.final_bankroll > 100
    assert simulation.bets_placed == 1
    assert len(simulation.simulation_fingerprint) == 64
    assert simulation.is_demo is False


def test_recommendation_return_metrics_are_deterministic() -> None:
    metrics = _return_metrics(
        profits=[1.0, -1.0, 0.0, -1.0],
        expected_values=[0.2, 0.2, 0.0, 0.2],
        offered_odds=[2.0, 3.0, 2.0, 4.0],
        model_probabilities=[0.6, 0.4, 0.5, 0.3],
    )

    assert metrics["bet_count"] == 4
    assert metrics["wins"] == 1
    assert metrics["losses"] == 2
    assert metrics["pushes"] == 1
    assert metrics["net_profit_units"] == -1
    assert metrics["expected_profit_units"] == pytest.approx(0.6)
    assert metrics["average_decimal_odds"] == pytest.approx(2.75)
    assert metrics["median_decimal_odds"] == pytest.approx(2.5)
    assert metrics["average_break_even_probability"] == pytest.approx(19 / 48)
    assert metrics["binary_brier_score"] == pytest.approx(0.165)
    assert metrics["maximum_drawdown_units"] == 2
    assert metrics["maximum_losing_streak"] == 2
    assert metrics["profit_factor"] == pytest.approx(0.5)


def test_recommendation_return_metrics_reject_inconsistent_inputs() -> None:
    with pytest.raises(BacktestingError, match="inconsistent lengths"):
        _return_metrics([1.0], [0.2], [2.0], [])


def _store_closing_snapshot(
    session: Session,
    event: Event,
    *,
    observed_at: datetime,
    ingested_at: datetime,
) -> tuple[OddsSnapshot, float]:
    signal = session.scalar(select(ValueSignal).where(ValueSignal.signal_type == "VALUE"))
    assert signal is not None
    taken = session.get_one(OddsSnapshot, signal.odds_snapshot_id)
    selections = session.scalars(
        select(Selection).where(Selection.market_id == taken.market_id)
    ).all()
    closing = OddsSnapshot(
        market_id=taken.market_id,
        bookmaker_id=taken.bookmaker_id,
        provider_id=taken.provider_id,
        import_job_id=None,
        source_updated_at=observed_at,
        observed_at=observed_at,
        ingested_at=ingested_at,
        is_closing=True,
        is_complete=True,
        source_label="timestamped closing fixture",
    )
    session.add(closing)
    session.flush()
    target_odds = 2.0
    for selection in selections:
        session.add(
            OddsPrice(
                snapshot_id=closing.id,
                selection_id=selection.id,
                decimal_odds=Decimal("2.0" if selection.id == signal.selection_id else "3.0"),
            )
        )
    session.commit()
    return closing, target_odds


def test_signal_backtest_reports_timestamp_valid_closing_line_value(session: Session) -> None:
    _, event, request = _prepared_backtest(session)
    kickoff_at = event.kickoff_at.replace(tzinfo=UTC)
    closing, closing_odds = _store_closing_snapshot(
        session,
        event,
        observed_at=kickoff_at - timedelta(minutes=1),
        ingested_at=kickoff_at + timedelta(hours=3),
    )

    run = run_signal_backtest(session, request, now=kickoff_at + timedelta(days=2))
    observation = run.observations[0]
    expected_clv = observation.decimal_odds / closing_odds - 1

    assert observation.closing_odds_snapshot_id == closing.id
    assert observation.closing_decimal_odds == closing_odds
    assert observation.closing_observed_at == kickoff_at - timedelta(minutes=1)
    assert observation.closing_line_value == pytest.approx(expected_clv)
    assert run.metrics["closing_line_value_coverage"] == 1
    assert run.metrics["average_closing_line_value"] == pytest.approx(expected_clv)
    assert run.metrics["median_closing_line_value"] == pytest.approx(expected_clv)


def test_signal_backtest_excludes_post_kickoff_closing_snapshot(session: Session) -> None:
    _, event, request = _prepared_backtest(session)
    kickoff_at = event.kickoff_at.replace(tzinfo=UTC)
    _store_closing_snapshot(
        session,
        event,
        observed_at=kickoff_at + timedelta(minutes=1),
        ingested_at=kickoff_at + timedelta(minutes=2),
    )

    run = run_signal_backtest(session, request, now=kickoff_at + timedelta(days=2))

    assert run.observations[0].closing_odds_snapshot_id is None
    assert run.observations[0].closing_line_value is None
    assert run.metrics["closing_line_value_coverage"] == 0


def test_signal_backtest_rejects_post_cutoff_snapshot_ingestion(session: Session) -> None:
    _, event, request = _prepared_backtest(session)
    snapshot = session.scalar(
        select(OddsSnapshot)
        .join(ValueSignal, ValueSignal.odds_snapshot_id == OddsSnapshot.id)
        .where(ValueSignal.signal_type == "VALUE")
    )
    assert snapshot is not None
    snapshot.ingested_at = AS_OF + timedelta(minutes=6)
    session.commit()

    with pytest.raises(BacktestingError, match="post-cutoff"):
        run_signal_backtest(
            session,
            request,
            now=event.kickoff_at.replace(tzinfo=UTC) + timedelta(days=2),
        )


def test_backtest_and_bankroll_api(session: Session) -> None:
    _, event, request = _prepared_backtest(session)
    engine = session.get_bind()

    def database_override() -> Generator[Session, None, None]:
        with Session(engine) as request_session:
            yield request_session

    app.dependency_overrides[get_db] = database_override
    try:
        with TestClient(app) as client:
            created = client.post("/api/v1/backtests/signals", json=request.model_dump(mode="json"))
            listed = client.get("/api/v1/backtests")
            assert created.status_code == 201
            simulated = client.post(
                "/api/v1/bankroll/simulate",
                json={"backtest_run_id": created.json()["id"], "strategy": "percentage"},
            )
    finally:
        app.dependency_overrides.clear()

    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [created.json()["id"]]
    assert simulated.status_code == 200
    assert simulated.json()["strategy"] == "percentage"
