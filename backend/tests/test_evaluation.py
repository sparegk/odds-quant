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
from app.services.evaluation import (
    EvaluationError,
    _policy_decision,
    evaluate_model,
)
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
    score_intervals = run.metrics["score_intervals"]
    assert isinstance(score_intervals, dict)
    brier_interval = score_intervals["brier_score"]
    log_loss_interval = score_intervals["log_loss"]
    assert isinstance(brier_interval, dict) and isinstance(log_loss_interval, dict)
    assert brier_interval["method"] == "moving_block_bootstrap"
    assert brier_interval["estimate"] == pytest.approx(brier_score)
    assert log_loss_interval["estimate"] == pytest.approx(log_loss)
    assert brier_interval["confidence_level"] == pytest.approx(0.95)
    assert brier_interval["resamples"] == 2000
    assert brier_interval["block_length"] == 2
    assert isinstance(brier_interval["seed"], int)

    uniform_metrics = run.benchmarks["uniform"]
    assert uniform_metrics["brier_score"] == pytest.approx(2 / 3)
    paired = uniform_metrics["paired_loss_difference"]
    assert isinstance(paired, dict)
    assert paired["definition"] == "poisson_loss_minus_benchmark_loss"
    paired_brier = paired["brier_score"]
    assert isinstance(paired_brier, dict)
    assert paired_brier["estimate"] == pytest.approx(brier_score - 2 / 3)
    assert paired_brier["observations"] == 8
    assert run.benchmarks["uniform"]["brier_score"] == pytest.approx(2 / 3)
    assert run.benchmarks["elo"]["observations"] == 8
    assert isinstance(run.benchmarks["elo"]["brier_score"], float)
    assert isinstance(run.benchmarks["elo"]["log_loss"], float)
    assert run.config["elo_benchmark"] == {
        "version": "davidson-elo-v1",
        "initial_rating": 1500.0,
        "k_factor": 20.0,
        "scale": 400.0,
        "home_advantage": 75.0,
        "draw_probability_at_even_strength": 0.26,
    }
    assert run.benchmarks["dixon_coles"]["observations"] == 8
    assert isinstance(run.benchmarks["dixon_coles"]["brier_score"], float)
    assert isinstance(run.benchmarks["dixon_coles"]["log_loss"], float)
    assert run.config["dixon_coles_benchmark"] == {
        "version": "time-decayed-dixon-coles-v1",
        "decay_rate": 0.0018,
        "low_score_rho_bounds": [-0.2, 0.2],
    }
    bootstrap_config = run.config["bootstrap"]
    assert isinstance(bootstrap_config, dict)
    assert run.config["evaluation_method_version"] == "expanding-window-block-bootstrap-v2"
    assert bootstrap_config["method"] == "moving_block_bootstrap"
    assert bootstrap_config["confidence_level"] == pytest.approx(0.95)
    assert bootstrap_config["resamples"] == 2000
    assert len(str(bootstrap_config["seed_material_sha256"])) == 64
    assert run.policy["version"] == "probability-calibration-v2"
    checks = run.policy["checks"]
    assert isinstance(checks, dict)
    paired_log_loss = paired["log_loss"]
    assert isinstance(paired_log_loss, dict)
    assert checks["uniform_brier_upper_difference_below_zero"] is (paired_brier["upper"] < 0)
    assert checks["uniform_log_loss_upper_difference_below_zero"] is (paired_log_loss["upper"] < 0)
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


def test_walk_forward_evaluation_uses_prior_canonical_competition_seasons(
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
    evaluation_start = AS_OF - timedelta(days=50)
    current_events = session.scalars(
        select(Event).where(Event.kickoff_at >= evaluation_start)
    ).all()
    assert current_events
    for event in current_events:
        event.competition_id = current_season.id
    session.commit()

    model_view = train_poisson_model(
        session,
        TrainPoissonRequest(
            competition_id=current_season.id,
            training_start=AS_OF - timedelta(days=150),
            training_end=evaluation_start,
            minimum_matches=20,
            minimum_team_matches=3,
            shrinkage_matches=5,
        ),
        now=AS_OF,
    )
    run = evaluate_model(
        session,
        model_view.id,
        _request(),
        now=AS_OF,
    )

    assert run.metrics["candidate_events"] == 12
    assert run.metrics["evaluated_events"] == 8
    assert run.config["competition_id"] == current_season.id
    observations = session.scalars(select(BacktestObservation)).all()
    assert observations
    assert all(
        observation.training_cutoff == observation.predicted_at for observation in observations
    )


def test_post_evaluation_correction_does_not_rewrite_existing_run(
    session: Session,
) -> None:
    model = _model(session)
    original = evaluate_model(session, model.id, _request(), now=AS_OF)
    original_elo = original.benchmarks["elo"]
    original_dixon_coles = original.benchmarks["dixon_coles"]
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
    assert repeated.benchmarks["elo"] == original_elo
    assert repeated.benchmarks["dixon_coles"] == original_dixon_coles
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
    market_comparison = market_metrics["paired_loss_difference"]
    assert isinstance(market_comparison, dict)
    market_brier_difference = market_comparison["brier_score"]
    assert isinstance(market_brier_difference, dict)
    assert market_brier_difference["observations"] == 1
    assert market_brier_difference["lower"] == pytest.approx(market_brier_difference["estimate"])
    assert market_brier_difference["upper"] == pytest.approx(market_brier_difference["estimate"])
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


def test_promotion_requires_confident_uniform_baseline_superiority() -> None:
    metrics: dict[str, object] = {
        "observations": 200,
        "coverage": 0.95,
        "expected_calibration_error": 0.05,
    }
    uniform_metrics: dict[str, object] = {
        "paired_loss_difference": {
            "brier_score": {"estimate": -0.02, "lower": -0.04, "upper": 0.001},
            "log_loss": {"estimate": -0.03, "lower": -0.05, "upper": -0.002},
        }
    }

    status, policy = _policy_decision(metrics, uniform_metrics, is_demo=False)

    assert status == "calibration_failed"
    checks = policy["checks"]
    assert isinstance(checks, dict)
    assert checks["uniform_brier_upper_difference_below_zero"] is False
    assert checks["uniform_log_loss_upper_difference_below_zero"] is True

    paired = uniform_metrics["paired_loss_difference"]
    assert isinstance(paired, dict)
    paired["brier_score"] = {"estimate": -0.02, "lower": -0.04, "upper": -0.001}
    status, policy = _policy_decision(metrics, uniform_metrics, is_demo=False)

    assert status == "calibrated"
    checks = policy["checks"]
    assert isinstance(checks, dict)
    assert all(policy_check is True for policy_check in checks.values())
