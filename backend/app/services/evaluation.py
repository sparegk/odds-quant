from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
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
from app.quant.calibration import (
    PROMOTION_POLICY_VERSION,
    RECALIBRATION_VERSION,
    fit_temperature_calibrator,
    walk_forward_temperature_scaling,
)
from app.quant.dixon_coles import DixonColesMatch, fit_dixon_coles
from app.quant.elo import EloConfig, EloMatchResult, elo_probabilities_as_of
from app.quant.evaluation import (
    OUTCOMES,
    CalibrationBucket,
    moving_block_mean_interval,
    multiclass_brier,
    multiclass_log_loss,
    summarize_probabilities,
)
from app.quant.model_selection import (
    NESTED_SELECTION_VERSION,
    walk_forward_candidate_selection,
)
from app.quant.odds import devig_proportional
from app.quant.poisson import derive_market, score_matrix
from app.quant.team_strength import HistoricalScore, fit_poisson_team_strength
from app.schemas.models import CalibrationBucketView, EvaluateModelRequest, EvaluationRunView
from app.services.modeling import ELO_MODEL_KIND, MODEL_KIND, competition_family_ids

MINIMUM_PROMOTION_OBSERVATIONS = 200
MINIMUM_PROMOTION_COVERAGE = 0.90
MINIMUM_MARKET_PROMOTION_OBSERVATIONS = 160
MINIMUM_MARKET_PROMOTION_COVERAGE = 0.80
MINIMUM_MARKET_BOOKMAKERS = 2
MARKET_BENCHMARK_MAX_AGE = timedelta(hours=24)
MAXIMUM_PROMOTION_ECE = 0.08
BOOTSTRAP_CONFIDENCE_LEVEL = 0.95
BOOTSTRAP_RESAMPLES = 2000
EVALUATION_METHOD_VERSION = "expanding-window-block-bootstrap-v5-nested-selection"
ELO_EVALUATION_METHOD_VERSION = "expanding-window-block-bootstrap-v5-elo-nested-selection"
MINIMUM_RECALIBRATION_HISTORY = 60
MINIMUM_RECALIBRATION_EVALUATION_OBSERVATIONS = 100
MINIMUM_RECALIBRATION_VALIDATION_OBSERVATIONS = 50
CALIBRATION_SELECTION_MINIMUM_IMPROVEMENT = 1e-4
NESTED_SELECTION_MINIMUM_HISTORY = 60
NESTED_POISSON_SHRINKAGES = (3.0, 5.0, 8.0)
NESTED_ELO_K_FACTORS = (10.0, 20.0, 30.0)


PROMOTION_POLICY: dict[str, object] = {
    "version": PROMOTION_POLICY_VERSION,
    "minimum_observations": MINIMUM_PROMOTION_OBSERVATIONS,
    "minimum_coverage": MINIMUM_PROMOTION_COVERAGE,
    "maximum_expected_calibration_error": MAXIMUM_PROMOTION_ECE,
    "minimum_market_observations": MINIMUM_MARKET_PROMOTION_OBSERVATIONS,
    "minimum_market_coverage": MINIMUM_MARKET_PROMOTION_COVERAGE,
    "minimum_market_bookmakers_per_event": MINIMUM_MARKET_BOOKMAKERS,
    "market_benchmark_max_age_seconds": int(MARKET_BENCHMARK_MAX_AGE.total_seconds()),
    "bootstrap_confidence_level": BOOTSTRAP_CONFIDENCE_LEVEL,
    "require_uniform_brier_upper_difference_below_zero": True,
    "require_uniform_log_loss_upper_difference_below_zero": True,
    "require_market_brier_upper_difference_below_zero": True,
    "require_market_log_loss_upper_difference_below_zero": True,
    "recalibration_version": RECALIBRATION_VERSION,
    "minimum_recalibration_history": MINIMUM_RECALIBRATION_HISTORY,
    "minimum_recalibration_evaluation_observations": (
        MINIMUM_RECALIBRATION_EVALUATION_OBSERVATIONS
    ),
    "minimum_recalibration_validation_observations": (
        MINIMUM_RECALIBRATION_VALIDATION_OBSERVATIONS
    ),
    "recalibration_selection": "earlier_development_partition",
    "recalibration_identity_fallback": True,
    "recalibration_selection_minimum_improvement": CALIBRATION_SELECTION_MINIMUM_IMPROVEMENT,
    "require_chronological_recalibration_acceptance": True,
    "demo_data_eligible": False,
}


class EvaluationError(ValueError):
    pass


@dataclass(frozen=True)
class _ReplayObservation:
    event: Event
    result: MatchResult
    predicted_at: datetime
    training_sample_size: int
    training_fingerprint: str
    probabilities: dict[str, float]
    actual_outcome: str
    brier_score: float
    log_loss: float
    poisson_probabilities: dict[str, float]
    elo_probabilities: dict[str, float]
    dixon_coles_probabilities: dict[str, float] | None
    nested_candidate_probabilities: dict[str, dict[str, float]]
    market_snapshot_ids: list[int]
    market_probabilities: dict[str, float] | None
    market_brier_score: float | None
    market_log_loss: float | None


def evaluate_model(
    session: Session,
    model_id: int,
    request: EvaluateModelRequest,
    *,
    now: datetime | None = None,
) -> EvaluationRunView:
    reference = _utc(now or datetime.now(UTC))
    evaluation_start = _utc(request.evaluation_start)
    evaluation_end = _utc(request.evaluation_end)
    if evaluation_end > reference:
        raise EvaluationError("evaluation_end cannot be in the future")
    model = session.get(ModelVersion, model_id)
    if model is None:
        raise EvaluationError("model version not found")
    if model.kind not in {MODEL_KIND, ELO_MODEL_KIND} or model.status != "trained":
        raise EvaluationError("model version is not a trained supported team-strength model")

    competition_id = _config_int(model.config, "competition_id")
    minimum_team_matches = _config_int(model.config, "minimum_team_matches")
    primary_benchmark = "elo" if model.kind == ELO_MODEL_KIND else "poisson"
    evaluation_method_version = (
        ELO_EVALUATION_METHOD_VERSION if model.kind == ELO_MODEL_KIND else EVALUATION_METHOD_VERSION
    )
    shrinkage_matches = (
        _config_number(model.config, "shrinkage_matches") if model.kind == MODEL_KIND else 5.0
    )
    elo_config = (
        EloConfig(
            initial_rating=_config_number(model.config, "initial_rating"),
            k_factor=_config_number(model.config, "k_factor"),
            scale=_config_number(model.config, "scale"),
            home_advantage=_config_number(model.config, "home_advantage"),
            draw_probability_at_even_strength=_config_number(
                model.config, "draw_probability_at_even_strength"
            ),
        )
        if model.kind == ELO_MODEL_KIND
        else EloConfig()
    )
    candidate_rows = _evaluation_observations(
        session,
        competition_id=competition_id,
        evaluation_start=evaluation_start,
        evaluation_end=evaluation_end,
        known_at=reference,
    )
    if not candidate_rows:
        raise EvaluationError("no final results exist in the evaluation window")

    replayed: list[_ReplayObservation] = []
    exclusions: dict[str, int] = {}
    for result, event in candidate_rows:
        predicted_at = _utc(event.kickoff_at) - timedelta(minutes=request.prediction_lead_minutes)
        training_rows = _training_observations(
            session,
            competition_id=competition_id,
            training_start=_utc(model.training_start),
            training_end=predicted_at,
        )
        if len(training_rows) < request.minimum_training_matches:
            _increment(exclusions, "insufficient_training_matches")
            continue
        scores = [
            HistoricalScore(
                home_team_id=training_event.home_team_id,
                away_team_id=training_event.away_team_id,
                home_goals=training_result.home_goals,
                away_goals=training_result.away_goals,
            )
            for training_result, training_event in training_rows
        ]
        elo_history = [
            EloMatchResult(
                event_id=training_event.id,
                home_team_id=training_event.home_team_id,
                away_team_id=training_event.away_team_id,
                kickoff_at=_utc(training_event.kickoff_at),
                observed_at=_utc(training_result.observed_at),
                home_goals=training_result.home_goals,
                away_goals=training_result.away_goals,
            )
            for training_result, training_event in training_rows
        ]
        dixon_coles_history = [
            DixonColesMatch(
                event_id=training_event.id,
                home_team_id=training_event.home_team_id,
                away_team_id=training_event.away_team_id,
                kickoff_at=_utc(training_event.kickoff_at),
                observed_at=_utc(training_result.observed_at),
                home_goals=training_result.home_goals,
                away_goals=training_result.away_goals,
            )
            for training_result, training_event in training_rows
        ]
        fitted = fit_poisson_team_strength(scores, shrinkage_matches=shrinkage_matches)
        home = fitted.teams.get(event.home_team_id)
        away = fitted.teams.get(event.away_team_id)
        if home is None or home.home_matches < minimum_team_matches:
            _increment(exclusions, "insufficient_home_venue_history")
            continue
        if away is None or away.away_matches < minimum_team_matches:
            _increment(exclusions, "insufficient_away_venue_history")
            continue

        home_lambda, away_lambda = fitted.expected_goals(event.home_team_id, event.away_team_id)
        poisson_probabilities = derive_market(
            score_matrix(home_lambda, away_lambda), "MATCH_RESULT"
        )
        elo_probabilities = elo_probabilities_as_of(
            elo_history,
            home_team_id=event.home_team_id,
            away_team_id=event.away_team_id,
            as_of=predicted_at,
            config=elo_config,
        ).probabilities
        probabilities = elo_probabilities if primary_benchmark == "elo" else poisson_probabilities
        dixon_coles_probabilities = (
            fit_dixon_coles(
                dixon_coles_history,
                as_of=predicted_at,
            ).probabilities(event.home_team_id, event.away_team_id)
            if primary_benchmark == "poisson"
            else None
        )
        nested_candidate_probabilities = _nested_candidate_probabilities(
            scores,
            elo_history,
            home_team_id=event.home_team_id,
            away_team_id=event.away_team_id,
            predicted_at=predicted_at,
            elo_config=elo_config,
        )
        actual_outcome = _actual_outcome(result)
        market_snapshot_ids, market_probabilities = _market_consensus(
            session, event.id, predicted_at
        )
        replayed.append(
            _ReplayObservation(
                event=event,
                result=result,
                predicted_at=predicted_at,
                training_sample_size=len(training_rows),
                training_fingerprint=_training_fingerprint(training_rows),
                probabilities=probabilities,
                actual_outcome=actual_outcome,
                brier_score=multiclass_brier(probabilities, actual_outcome),
                log_loss=multiclass_log_loss(probabilities, actual_outcome),
                poisson_probabilities=poisson_probabilities,
                elo_probabilities=elo_probabilities,
                dixon_coles_probabilities=dixon_coles_probabilities,
                nested_candidate_probabilities=nested_candidate_probabilities,
                market_snapshot_ids=market_snapshot_ids,
                market_probabilities=market_probabilities,
                market_brier_score=(
                    multiclass_brier(market_probabilities, actual_outcome)
                    if market_probabilities is not None
                    else None
                ),
                market_log_loss=(
                    multiclass_log_loss(market_probabilities, actual_outcome)
                    if market_probabilities is not None
                    else None
                ),
            )
        )
    if not replayed:
        raise EvaluationError(
            "no events were eligible for replay; inspect training and team-history requirements"
        )

    probability_rows = [
        (observation.probabilities, observation.actual_outcome) for observation in replayed
    ]
    bootstrap_seed_material = _bootstrap_seed_material(
        replayed, primary_benchmark=primary_benchmark
    )
    metrics, buckets = summarize_probabilities(probability_rows, bins=request.calibration_bins)
    _attach_score_intervals(
        metrics,
        probability_rows,
        seed_material=bootstrap_seed_material,
        namespace=primary_benchmark,
    )
    metrics.update(
        {
            "candidate_events": len(candidate_rows),
            "evaluated_events": len(replayed),
            "coverage": len(replayed) / len(candidate_rows),
            "excluded_events": exclusions,
            "prediction_lead_minutes": request.prediction_lead_minutes,
        }
    )
    uniform_rows = [
        ({outcome: 1 / 3 for outcome in OUTCOMES}, actual) for _, actual in probability_rows
    ]
    uniform_metrics, _ = summarize_probabilities(uniform_rows, bins=request.calibration_bins)
    _attach_score_intervals(
        uniform_metrics, uniform_rows, seed_material=bootstrap_seed_material, namespace="uniform"
    )
    _attach_paired_loss_difference(
        uniform_metrics,
        probability_rows,
        uniform_rows,
        seed_material=bootstrap_seed_material,
        namespace="uniform",
        primary_name=primary_benchmark,
    )
    benchmark_metrics: dict[str, dict[str, object]] = {"uniform": uniform_metrics}
    elo_rows = [
        (observation.elo_probabilities, observation.actual_outcome) for observation in replayed
    ]
    if primary_benchmark == "poisson":
        elo_metrics, _ = summarize_probabilities(elo_rows, bins=request.calibration_bins)
        _attach_score_intervals(
            elo_metrics, elo_rows, seed_material=bootstrap_seed_material, namespace="elo"
        )
        _attach_paired_loss_difference(
            elo_metrics,
            probability_rows,
            elo_rows,
            seed_material=bootstrap_seed_material,
            namespace="elo",
        )
        benchmark_metrics["elo"] = elo_metrics
        dixon_coles_rows = [
            (dixon_probabilities, observation.actual_outcome)
            for observation in replayed
            if (dixon_probabilities := observation.dixon_coles_probabilities) is not None
        ]
        dixon_coles_metrics, _ = summarize_probabilities(
            dixon_coles_rows, bins=request.calibration_bins
        )
        _attach_score_intervals(
            dixon_coles_metrics,
            dixon_coles_rows,
            seed_material=bootstrap_seed_material,
            namespace="dixon_coles",
        )
        _attach_paired_loss_difference(
            dixon_coles_metrics,
            probability_rows,
            dixon_coles_rows,
            seed_material=bootstrap_seed_material,
            namespace="dixon_coles",
        )
        benchmark_metrics["dixon_coles"] = dixon_coles_metrics
    else:
        poisson_rows = [
            (observation.poisson_probabilities, observation.actual_outcome)
            for observation in replayed
        ]
        poisson_metrics, _ = summarize_probabilities(poisson_rows, bins=request.calibration_bins)
        _attach_score_intervals(
            poisson_metrics,
            poisson_rows,
            seed_material=bootstrap_seed_material,
            namespace="poisson",
        )
        _attach_paired_loss_difference(
            poisson_metrics,
            probability_rows,
            poisson_rows,
            seed_material=bootstrap_seed_material,
            namespace="poisson",
            primary_name=primary_benchmark,
        )
        benchmark_metrics["poisson"] = poisson_metrics
    nested_inputs = [
        (observation.nested_candidate_probabilities, observation.actual_outcome)
        for observation in replayed
    ]
    nested_selected = walk_forward_candidate_selection(
        nested_inputs,
        minimum_history=NESTED_SELECTION_MINIMUM_HISTORY,
    )
    if nested_selected:
        nested_rows = [
            (selected.probabilities, replayed[selected.index].actual_outcome)
            for selected in nested_selected
        ]
        nested_primary_rows = [
            (replayed[selected.index].probabilities, replayed[selected.index].actual_outcome)
            for selected in nested_selected
        ]
        nested_metrics, _ = summarize_probabilities(nested_rows, bins=request.calibration_bins)
        _attach_score_intervals(
            nested_metrics,
            nested_rows,
            seed_material=bootstrap_seed_material,
            namespace="nested_selected",
        )
        _attach_paired_loss_difference(
            nested_metrics,
            nested_primary_rows,
            nested_rows,
            seed_material=bootstrap_seed_material,
            namespace="nested_selected",
            primary_name=primary_benchmark,
        )
        selection_counts: dict[str, int] = {}
        for selected in nested_selected:
            _increment(selection_counts, selected.candidate)
        nested_metrics.update(
            {
                "version": NESTED_SELECTION_VERSION,
                "selection_objective": "mean_log_loss_then_brier_then_candidate_name",
                "minimum_history": NESTED_SELECTION_MINIMUM_HISTORY,
                "candidate_grid": _nested_candidate_grid(),
                "selection_counts": selection_counts,
                "first_history_fingerprint": nested_selected[0].history_fingerprint,
                "last_history_fingerprint": nested_selected[-1].history_fingerprint,
            }
        )
        benchmark_metrics["nested_selected"] = nested_metrics
    market_pairs = [
        (
            observation.probabilities,
            observation.market_probabilities,
            observation.actual_outcome,
        )
        for observation in replayed
        if observation.market_probabilities is not None
    ]
    market_metrics: dict[str, object] | None = None
    if market_pairs:
        market_model_rows = [(model_row, actual) for model_row, _, actual in market_pairs]
        market_rows = [(market_row, actual) for _, market_row, actual in market_pairs]
        market_metrics, _ = summarize_probabilities(market_rows, bins=request.calibration_bins)
        market_metrics["coverage"] = len(market_rows) / len(replayed)
        _attach_score_intervals(
            market_metrics,
            market_rows,
            seed_material=bootstrap_seed_material,
            namespace="market_consensus",
        )
        _attach_paired_loss_difference(
            market_metrics,
            market_model_rows,
            market_rows,
            seed_material=bootstrap_seed_material,
            namespace="market_consensus",
            primary_name=primary_benchmark,
        )

    recalibration_metrics = _temperature_recalibration_metrics(
        probability_rows,
        bins=request.calibration_bins,
        seed_material=bootstrap_seed_material,
        fit_through=evaluation_end,
        primary_name=primary_benchmark,
    )

    is_demo = bool(model.is_demo or any(row.event.is_demo for row in replayed))
    evaluation_status, probability_evaluation_status, policy = _policy_decision(
        metrics,
        uniform_metrics,
        market_metrics,
        recalibration_metrics,
        is_demo=is_demo,
    )
    fingerprint = _evaluation_fingerprint(
        model=model,
        request=request,
        replayed=replayed,
        evaluation_status=evaluation_status,
        probability_evaluation_status=probability_evaluation_status,
        evaluation_method_version=evaluation_method_version,
    )
    existing = session.scalar(select(BacktestRun).where(BacktestRun.fingerprint == fingerprint))
    if existing is not None:
        return _run_view(session, existing)

    config: dict[str, object] = {
        "evaluation_kind": "expanding_window_match_result",
        "evaluation_method_version": evaluation_method_version,
        "primary_benchmark": primary_benchmark,
        "primary_model_kind": model.kind,
        "competition_id": competition_id,
        "training_start": _utc(model.training_start).isoformat(),
        "evaluation_start": evaluation_start.isoformat(),
        "evaluation_end": evaluation_end.isoformat(),
        "prediction_lead_minutes": request.prediction_lead_minutes,
        "minimum_training_matches": request.minimum_training_matches,
        "minimum_team_matches": minimum_team_matches,
        "shrinkage_matches": shrinkage_matches,
        "calibration_bins": request.calibration_bins,
        "result_known_at": reference.isoformat(),
        "outcomes": list(OUTCOMES),
        "brier_definition": "sum_squared_error_over_three_outcomes_range_0_to_2",
        "bootstrap": {
            "method": "moving_block_bootstrap",
            "confidence_level": BOOTSTRAP_CONFIDENCE_LEVEL,
            "resamples": BOOTSTRAP_RESAMPLES,
            "block_length_rule": "round_cube_root_sample_size_minimum_1",
            "seed_derivation": "sha256_seed_material_and_metric_namespace",
            "seed_material_sha256": bootstrap_seed_material,
            "paired_difference_definition": (f"{primary_benchmark}_loss_minus_benchmark_loss"),
        },
        "market_benchmark": "mean_proportional_devig_of_latest_compatible_snapshot_per_bookmaker",
        "probability_recalibration": {
            "version": RECALIBRATION_VERSION,
            "candidates": ["scalar_temperature_scaling", "identity"],
            "minimum_history": MINIMUM_RECALIBRATION_HISTORY,
            "fit_schedule": "expanding_window_refit_before_each_held_out_prediction",
            "selection_partition": "earlier_half_of_walk_forward_observations",
            "validation_partition": "later_untouched_half_of_walk_forward_observations",
            "activation_rule": "selected_method_must_not_degrade_untouched_validation",
        },
        "nested_model_selection": {
            "version": NESTED_SELECTION_VERSION,
            "minimum_history": NESTED_SELECTION_MINIMUM_HISTORY,
            "candidate_grid": _nested_candidate_grid(),
            "selection_objective": "mean_log_loss_then_brier_then_candidate_name",
            "uses_only_prior_held_out_forecasts": True,
        },
        "elo_benchmark": {
            "version": "davidson-elo-v1",
            **elo_config.__dict__,
        },
        **(
            {
                "dixon_coles_benchmark": {
                    "version": "time-decayed-dixon-coles-v1",
                    "decay_rate": 0.0018,
                    "low_score_rho_bounds": [-0.2, 0.2],
                }
            }
            if primary_benchmark == "poisson"
            else {}
        ),
    }
    run = BacktestRun(
        model_version_id=model.id,
        status="completed",
        train_end=evaluation_start,
        validation_end=evaluation_start,
        test_end=evaluation_end,
        fingerprint=fingerprint,
        config=config,
        policy=policy,
        probability_evaluation_status=probability_evaluation_status,
        evaluation_status=evaluation_status,
        is_demo=is_demo,
    )
    session.add(run)
    session.flush()
    for observation in replayed:
        session.add(
            BacktestObservation(
                run_id=run.id,
                event_id=observation.event.id,
                selection_id=None,
                odds_snapshot_id=None,
                prediction_id=None,
                result_id=observation.result.id,
                predicted_at=observation.predicted_at,
                training_cutoff=observation.predicted_at,
                training_sample_size=observation.training_sample_size,
                training_fingerprint=observation.training_fingerprint,
                market_type="MATCH_RESULT",
                probabilities=observation.probabilities,
                actual_outcome=observation.actual_outcome,
                brier_score=observation.brier_score,
                log_loss=observation.log_loss,
                market_snapshot_ids=observation.market_snapshot_ids,
                market_probabilities=observation.market_probabilities,
                market_brier_score=observation.market_brier_score,
                market_log_loss=observation.market_log_loss,
                settled_at=_utc(observation.result.settled_at),
                settlement=observation.actual_outcome,
                stake=0,
                profit_units=None,
                closing_line_value=None,
            )
        )
    _persist_results(
        session,
        run_id=run.id,
        primary_benchmark=primary_benchmark,
        metrics=metrics,
        benchmark_metrics=benchmark_metrics,
        market_metrics=market_metrics,
        recalibration_metrics=recalibration_metrics,
        buckets=buckets,
    )
    if probability_evaluation_status == "probability_validated":
        model.probability_evaluation_status = "probability_validated"
        model.metrics = {
            **model.metrics,
            "held_out_evaluation": True,
            "latest_probability_evaluation_run_id": run.id,
            "held_out_metrics": metrics,
        }
    if evaluation_status == "calibrated":
        model.evaluation_status = "calibrated"
        model.metrics = {
            **model.metrics,
            "latest_evaluation_run_id": run.id,
        }
    session.commit()
    return _run_view(session, run)


def list_evaluations(session: Session, *, model_id: int | None = None) -> list[EvaluationRunView]:
    statement = select(BacktestRun).order_by(BacktestRun.created_at.desc(), BacktestRun.id.desc())
    if model_id is not None:
        statement = statement.where(BacktestRun.model_version_id == model_id)
    runs = [run for run in session.scalars(statement).all() if _is_calibration_run(run)]
    return [_run_view(session, run) for run in runs]


def get_evaluation(session: Session, run_id: int) -> EvaluationRunView | None:
    run = session.get(BacktestRun, run_id)
    return _run_view(session, run) if run is not None and _is_calibration_run(run) else None


def _is_calibration_run(run: BacktestRun) -> bool:
    return run.config.get("evaluation_kind") == "expanding_window_match_result"


def _evaluation_observations(
    session: Session,
    *,
    competition_id: int,
    evaluation_start: datetime,
    evaluation_end: datetime,
    known_at: datetime,
) -> list[tuple[MatchResult, Event]]:
    rows = session.execute(
        select(MatchResult, Event)
        .join(Event, Event.id == MatchResult.event_id)
        .where(
            Event.competition_id == competition_id,
            Event.kickoff_at >= evaluation_start,
            Event.kickoff_at < evaluation_end,
            MatchResult.is_final.is_(True),
            MatchResult.observed_at >= Event.kickoff_at,
            MatchResult.settled_at >= Event.kickoff_at,
            MatchResult.observed_at <= known_at,
            MatchResult.settled_at <= known_at,
        )
        .order_by(MatchResult.observed_at, MatchResult.id)
    ).all()
    latest_by_event: dict[int, tuple[MatchResult, Event]] = {}
    for result, event in rows:
        latest_by_event[event.id] = (result, event)
    canonical: dict[tuple[datetime, int, int], tuple[MatchResult, Event]] = {}
    for result, event in latest_by_event.values():
        key = (_utc(event.kickoff_at), event.home_team_id, event.away_team_id)
        existing = canonical.get(key)
        if existing is not None and (
            existing[0].home_goals,
            existing[0].away_goals,
        ) != (result.home_goals, result.away_goals):
            raise EvaluationError(
                "conflicting final scores exist for the same canonical evaluation event"
            )
        if existing is None or _utc(result.observed_at) > _utc(existing[0].observed_at):
            canonical[key] = (result, event)
    return sorted(canonical.values(), key=lambda row: (_utc(row[1].kickoff_at), row[1].id))


def _training_observations(
    session: Session,
    *,
    competition_id: int,
    training_start: datetime,
    training_end: datetime,
) -> list[tuple[MatchResult, Event]]:
    competition = session.get(Competition, competition_id)
    if competition is None:
        raise EvaluationError("competition not found")
    competition_ids = competition_family_ids(session, competition)
    rows = session.execute(
        select(MatchResult, Event)
        .join(Event, Event.id == MatchResult.event_id)
        .where(
            Event.competition_id.in_(competition_ids),
            Event.kickoff_at >= training_start,
            Event.kickoff_at < training_end,
            MatchResult.is_final.is_(True),
            MatchResult.observed_at >= Event.kickoff_at,
            MatchResult.settled_at >= Event.kickoff_at,
            MatchResult.observed_at <= training_end,
            MatchResult.settled_at <= training_end,
        )
        .order_by(MatchResult.observed_at, MatchResult.id)
    ).all()
    latest_by_event: dict[int, tuple[MatchResult, Event]] = {}
    for result, event in rows:
        latest_by_event[event.id] = (result, event)
    canonical: dict[tuple[datetime, int, int], tuple[MatchResult, Event]] = {}
    for result, event in latest_by_event.values():
        key = (_utc(event.kickoff_at), event.home_team_id, event.away_team_id)
        existing = canonical.get(key)
        if existing is not None and (
            existing[0].home_goals,
            existing[0].away_goals,
        ) != (result.home_goals, result.away_goals):
            raise EvaluationError("conflicting scores exist in a replay training window")
        if existing is None or _utc(result.observed_at) > _utc(existing[0].observed_at):
            canonical[key] = (result, event)
    return sorted(canonical.values(), key=lambda row: (_utc(row[1].kickoff_at), row[1].id))


def _market_consensus(
    session: Session, event_id: int, predicted_at: datetime
) -> tuple[list[int], dict[str, float] | None]:
    rows = session.execute(
        select(Market, OddsSnapshot, OddsPrice, Selection)
        .join(OddsSnapshot, OddsSnapshot.market_id == Market.id)
        .join(OddsPrice, OddsPrice.snapshot_id == OddsSnapshot.id)
        .join(Selection, Selection.id == OddsPrice.selection_id)
        .join(Bookmaker, Bookmaker.id == OddsSnapshot.bookmaker_id)
        .join(Provider, Provider.id == OddsSnapshot.provider_id)
        .where(
            Market.event_id == event_id,
            Market.market_type == "MATCH_RESULT",
            Market.line.is_(None),
            Market.period == "FULL_TIME",
            OddsSnapshot.is_complete.is_(True),
            OddsSnapshot.observed_at <= predicted_at,
            OddsSnapshot.observed_at >= predicted_at - MARKET_BENCHMARK_MAX_AGE,
            Bookmaker.is_demo.is_(False),
            Provider.is_demo.is_(False),
        )
        .order_by(OddsSnapshot.observed_at, OddsSnapshot.id, Selection.id)
    ).all()
    snapshots: dict[int, tuple[Market, OddsSnapshot, dict[str, float]]] = {}
    for market, snapshot, price, selection in rows:
        stored = snapshots.setdefault(snapshot.id, (market, snapshot, {}))
        stored[2][selection.code] = float(price.decimal_odds)
    latest: dict[tuple[int, int], tuple[Market, OddsSnapshot, dict[str, float]]] = {}
    for market, snapshot, prices in snapshots.values():
        if set(prices) != set(OUTCOMES):
            continue
        key = (market.id, snapshot.bookmaker_id)
        existing = latest.get(key)
        if existing is None or (_utc(snapshot.observed_at), snapshot.id) > (
            _utc(existing[1].observed_at),
            existing[1].id,
        ):
            latest[key] = (market, snapshot, prices)
    by_market: dict[int, list[tuple[Market, OddsSnapshot, dict[str, float]]]] = {}
    for row in latest.values():
        by_market.setdefault(row[0].id, []).append(row)
    if not by_market:
        return ([], None)
    chosen = max(
        by_market.values(),
        key=lambda group: (
            len(group),
            max((_utc(row[1].observed_at), row[1].id) for row in group),
            -group[0][0].id,
        ),
    )
    if len(chosen) < MINIMUM_MARKET_BOOKMAKERS:
        return ([], None)
    devigged: list[dict[str, float]] = []
    for _, _, prices in chosen:
        ordered_odds = [prices[outcome] for outcome in OUTCOMES]
        probabilities = devig_proportional(ordered_odds)
        devigged.append(dict(zip(OUTCOMES, probabilities, strict=True)))
    consensus = {
        outcome: sum(row[outcome] for row in devigged) / len(devigged) for outcome in OUTCOMES
    }
    return (sorted(row[1].id for row in chosen), consensus)


def _attach_score_intervals(
    metrics: dict[str, object],
    rows: list[tuple[dict[str, float], str]],
    *,
    seed_material: str,
    namespace: str,
) -> None:
    brier_losses = [multiclass_brier(probabilities, actual) for probabilities, actual in rows]
    log_losses = [multiclass_log_loss(probabilities, actual) for probabilities, actual in rows]
    metrics["score_intervals"] = {
        "brier_score": moving_block_mean_interval(
            brier_losses,
            confidence_level=BOOTSTRAP_CONFIDENCE_LEVEL,
            resamples=BOOTSTRAP_RESAMPLES,
            seed=_derived_bootstrap_seed(seed_material, f"{namespace}:brier_score"),
        ).as_dict(),
        "log_loss": moving_block_mean_interval(
            log_losses,
            confidence_level=BOOTSTRAP_CONFIDENCE_LEVEL,
            resamples=BOOTSTRAP_RESAMPLES,
            seed=_derived_bootstrap_seed(seed_material, f"{namespace}:log_loss"),
        ).as_dict(),
    }


def _attach_paired_loss_difference(
    metrics: dict[str, object],
    primary_rows: list[tuple[dict[str, float], str]],
    benchmark_rows: list[tuple[dict[str, float], str]],
    *,
    seed_material: str,
    namespace: str,
    primary_name: str = "poisson",
) -> None:
    if len(primary_rows) != len(benchmark_rows) or not primary_rows:
        raise EvaluationError("paired benchmark comparison requires aligned observations")
    brier_differences: list[float] = []
    log_loss_differences: list[float] = []
    for (primary_probabilities, primary_actual), (benchmark_probabilities, actual) in zip(
        primary_rows, benchmark_rows, strict=True
    ):
        if primary_actual != actual:
            raise EvaluationError("paired benchmark comparison outcomes are not aligned")
        brier_differences.append(
            multiclass_brier(primary_probabilities, actual)
            - multiclass_brier(benchmark_probabilities, actual)
        )
        log_loss_differences.append(
            multiclass_log_loss(primary_probabilities, actual)
            - multiclass_log_loss(benchmark_probabilities, actual)
        )
    metrics["paired_loss_difference"] = {
        "definition": f"{primary_name}_loss_minus_benchmark_loss",
        "negative_values_favor": primary_name,
        "brier_score": moving_block_mean_interval(
            brier_differences,
            confidence_level=BOOTSTRAP_CONFIDENCE_LEVEL,
            resamples=BOOTSTRAP_RESAMPLES,
            seed=_derived_bootstrap_seed(seed_material, f"{namespace}:paired_brier_score"),
        ).as_dict(),
        "log_loss": moving_block_mean_interval(
            log_loss_differences,
            confidence_level=BOOTSTRAP_CONFIDENCE_LEVEL,
            resamples=BOOTSTRAP_RESAMPLES,
            seed=_derived_bootstrap_seed(seed_material, f"{namespace}:paired_log_loss"),
        ).as_dict(),
    }


def _temperature_recalibration_metrics(
    probability_rows: list[tuple[dict[str, float], str]],
    *,
    bins: int,
    seed_material: str,
    fit_through: datetime,
    primary_name: str = "poisson",
) -> dict[str, object] | None:
    walk_forward = walk_forward_temperature_scaling(
        probability_rows,
        minimum_history=MINIMUM_RECALIBRATION_HISTORY,
    )
    if len(walk_forward) < MINIMUM_RECALIBRATION_EVALUATION_OBSERVATIONS:
        return None
    raw_rows = [probability_rows[item.index] for item in walk_forward]
    temperature_rows = [
        (item.probabilities, probability_rows[item.index][1]) for item in walk_forward
    ]
    development_size = len(walk_forward) // 2
    validation_size = len(walk_forward) - development_size
    if validation_size < MINIMUM_RECALIBRATION_VALIDATION_OBSERVATIONS:
        return None

    raw_development_rows = raw_rows[:development_size]
    temperature_development_rows = temperature_rows[:development_size]
    raw_development_metrics, _ = summarize_probabilities(raw_development_rows, bins=bins)
    temperature_development_metrics, _ = summarize_probabilities(
        temperature_development_rows, bins=bins
    )
    development_checks = {
        "brier_improved": (
            _metric_number(temperature_development_metrics, "brier_score")
            <= _metric_number(raw_development_metrics, "brier_score")
            - CALIBRATION_SELECTION_MINIMUM_IMPROVEMENT
        ),
        "log_loss_improved": (
            _metric_number(temperature_development_metrics, "log_loss")
            <= _metric_number(raw_development_metrics, "log_loss")
            - CALIBRATION_SELECTION_MINIMUM_IMPROVEMENT
        ),
        "ece_not_worse": (
            _metric_number(temperature_development_metrics, "expected_calibration_error")
            <= _metric_number(raw_development_metrics, "expected_calibration_error")
        ),
    }
    selected_method = (
        "scalar_temperature_scaling" if all(development_checks.values()) else "identity"
    )

    raw_validation_rows = raw_rows[development_size:]
    selected_validation_rows = (
        temperature_rows[development_size:]
        if selected_method == "scalar_temperature_scaling"
        else raw_validation_rows
    )
    calibrated_metrics, _ = summarize_probabilities(selected_validation_rows, bins=bins)
    raw_subset_metrics, _ = summarize_probabilities(raw_validation_rows, bins=bins)
    calibrated_metrics["coverage"] = len(selected_validation_rows) / len(probability_rows)
    calibrated_metrics["minimum_history"] = MINIMUM_RECALIBRATION_HISTORY
    calibrated_metrics["walk_forward_observations"] = len(walk_forward)
    calibrated_metrics["development_observations"] = development_size
    calibrated_metrics["validation_observations"] = validation_size
    _attach_score_intervals(
        calibrated_metrics,
        selected_validation_rows,
        seed_material=seed_material,
        namespace=f"selected_calibration:{selected_method}",
    )
    _attach_paired_loss_difference(
        calibrated_metrics,
        raw_validation_rows,
        selected_validation_rows,
        seed_material=seed_material,
        namespace=f"selected_calibration:{selected_method}",
        primary_name=primary_name,
    )
    paired = calibrated_metrics["paired_loss_difference"]
    assert isinstance(paired, dict)
    brier_difference = paired["brier_score"]
    log_loss_difference = paired["log_loss"]
    assert isinstance(brier_difference, dict) and isinstance(log_loss_difference, dict)
    checks = {
        "minimum_untouched_validation_observations": (
            validation_size >= MINIMUM_RECALIBRATION_VALIDATION_OBSERVATIONS
        ),
        "untouched_brier_not_worse": _metric_number(brier_difference, "lower") >= 0,
        "untouched_log_loss_not_worse": _metric_number(log_loss_difference, "lower") >= 0,
        "untouched_ece_not_worse": (
            _metric_number(calibrated_metrics, "expected_calibration_error")
            <= _metric_number(raw_subset_metrics, "expected_calibration_error")
        ),
    }
    accepted = all(checks.values())
    fitted_temperature = fit_temperature_calibrator(probability_rows)
    final_temperature = (
        fitted_temperature.temperature if selected_method == "scalar_temperature_scaling" else 1.0
    )
    calibrated_metrics.update(
        {
            "version": RECALIBRATION_VERSION,
            "method": selected_method,
            "selection_method": "earlier_development_partition",
            "development_selection": {
                "selected_method": selected_method,
                "checks": development_checks,
                "raw_metrics": raw_development_metrics,
                "temperature_scaled_metrics": temperature_development_metrics,
            },
            "activation_status": "accepted" if accepted else "rejected",
            "activation_checks": checks,
            "raw_subset_metrics": raw_subset_metrics,
            "final_calibrator": {
                "version": RECALIBRATION_VERSION,
                "method": selected_method,
                "temperature": final_temperature,
                "sample_size": fitted_temperature.sample_size,
                "input_fingerprint": fitted_temperature.input_fingerprint,
                "fit_through": fit_through.isoformat(),
                "accepted": accepted,
            },
            "last_walk_forward_training_fingerprint": walk_forward[-1].training_fingerprint,
        }
    )
    return calibrated_metrics


def _bootstrap_seed_material(
    replayed: list[_ReplayObservation],
    *,
    primary_benchmark: str = "poisson",
) -> str:
    payload = []
    for observation in replayed:
        row: dict[str, object] = {
            "event_id": observation.event.id,
            "actual_outcome": observation.actual_outcome,
            "poisson": (
                observation.probabilities
                if primary_benchmark == "poisson"
                else observation.poisson_probabilities
            ),
            "elo": observation.elo_probabilities,
            "dixon_coles": observation.dixon_coles_probabilities,
            "nested_candidates": observation.nested_candidate_probabilities,
            "market_snapshot_ids": observation.market_snapshot_ids,
            "market": observation.market_probabilities,
        }
        if primary_benchmark != "poisson":
            row["primary"] = observation.probabilities
        payload.append(row)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _derived_bootstrap_seed(seed_material: str, namespace: str) -> int:
    digest = hashlib.sha256(f"{seed_material}:{namespace}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


def _paired_interval_upper(metrics: dict[str, object], metric: str) -> float:
    comparison = metrics.get("paired_loss_difference")
    if not isinstance(comparison, dict):
        raise EvaluationError("evaluation benchmark has no paired loss comparison")
    interval = comparison.get(metric)
    if not isinstance(interval, dict):
        raise EvaluationError(f"evaluation benchmark has no paired {metric} interval")
    return _metric_number(interval, "upper")


def _policy_decision(
    metrics: dict[str, object],
    uniform_metrics: dict[str, object],
    market_metrics: dict[str, object] | None,
    recalibration_metrics: dict[str, object] | None,
    *,
    is_demo: bool,
) -> tuple[str, str, dict[str, object]]:
    observations = _metric_number(metrics, "observations")
    coverage = _metric_number(metrics, "coverage")
    ece = _metric_number(metrics, "expected_calibration_error")
    uniform_brier_upper = _paired_interval_upper(uniform_metrics, "brier_score")
    uniform_log_loss_upper = _paired_interval_upper(uniform_metrics, "log_loss")
    market_observations = (
        _metric_number(market_metrics, "observations") if market_metrics is not None else 0.0
    )
    market_coverage = (
        _metric_number(market_metrics, "coverage") if market_metrics is not None else 0.0
    )
    market_brier_upper = (
        _paired_interval_upper(market_metrics, "brier_score")
        if market_metrics is not None
        else float("inf")
    )
    market_log_loss_upper = (
        _paired_interval_upper(market_metrics, "log_loss")
        if market_metrics is not None
        else float("inf")
    )
    probability_checks = {
        "non_demo_data": not is_demo,
        "minimum_observations": observations >= MINIMUM_PROMOTION_OBSERVATIONS,
        "minimum_coverage": coverage >= MINIMUM_PROMOTION_COVERAGE,
        "maximum_expected_calibration_error": ece <= MAXIMUM_PROMOTION_ECE,
        "uniform_brier_upper_difference_below_zero": uniform_brier_upper < 0,
        "uniform_log_loss_upper_difference_below_zero": uniform_log_loss_upper < 0,
        "chronological_recalibration_accepted": (
            recalibration_metrics is not None
            and recalibration_metrics.get("activation_status") == "accepted"
        ),
    }
    checks = {
        **probability_checks,
        "market_benchmark_available": market_metrics is not None,
        "minimum_market_observations": (
            market_observations >= MINIMUM_MARKET_PROMOTION_OBSERVATIONS
        ),
        "minimum_market_coverage": market_coverage >= MINIMUM_MARKET_PROMOTION_COVERAGE,
        "market_brier_upper_difference_below_zero": market_brier_upper < 0,
        "market_log_loss_upper_difference_below_zero": market_log_loss_upper < 0,
    }
    if is_demo:
        probability_status = "demo_only"
    elif (
        not probability_checks["minimum_observations"] or not probability_checks["minimum_coverage"]
    ):
        probability_status = "insufficient_evidence"
    elif recalibration_metrics is None:
        probability_status = "insufficient_recalibration_evidence"
    elif all(probability_checks.values()):
        probability_status = "probability_validated"
    else:
        probability_status = "probability_validation_failed"
    if is_demo:
        status = "demo_only"
    elif not checks["minimum_observations"] or not checks["minimum_coverage"]:
        status = "insufficient_evidence"
    elif (
        not checks["market_benchmark_available"]
        or not checks["minimum_market_observations"]
        or not checks["minimum_market_coverage"]
    ):
        status = "insufficient_market_evidence"
    elif recalibration_metrics is None:
        status = "insufficient_recalibration_evidence"
    elif all(checks.values()):
        status = "calibrated"
    else:
        status = "calibration_failed"
    return (
        status,
        probability_status,
        {
            **PROMOTION_POLICY,
            "probability_checks": probability_checks,
            "checks": checks,
            "probability_decision": probability_status,
            "market_decision": status,
            "decision": status,
        },
    )


def _persist_results(
    session: Session,
    *,
    run_id: int,
    primary_benchmark: str,
    metrics: dict[str, object],
    benchmark_metrics: dict[str, dict[str, object]],
    market_metrics: dict[str, object] | None,
    recalibration_metrics: dict[str, object] | None,
    buckets: list[CalibrationBucket],
) -> None:
    session.add(
        BacktestResult(
            run_id=run_id,
            benchmark=primary_benchmark,
            dimension="overall",
            dimension_value="all",
            metrics=metrics,
        )
    )
    for benchmark, benchmark_values in benchmark_metrics.items():
        session.add(
            BacktestResult(
                run_id=run_id,
                benchmark=benchmark,
                dimension="overall",
                dimension_value="all",
                metrics=benchmark_values,
            )
        )
    if market_metrics is not None:
        session.add(
            BacktestResult(
                run_id=run_id,
                benchmark="market_consensus",
                dimension="overall",
                dimension_value="available_events",
                metrics=market_metrics,
            )
        )
    if recalibration_metrics is not None:
        session.add(
            BacktestResult(
                run_id=run_id,
                benchmark="temperature_scaled",
                dimension="overall",
                dimension_value="all",
                metrics=recalibration_metrics,
            )
        )
    for bucket in buckets:
        session.add(
            BacktestResult(
                run_id=run_id,
                benchmark=primary_benchmark,
                dimension="calibration_bucket",
                dimension_value=f"{bucket.selection_code}:{bucket.bucket_index}",
                metrics=bucket.as_dict(),
            )
        )


def _run_view(session: Session, run: BacktestRun) -> EvaluationRunView:
    model = session.get(ModelVersion, run.model_version_id)
    if model is None:
        raise EvaluationError("evaluation references a missing model version")
    if run.fingerprint is None:
        raise EvaluationError("evaluation is missing its reproducibility fingerprint")
    results = session.scalars(
        select(BacktestResult).where(BacktestResult.run_id == run.id).order_by(BacktestResult.id)
    ).all()
    overall = {
        result.benchmark: result.metrics for result in results if result.dimension == "overall"
    }
    primary_benchmark = run.config.get("primary_benchmark", "poisson")
    if not isinstance(primary_benchmark, str) or primary_benchmark not in overall:
        raise EvaluationError("evaluation primary benchmark is missing or invalid")
    calibration = [
        CalibrationBucketView.model_validate(result.metrics)
        for result in results
        if result.benchmark == primary_benchmark and result.dimension == "calibration_bucket"
    ]
    return EvaluationRunView(
        id=run.id,
        model_version_id=model.id,
        model_version=model.version,
        status=run.status,
        evaluation_start=_utc(run.validation_end),
        evaluation_end=_utc(run.test_end),
        fingerprint=run.fingerprint,
        config=run.config,
        policy=run.policy,
        probability_evaluation_status=run.probability_evaluation_status,
        evaluation_status=run.evaluation_status,
        is_demo=run.is_demo,
        metrics=overall[primary_benchmark],
        benchmarks={
            benchmark: values
            for benchmark, values in overall.items()
            if benchmark != primary_benchmark
        },
        calibration=calibration,
        created_at=_utc(run.created_at),
    )


def _evaluation_fingerprint(
    *,
    model: ModelVersion,
    request: EvaluateModelRequest,
    replayed: list[_ReplayObservation],
    evaluation_status: str,
    probability_evaluation_status: str,
    evaluation_method_version: str = EVALUATION_METHOD_VERSION,
) -> str:
    payload = {
        "model_version": model.version,
        "evaluation_method_version": evaluation_method_version,
        "request": request.model_dump(mode="json"),
        "evaluation_status": evaluation_status,
        "probability_evaluation_status": probability_evaluation_status,
        "observations": [
            {
                "event_id": row.event.id,
                "result_id": row.result.id,
                "predicted_at": row.predicted_at.isoformat(),
                "training_fingerprint": row.training_fingerprint,
                "probabilities": row.probabilities,
                "elo_probabilities": row.elo_probabilities,
                "dixon_coles_probabilities": row.dixon_coles_probabilities,
                "nested_candidate_probabilities": row.nested_candidate_probabilities,
                "market_snapshot_ids": row.market_snapshot_ids,
                **(
                    {"poisson_probabilities": row.poisson_probabilities}
                    if model.kind == ELO_MODEL_KIND
                    else {}
                ),
            }
            for row in replayed
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _nested_candidate_probabilities(
    scores: list[HistoricalScore],
    elo_history: list[EloMatchResult],
    *,
    home_team_id: int,
    away_team_id: int,
    predicted_at: datetime,
    elo_config: EloConfig,
) -> dict[str, dict[str, float]]:
    candidates: dict[str, dict[str, float]] = {}
    for shrinkage in NESTED_POISSON_SHRINKAGES:
        fitted = fit_poisson_team_strength(scores, shrinkage_matches=shrinkage)
        home_lambda, away_lambda = fitted.expected_goals(home_team_id, away_team_id)
        candidates[f"poisson_shrinkage_{shrinkage:g}"] = derive_market(
            score_matrix(home_lambda, away_lambda), "MATCH_RESULT"
        )
    for k_factor in NESTED_ELO_K_FACTORS:
        config = EloConfig(
            initial_rating=elo_config.initial_rating,
            k_factor=k_factor,
            scale=elo_config.scale,
            home_advantage=elo_config.home_advantage,
            draw_probability_at_even_strength=elo_config.draw_probability_at_even_strength,
        )
        candidates[f"elo_k_{k_factor:g}"] = elo_probabilities_as_of(
            elo_history,
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            as_of=predicted_at,
            config=config,
        ).probabilities
    return candidates


def _nested_candidate_grid() -> dict[str, object]:
    return {
        "poisson_shrinkage_matches": list(NESTED_POISSON_SHRINKAGES),
        "elo_k_factors": list(NESTED_ELO_K_FACTORS),
        "fixed_elo_parameters": {
            "initial_rating": "model_or_default",
            "scale": "model_or_default",
            "home_advantage": "model_or_default",
            "draw_probability_at_even_strength": "model_or_default",
        },
    }


def _training_fingerprint(rows: list[tuple[MatchResult, Event]]) -> str:
    payload = [
        {
            "event_id": event.id,
            "result_id": result.id,
            "kickoff_at": _utc(event.kickoff_at).isoformat(),
            "home_goals": result.home_goals,
            "away_goals": result.away_goals,
            "observed_at": _utc(result.observed_at).isoformat(),
        }
        for result, event in rows
    ]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _actual_outcome(result: MatchResult) -> str:
    if result.home_goals > result.away_goals:
        return "HOME"
    if result.home_goals < result.away_goals:
        return "AWAY"
    return "DRAW"


def _config_int(config: dict[str, object], key: str) -> int:
    value = config.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise EvaluationError(f"model configuration field {key} is invalid")
    return value


def _config_number(config: dict[str, object], key: str) -> float:
    value = config.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EvaluationError(f"model configuration field {key} is invalid")
    return float(value)


def _metric_number(metrics: dict[str, object], key: str) -> float:
    value = metrics.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EvaluationError(f"evaluation metric {key} is invalid")
    return float(value)


def _increment(values: dict[str, int], key: str) -> None:
    values[key] = values.get(key, 0) + 1


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
