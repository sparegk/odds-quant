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
from app.schemas.models import EvaluateModelRequest, TrainEloRequest, TrainPoissonRequest
from app.services.demo_seed import seed_demo_results
from app.services.evaluation import (
    EvaluationError,
    _fingerprint_request,
    _policy_decision,
    _temperature_recalibration_metrics,
    evaluate_model,
)
from app.services.modeling import train_elo_model, train_poisson_model

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


def _elo_model(session: Session) -> ModelVersion:
    competition_id = session.scalar(select(Competition.id))
    assert competition_id is not None
    view = train_elo_model(
        session,
        TrainEloRequest(
            competition_id=competition_id,
            training_start=AS_OF - timedelta(days=150),
            training_end=AS_OF,
            minimum_matches=20,
            minimum_team_matches=3,
        ),
        now=AS_OF,
    )
    return session.get_one(ModelVersion, view.id)


def _request() -> EvaluateModelRequest:
    return EvaluateModelRequest(
        evaluation_start=AS_OF - timedelta(days=50),
        evaluation_end=AS_OF,
        prediction_lead_minutes=60,
        minimum_training_matches=20,
        calibration_bins=5,
    )


def test_cold_start_flag_preserves_strict_fingerprint_request_payload() -> None:
    strict = _fingerprint_request(_request())
    development = _fingerprint_request(
        _request().model_copy(update={"include_cold_start_benchmark": True})
    )

    assert "include_cold_start_benchmark" not in strict
    assert development["include_cold_start_benchmark"] is True


def test_cold_start_benchmark_is_opt_in_and_does_not_change_primary_eligibility(
    session: Session,
) -> None:
    model = _model(session)
    strict = evaluate_model(session, model.id, _request(), now=AS_OF)
    development_request = _request().model_copy(update={"include_cold_start_benchmark": True})

    development = evaluate_model(session, model.id, development_request, now=AS_OF)

    assert development.id != strict.id
    assert development.metrics["candidate_events"] == 12
    assert development.metrics["evaluated_events"] == 8
    assert "poisson_cold_start" not in strict.benchmarks
    cold_start = development.benchmarks["poisson_cold_start"]
    assert cold_start["version"] == "league-prior-cold-start-poisson-v1"
    assert cold_start["evidence_role"] == "examined_development_benchmark"
    assert cold_start["candidate_events"] == 12
    assert cold_start["evaluated_events"] == 12
    assert cold_start["coverage"] == pytest.approx(1.0)
    assert cold_start["paired_observations"] == 8
    assert cold_start["below_minimum_venue_history_events"] == 4
    assert development.config["development_benchmarks"] == ["league-prior-cold-start-poisson-v1"]


def test_walk_forward_evaluation_persists_immutable_demo_evidence(
    session: Session,
) -> None:
    model = _model(session)

    run = evaluate_model(session, model.id, _request(), now=AS_OF)
    repeated = evaluate_model(session, model.id, _request(), now=AS_OF)

    assert repeated.id == run.id
    assert run.evaluation_status == "demo_only"
    assert run.probability_evaluation_status == "demo_only"
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
    assert run.config["nested_model_selection"] == {
        "version": "chronological-candidate-selection-v1",
        "minimum_history": 60,
        "candidate_grid": {
            "poisson_shrinkage_matches": [3.0, 5.0, 8.0],
            "elo_k_factors": [10.0, 20.0, 30.0],
            "fixed_elo_parameters": {
                "initial_rating": "model_or_default",
                "scale": "model_or_default",
                "home_advantage": "model_or_default",
                "draw_probability_at_even_strength": "model_or_default",
            },
        },
        "selection_objective": "mean_log_loss_then_brier_then_candidate_name",
        "uses_only_prior_held_out_forecasts": True,
    }
    ensemble_config = run.config["chronological_ensemble"]
    assert isinstance(ensemble_config, dict)
    assert ensemble_config["version"] == "chronological-simplex-ensemble-v1"
    assert ensemble_config["models"] == ["poisson", "elo", "dixon_coles"]
    assert ensemble_config["minimum_history"] == 60
    assert ensemble_config["weight_step"] == pytest.approx(0.25)
    assert len(ensemble_config["weight_grid"]) == 12
    assert ensemble_config["requires_multiple_positive_weights"] is True
    assert ensemble_config["uses_only_prior_held_out_forecasts"] is True
    bootstrap_config = run.config["bootstrap"]
    assert isinstance(bootstrap_config, dict)
    assert run.config["evaluation_method_version"] == (
        "expanding-window-block-bootstrap-v6-ensemble"
    )
    assert bootstrap_config["method"] == "moving_block_bootstrap"
    assert bootstrap_config["confidence_level"] == pytest.approx(0.95)
    assert bootstrap_config["resamples"] == 2000
    assert len(str(bootstrap_config["seed_material_sha256"])) == 64
    assert run.policy["version"] == "separated-probability-market-v6"
    checks = run.policy["checks"]
    assert isinstance(checks, dict)
    paired_log_loss = paired["log_loss"]
    assert isinstance(paired_log_loss, dict)
    assert checks["uniform_brier_upper_difference_below_zero"] is (paired_brier["upper"] < 0)
    assert checks["uniform_log_loss_upper_difference_below_zero"] is (paired_log_loss["upper"] < 0)
    assert len(run.calibration) > 0
    session.refresh(model)
    assert model.evaluation_status == "unvalidated"
    assert model.probability_evaluation_status == "unvalidated"
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


def test_elo_primary_evaluation_matches_aligned_benchmark(
    session: Session,
) -> None:
    poisson_run = evaluate_model(session, _model(session).id, _request(), now=AS_OF)
    elo_model = _elo_model(session)

    elo_run = evaluate_model(session, elo_model.id, _request(), now=AS_OF)
    repeated = evaluate_model(session, elo_model.id, _request(), now=AS_OF)

    assert repeated.id == elo_run.id
    assert elo_run.config["primary_benchmark"] == "elo"
    assert elo_run.config["primary_model_kind"] == "davidson_elo"
    assert elo_run.config["evaluation_method_version"] == (
        "expanding-window-block-bootstrap-v6-elo-ensemble"
    )
    assert elo_run.metrics["observations"] == 8
    assert elo_run.metrics["brier_score"] == pytest.approx(
        poisson_run.benchmarks["elo"]["brier_score"]
    )
    assert elo_run.metrics["log_loss"] == pytest.approx(poisson_run.benchmarks["elo"]["log_loss"])
    assert elo_run.benchmarks["poisson"]["brier_score"] == pytest.approx(
        poisson_run.metrics["brier_score"]
    )
    assert "dixon_coles" not in elo_run.benchmarks
    paired = elo_run.benchmarks["poisson"]["paired_loss_difference"]
    assert isinstance(paired, dict)
    assert paired["definition"] == "elo_loss_minus_benchmark_loss"
    assert paired["negative_values_favor"] == "elo"
    assert elo_run.probability_evaluation_status == "demo_only"
    assert elo_model.probability_evaluation_status == "unvalidated"
    assert len(elo_run.calibration) > 0


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
    assert event is not None
    provider = Provider(
        slug="licensed-benchmark-provider",
        name="Licensed benchmark provider",
        kind="licensed_api",
        is_demo=False,
        terms_url="https://example.test/terms",
        capabilities={"odds": True},
    )
    bookmakers = [
        Bookmaker(slug="benchmark-book-a", name="Benchmark Book A", is_demo=False),
        Bookmaker(slug="benchmark-book-b", name="Benchmark Book B", is_demo=False),
    ]
    market = Market(
        event_id=event.id,
        market_type="MATCH_RESULT",
        line=None,
        line_key="",
        period="FULL_TIME",
        currency="EUR",
        settlement_rule_key="standard_90_minutes",
    )
    session.add_all([provider, *bookmakers, market])
    session.flush()
    selections = {
        code: Selection(market_id=market.id, code=code, name=code.title())
        for code in ("HOME", "DRAW", "AWAY")
    }
    session.add_all(selections.values())
    session.flush()
    snapshots: list[OddsSnapshot] = []
    for bookmaker in bookmakers:
        snapshot = OddsSnapshot(
            market_id=market.id,
            bookmaker_id=bookmaker.id,
            provider_id=provider.id,
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
        snapshots.append(snapshot)
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
    assert stored.market_snapshot_ids == [snapshot.id for snapshot in snapshots]
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


def test_promotion_requires_confident_uniform_and_market_superiority() -> None:
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
    market_metrics: dict[str, object] = {
        "observations": 180,
        "coverage": 0.9,
        "paired_loss_difference": {
            "brier_score": {"estimate": -0.01, "lower": -0.02, "upper": -0.001},
            "log_loss": {"estimate": -0.02, "lower": -0.03, "upper": -0.001},
        },
    }
    recalibration_metrics: dict[str, object] = {"activation_status": "accepted"}

    status, probability_status, policy = _policy_decision(
        metrics,
        uniform_metrics,
        market_metrics,
        recalibration_metrics,
        is_demo=False,
    )

    assert status == "calibration_failed"
    assert probability_status == "probability_validation_failed"
    checks = policy["checks"]
    assert isinstance(checks, dict)
    assert checks["uniform_brier_upper_difference_below_zero"] is False
    assert checks["uniform_log_loss_upper_difference_below_zero"] is True

    paired = uniform_metrics["paired_loss_difference"]
    assert isinstance(paired, dict)
    paired["brier_score"] = {"estimate": -0.02, "lower": -0.04, "upper": -0.001}
    status, probability_status, policy = _policy_decision(
        metrics,
        uniform_metrics,
        market_metrics,
        recalibration_metrics,
        is_demo=False,
    )

    assert status == "calibrated"
    assert probability_status == "probability_validated"
    checks = policy["checks"]
    assert isinstance(checks, dict)
    assert all(policy_check is True for policy_check in checks.values())


def test_walk_forward_recalibration_persists_activation_evidence() -> None:
    outcomes = ("HOME", "DRAW", "AWAY")
    rows: list[tuple[dict[str, float], str]] = []
    for index in range(180):
        predicted = outcomes[index % 3]
        actual = outcomes[(index + (1 if index % 4 == 0 else 0)) % 3]
        probabilities = {outcome: 0.05 for outcome in outcomes}
        probabilities[predicted] = 0.90
        rows.append((probabilities, actual))

    metrics = _temperature_recalibration_metrics(
        rows,
        bins=5,
        seed_material="chronological-recalibration-test",
        fit_through=AS_OF,
    )

    assert metrics is not None
    assert metrics["version"] == "development-selected-calibration-v2"
    assert metrics["walk_forward_observations"] == 120
    assert metrics["development_observations"] == 60
    assert metrics["validation_observations"] == 60
    assert metrics["method"] == "scalar_temperature_scaling"
    assert metrics["activation_status"] == "accepted"
    checks = metrics["activation_checks"]
    assert isinstance(checks, dict) and all(checks.values())
    final = metrics["final_calibrator"]
    assert isinstance(final, dict)
    assert final["temperature"] > 1
    assert final["sample_size"] == 180
    assert len(str(final["input_fingerprint"])) == 64
    assert final["fit_through"] == AS_OF.isoformat()


def test_walk_forward_recalibration_selects_identity_on_development_data() -> None:
    probabilities = {"HOME": 0.6, "DRAW": 0.3, "AWAY": 0.1}
    actuals = ("HOME",) * 6 + ("DRAW",) * 3 + ("AWAY",)
    rows = [(probabilities, actuals[index % 10]) for index in range(180)]

    metrics = _temperature_recalibration_metrics(
        rows,
        bins=5,
        seed_material="identity-calibration-test",
        fit_through=AS_OF,
    )

    assert metrics is not None
    assert metrics["method"] == "identity"
    assert metrics["activation_status"] == "accepted"
    selection = metrics["development_selection"]
    assert isinstance(selection, dict)
    assert selection["selected_method"] == "identity"
    final = metrics["final_calibrator"]
    assert isinstance(final, dict)
    assert final["method"] == "identity"
    assert final["temperature"] == 1.0
    checks = metrics["activation_checks"]
    assert isinstance(checks, dict) and all(checks.values())


def test_promotion_fails_closed_without_adequate_market_coverage() -> None:
    metrics: dict[str, object] = {
        "observations": 220,
        "coverage": 0.95,
        "expected_calibration_error": 0.04,
    }
    strong_comparison = {
        "paired_loss_difference": {
            "brier_score": {"estimate": -0.02, "lower": -0.03, "upper": -0.001},
            "log_loss": {"estimate": -0.02, "lower": -0.03, "upper": -0.001},
        }
    }
    uniform_metrics: dict[str, object] = dict(strong_comparison)

    recalibration_metrics: dict[str, object] = {"activation_status": "accepted"}
    status, probability_status, policy = _policy_decision(
        metrics, uniform_metrics, None, recalibration_metrics, is_demo=False
    )

    assert status == "insufficient_market_evidence"
    assert probability_status == "probability_validated"
    assert policy["probability_decision"] == "probability_validated"
    assert policy["market_decision"] == "insufficient_market_evidence"
    checks = policy["checks"]
    assert isinstance(checks, dict)
    assert checks["market_benchmark_available"] is False

    market_metrics: dict[str, object] = {
        **strong_comparison,
        "observations": 159,
        "coverage": 0.79,
    }
    status, probability_status, policy = _policy_decision(
        metrics,
        uniform_metrics,
        market_metrics,
        recalibration_metrics,
        is_demo=False,
    )

    assert status == "insufficient_market_evidence"
    assert probability_status == "probability_validated"
    checks = policy["checks"]
    assert isinstance(checks, dict)
    assert checks["minimum_market_observations"] is False
    assert checks["minimum_market_coverage"] is False


def test_market_loss_uncertainty_can_block_promotion() -> None:
    metrics: dict[str, object] = {
        "observations": 220,
        "coverage": 0.95,
        "expected_calibration_error": 0.04,
    }
    uniform_metrics: dict[str, object] = {
        "paired_loss_difference": {
            "brier_score": {"estimate": -0.02, "lower": -0.03, "upper": -0.001},
            "log_loss": {"estimate": -0.02, "lower": -0.03, "upper": -0.001},
        }
    }
    market_metrics: dict[str, object] = {
        "observations": 180,
        "coverage": 0.82,
        "paired_loss_difference": {
            "brier_score": {"estimate": -0.01, "lower": -0.02, "upper": 0.002},
            "log_loss": {"estimate": -0.01, "lower": -0.02, "upper": -0.001},
        },
    }

    status, probability_status, policy = _policy_decision(
        metrics,
        uniform_metrics,
        market_metrics,
        {"activation_status": "accepted"},
        is_demo=False,
    )

    assert status == "calibration_failed"
    assert probability_status == "probability_validated"
    checks = policy["checks"]
    assert isinstance(checks, dict)
    assert checks["market_brier_upper_difference_below_zero"] is False
    assert checks["market_log_loss_upper_difference_below_zero"] is True


def test_promotion_requires_accepted_chronological_recalibration() -> None:
    metrics: dict[str, object] = {
        "observations": 220,
        "coverage": 0.95,
        "expected_calibration_error": 0.04,
    }
    comparison = {
        "paired_loss_difference": {
            "brier_score": {"estimate": -0.02, "lower": -0.03, "upper": -0.001},
            "log_loss": {"estimate": -0.02, "lower": -0.03, "upper": -0.001},
        }
    }
    uniform_metrics: dict[str, object] = dict(comparison)
    market_metrics: dict[str, object] = {
        **comparison,
        "observations": 180,
        "coverage": 0.82,
    }

    status, probability_status, policy = _policy_decision(
        metrics, uniform_metrics, market_metrics, None, is_demo=False
    )

    assert status == "insufficient_recalibration_evidence"
    assert probability_status == "insufficient_recalibration_evidence"
    checks = policy["checks"]
    assert isinstance(checks, dict)
    assert checks["chronological_recalibration_accepted"] is False
