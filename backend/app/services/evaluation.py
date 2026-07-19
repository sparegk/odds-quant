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
    Event,
    Market,
    MatchResult,
    ModelVersion,
    OddsPrice,
    OddsSnapshot,
    Selection,
)
from app.quant.evaluation import (
    OUTCOMES,
    CalibrationBucket,
    multiclass_brier,
    multiclass_log_loss,
    summarize_probabilities,
)
from app.quant.odds import devig_proportional
from app.quant.poisson import derive_market, score_matrix
from app.quant.team_strength import HistoricalScore, fit_poisson_team_strength
from app.schemas.models import CalibrationBucketView, EvaluateModelRequest, EvaluationRunView
from app.services.modeling import MODEL_KIND

MINIMUM_PROMOTION_OBSERVATIONS = 200
MINIMUM_PROMOTION_COVERAGE = 0.90
MAXIMUM_PROMOTION_ECE = 0.08

PROMOTION_POLICY: dict[str, object] = {
    "version": "probability-calibration-v1",
    "minimum_observations": MINIMUM_PROMOTION_OBSERVATIONS,
    "minimum_coverage": MINIMUM_PROMOTION_COVERAGE,
    "maximum_expected_calibration_error": MAXIMUM_PROMOTION_ECE,
    "require_better_than_uniform_brier": True,
    "require_better_than_uniform_log_loss": True,
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
    if model.kind != MODEL_KIND or model.status != "trained":
        raise EvaluationError("model version is not a trained Poisson team-strength model")

    competition_id = _config_int(model.config, "competition_id")
    minimum_team_matches = _config_int(model.config, "minimum_team_matches")
    shrinkage_matches = _config_number(model.config, "shrinkage_matches")
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
        probabilities = derive_market(score_matrix(home_lambda, away_lambda), "MATCH_RESULT")
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
    metrics, buckets = summarize_probabilities(probability_rows, bins=request.calibration_bins)
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
    market_rows = [
        (observation.market_probabilities, observation.actual_outcome)
        for observation in replayed
        if observation.market_probabilities is not None
    ]
    market_metrics: dict[str, object] | None = None
    if market_rows:
        typed_market_rows = [
            (probabilities, actual)
            for probabilities, actual in market_rows
            if probabilities is not None
        ]
        market_metrics, _ = summarize_probabilities(
            typed_market_rows, bins=request.calibration_bins
        )
        market_metrics["coverage"] = len(typed_market_rows) / len(replayed)

    is_demo = bool(model.is_demo or any(row.event.is_demo for row in replayed))
    evaluation_status, policy = _policy_decision(metrics, uniform_metrics, is_demo=is_demo)
    fingerprint = _evaluation_fingerprint(
        model=model,
        request=request,
        replayed=replayed,
        evaluation_status=evaluation_status,
    )
    existing = session.scalar(select(BacktestRun).where(BacktestRun.fingerprint == fingerprint))
    if existing is not None:
        return _run_view(session, existing)

    config: dict[str, object] = {
        "evaluation_kind": "expanding_window_match_result",
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
        "market_benchmark": "mean_proportional_devig_of_latest_compatible_snapshot_per_bookmaker",
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
        metrics=metrics,
        uniform_metrics=uniform_metrics,
        market_metrics=market_metrics,
        buckets=buckets,
    )
    if evaluation_status == "calibrated":
        model.evaluation_status = "calibrated"
        model.metrics = {
            **model.metrics,
            "held_out_evaluation": True,
            "latest_evaluation_run_id": run.id,
            "held_out_metrics": metrics,
        }
    session.commit()
    return _run_view(session, run)


def list_evaluations(session: Session, *, model_id: int | None = None) -> list[EvaluationRunView]:
    statement = select(BacktestRun).order_by(BacktestRun.created_at.desc(), BacktestRun.id.desc())
    if model_id is not None:
        statement = statement.where(BacktestRun.model_version_id == model_id)
    return [_run_view(session, run) for run in session.scalars(statement).all()]


def get_evaluation(session: Session, run_id: int) -> EvaluationRunView | None:
    run = session.get(BacktestRun, run_id)
    return _run_view(session, run) if run is not None else None


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
    rows = session.execute(
        select(MatchResult, Event)
        .join(Event, Event.id == MatchResult.event_id)
        .where(
            Event.competition_id == competition_id,
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
        .where(
            Market.event_id == event_id,
            Market.market_type == "MATCH_RESULT",
            Market.line.is_(None),
            Market.period == "FULL_TIME",
            OddsSnapshot.is_complete.is_(True),
            OddsSnapshot.observed_at <= predicted_at,
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
    devigged: list[dict[str, float]] = []
    for _, _, prices in chosen:
        ordered_odds = [prices[outcome] for outcome in OUTCOMES]
        probabilities = devig_proportional(ordered_odds)
        devigged.append(dict(zip(OUTCOMES, probabilities, strict=True)))
    consensus = {
        outcome: sum(row[outcome] for row in devigged) / len(devigged) for outcome in OUTCOMES
    }
    return (sorted(row[1].id for row in chosen), consensus)


def _policy_decision(
    metrics: dict[str, object],
    uniform_metrics: dict[str, object],
    *,
    is_demo: bool,
) -> tuple[str, dict[str, object]]:
    observations = _metric_number(metrics, "observations")
    coverage = _metric_number(metrics, "coverage")
    ece = _metric_number(metrics, "expected_calibration_error")
    brier = _metric_number(metrics, "brier_score")
    log_loss = _metric_number(metrics, "log_loss")
    checks = {
        "non_demo_data": not is_demo,
        "minimum_observations": observations >= MINIMUM_PROMOTION_OBSERVATIONS,
        "minimum_coverage": coverage >= MINIMUM_PROMOTION_COVERAGE,
        "maximum_expected_calibration_error": ece <= MAXIMUM_PROMOTION_ECE,
        "better_than_uniform_brier": brier < _metric_number(uniform_metrics, "brier_score"),
        "better_than_uniform_log_loss": log_loss < _metric_number(uniform_metrics, "log_loss"),
    }
    if is_demo:
        status = "demo_only"
    elif not checks["minimum_observations"] or not checks["minimum_coverage"]:
        status = "insufficient_evidence"
    elif all(checks.values()):
        status = "calibrated"
    else:
        status = "calibration_failed"
    return status, {**PROMOTION_POLICY, "checks": checks, "decision": status}


def _persist_results(
    session: Session,
    *,
    run_id: int,
    metrics: dict[str, object],
    uniform_metrics: dict[str, object],
    market_metrics: dict[str, object] | None,
    buckets: list[CalibrationBucket],
) -> None:
    session.add(
        BacktestResult(
            run_id=run_id,
            benchmark="poisson",
            dimension="overall",
            dimension_value="all",
            metrics=metrics,
        )
    )
    session.add(
        BacktestResult(
            run_id=run_id,
            benchmark="uniform",
            dimension="overall",
            dimension_value="all",
            metrics=uniform_metrics,
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
    for bucket in buckets:
        session.add(
            BacktestResult(
                run_id=run_id,
                benchmark="poisson",
                dimension="calibration_bucket",
                dimension_value=f"{bucket.selection_code}:{bucket.bucket_index}",
                metrics=bucket.as_dict(),
            )
        )


def _run_view(session: Session, run: BacktestRun) -> EvaluationRunView:
    model = session.get(ModelVersion, run.model_version_id)
    if model is None:
        raise EvaluationError("evaluation references a missing model version")
    results = session.scalars(
        select(BacktestResult).where(BacktestResult.run_id == run.id).order_by(BacktestResult.id)
    ).all()
    overall = {
        result.benchmark: result.metrics for result in results if result.dimension == "overall"
    }
    calibration = [
        CalibrationBucketView.model_validate(result.metrics)
        for result in results
        if result.benchmark == "poisson" and result.dimension == "calibration_bucket"
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
        evaluation_status=run.evaluation_status,
        is_demo=run.is_demo,
        metrics=overall.get("poisson", {}),
        benchmarks={
            benchmark: values for benchmark, values in overall.items() if benchmark != "poisson"
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
) -> str:
    payload = {
        "model_version": model.version,
        "request": request.model_dump(mode="json"),
        "evaluation_status": evaluation_status,
        "observations": [
            {
                "event_id": row.event.id,
                "result_id": row.result.id,
                "predicted_at": row.predicted_at.isoformat(),
                "training_fingerprint": row.training_fingerprint,
                "probabilities": row.probabilities,
                "market_snapshot_ids": row.market_snapshot_ids,
            }
            for row in replayed
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


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
