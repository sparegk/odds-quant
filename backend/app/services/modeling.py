from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from datetime import UTC, datetime

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    BacktestResult,
    BacktestRun,
    Competition,
    Event,
    LineupMember,
    LineupSnapshot,
    Market,
    MatchResult,
    ModelEventOutput,
    ModelOutputLineupSnapshot,
    ModelPrediction,
    ModelVersion,
    Provider,
    Selection,
)
from app.quant.calibration import (
    PROMOTION_POLICY_VERSION,
    temperature_scale,
)
from app.quant.cold_start import (
    cold_start_uncertainty_class,
    widen_match_result_probabilities,
)
from app.quant.elo import EloConfig
from app.quant.evaluation import OUTCOMES
from app.quant.feature_activation import blocked_feature_activation
from app.quant.odds import fair_odds
from app.quant.poisson import derive_market, score_matrix, selection_probability
from app.quant.team_strength import (
    HistoricalScore,
    fit_poisson_team_strength,
    model_from_config,
    model_to_config,
)
from app.quant.uncertainty import (
    bootstrap_probability_interval,
    chronological_block_bootstrap_expected_goals,
)
from app.schemas.models import (
    FeatureActivationView,
    ModelOutputView,
    ModelVersionView,
    PredictEventRequest,
    ProbabilityCalibrationView,
    ProbabilityUncertaintyView,
    SelectionPredictionView,
    TrainEloRequest,
    TrainPoissonRequest,
)
from app.services.cold_start_activation import (
    ACTIVATION_CONTRACT_VERSION,
    COLD_START_CALIBRATION_VERSION,
    COLD_START_FEATURE_VERSION,
    COLD_START_MODEL_KIND,
    COLD_START_PREDICTION_POLICY_VERSION,
    COLD_START_UNCERTAINTY_VERSION,
    EXPECTED_FAMILY_FINGERPRINTS,
    EXPECTED_SOURCE_MODEL_IDS,
    cold_start_activation_decision,
    frozen_activation_evidence,
)

MODEL_KIND = "poisson_team_strength"
ELO_MODEL_KIND = "davidson_elo"
FEATURE_VERSION = "final-score-home-away-v3-bootstrap-uncertainty"
ELO_FEATURE_VERSION = "final-score-result-sequence-v1"
UNCERTAINTY_METHOD = "chronological_moving_block_bootstrap_refit"
UNCERTAINTY_VERSION = "probability-uncertainty-v1"
UNCERTAINTY_CONFIDENCE_LEVEL = 0.95
UNCERTAINTY_RESAMPLES = 400
COLD_START_UNCERTAINTY_METHOD = "chronological_block_bootstrap_with_league_priors"


class ModelingError(ValueError):
    pass


def train_poisson_model(
    session: Session,
    request: TrainPoissonRequest,
    *,
    now: datetime | None = None,
) -> ModelVersionView:
    reference = _utc(now or datetime.now(UTC))
    training_start = _utc(request.training_start)
    training_end = _utc(request.training_end)
    if training_end > reference:
        raise ModelingError("training_end cannot be in the future")
    competition = session.get(Competition, request.competition_id)
    if competition is None:
        raise ModelingError("competition not found")
    training_competition_ids = competition_family_ids(session, competition)

    observations = _training_observations(
        session,
        competition_id=request.competition_id,
        training_start=training_start,
        training_end=training_end,
    )
    if len(observations) < request.minimum_matches:
        raise ModelingError(
            f"insufficient historical matches: {len(observations)} available, "
            f"{request.minimum_matches} required"
        )
    scores = [
        HistoricalScore(
            home_team_id=event.home_team_id,
            away_team_id=event.away_team_id,
            home_goals=result.home_goals,
            away_goals=result.away_goals,
        )
        for result, event in observations
    ]
    fitted = fit_poisson_team_strength(scores, shrinkage_matches=request.shrinkage_matches)
    fingerprint = _fingerprint(observations)
    specification = json.dumps(
        {
            "data_fingerprint": fingerprint,
            "feature_version": FEATURE_VERSION,
            "minimum_team_matches": request.minimum_team_matches,
            "shrinkage_matches": request.shrinkage_matches,
            "training_start": training_start.isoformat(),
            "training_competition_ids": training_competition_ids,
            "probability_uncertainty_version": UNCERTAINTY_VERSION,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    specification_hash = hashlib.sha256(specification).hexdigest()
    version = f"pq1-c{request.competition_id}-{training_end:%Y%m%d%H%M}-{specification_hash[:8]}"
    existing = session.scalar(select(ModelVersion).where(ModelVersion.version == version))
    if existing is not None:
        return _model_view(existing)

    config = model_to_config(fitted)
    config.update(
        {
            "competition_id": request.competition_id,
            "training_competition_ids": training_competition_ids,
            "training_competition_scope": "same_sport_name_country_all_seasons",
            "minimum_team_matches": request.minimum_team_matches,
            "lambda_bounds": [0.05, 4.0],
            "score_matrix_max_goals": 20,
            "training_cutoff_inclusive_for_observations": True,
            "training_kickoff_end_exclusive": True,
            "probability_uncertainty": {
                "method": UNCERTAINTY_METHOD,
                "version": UNCERTAINTY_VERSION,
                "confidence_level": UNCERTAINTY_CONFIDENCE_LEVEL,
                "resamples": UNCERTAINTY_RESAMPLES,
                "block_length_rule": "round_sqrt_training_matches_minimum_2",
                "seed_scope": "training_fingerprint_event_id_method_version",
            },
        }
    )
    model = ModelVersion(
        name="Poisson team-strength baseline",
        version=version,
        kind=MODEL_KIND,
        training_start=training_start,
        training_end=training_end,
        data_fingerprint=fingerprint,
        feature_version=FEATURE_VERSION,
        sample_size=fitted.sample_size,
        probability_evaluation_status="unvalidated",
        evaluation_status="unvalidated",
        config=config,
        metrics={
            "metric_scope": "training_descriptive_only",
            "held_out_evaluation": False,
            "mean_home_goals": fitted.league_home_goals,
            "mean_away_goals": fitted.league_away_goals,
            "teams": len(fitted.teams),
        },
        status="trained",
        is_demo=all(event.is_demo for _, event in observations),
    )
    session.add(model)
    session.commit()
    return _model_view(model)


def activate_cold_start_model(
    session: Session,
    source_model_id: int,
) -> ModelVersionView:
    activation = cold_start_activation_decision(frozen_activation_evidence())
    if activation["status"] != "approved_probability_only_model_path":
        raise ModelingError("cold-start activation contract did not approve the model path")
    if source_model_id in EXPECTED_SOURCE_MODEL_IDS:
        raise ModelingError("validation evidence models cannot be activated or mutated")
    source = session.get(ModelVersion, source_model_id)
    if source is None:
        raise ModelingError("source model version not found")
    if source.kind != MODEL_KIND or source.status != "trained":
        raise ModelingError("cold-start activation requires a trained Poisson source model")
    if source.is_demo:
        raise ModelingError("demo models cannot activate the validated cold-start path")
    if source.feature_version != FEATURE_VERSION:
        raise ModelingError("source model feature version does not match the activation contract")

    specification = json.dumps(
        {
            "activation_contract_version": ACTIVATION_CONTRACT_VERSION,
            "data_fingerprint": source.data_fingerprint,
            "feature_version": COLD_START_FEATURE_VERSION,
            "prediction_policy_version": COLD_START_PREDICTION_POLICY_VERSION,
            "source_model_id": source.id,
            "source_model_version": source.version,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    specification_hash = hashlib.sha256(specification).hexdigest()
    competition_id = _config_int(source.config, "competition_id")
    version = (
        f"pqc2-c{competition_id}-{_utc(source.training_end):%Y%m%d%H%M}-{specification_hash[:8]}"
    )
    existing = session.scalar(select(ModelVersion).where(ModelVersion.version == version))
    if existing is not None:
        return _model_view(existing)

    config = deepcopy(source.config)
    config.update(
        {
            "activation_contract_version": ACTIVATION_CONTRACT_VERSION,
            "source_model_id": source.id,
            "source_model_version": source.version,
            "prediction_policy_version": COLD_START_PREDICTION_POLICY_VERSION,
            "cold_start_uncertainty_version": COLD_START_UNCERTAINTY_VERSION,
            "cold_start_calibration_version": COLD_START_CALIBRATION_VERSION,
            "authorized_probability_markets": ["MATCH_RESULT"],
            "market_authorization": False,
            "automatic_signal_generation_authorized": False,
        }
    )
    model = ModelVersion(
        name="Activated cold-start v2 Poisson probability model",
        version=version,
        kind=COLD_START_MODEL_KIND,
        training_start=_utc(source.training_start),
        training_end=_utc(source.training_end),
        data_fingerprint=source.data_fingerprint,
        feature_version=COLD_START_FEATURE_VERSION,
        sample_size=source.sample_size,
        probability_evaluation_status="probability_validated",
        evaluation_status="insufficient_market_evidence",
        config=config,
        metrics={
            "metric_scope": "cross_league_method_activation",
            "held_out_evaluation": False,
            "method_held_out_evaluation": True,
            "activation_contract_version": ACTIVATION_CONTRACT_VERSION,
            "confirmation_status": "replicated_probability_candidate",
            "family_evaluation_fingerprints": list(EXPECTED_FAMILY_FINGERPRINTS),
            "source_training_metrics": deepcopy(source.metrics),
            "market_evidence_inherited": False,
        },
        status="trained",
        is_demo=False,
    )
    session.add(model)
    session.commit()
    return _model_view(model)


def train_elo_model(
    session: Session,
    request: TrainEloRequest,
    *,
    now: datetime | None = None,
) -> ModelVersionView:
    reference = _utc(now or datetime.now(UTC))
    training_start = _utc(request.training_start)
    training_end = _utc(request.training_end)
    if training_end > reference:
        raise ModelingError("training_end cannot be in the future")
    competition = session.get(Competition, request.competition_id)
    if competition is None:
        raise ModelingError("competition not found")
    training_competition_ids = competition_family_ids(session, competition)
    observations = _training_observations(
        session,
        competition_id=request.competition_id,
        training_start=training_start,
        training_end=training_end,
    )
    if len(observations) < request.minimum_matches:
        raise ModelingError(
            f"insufficient historical matches: {len(observations)} available, "
            f"{request.minimum_matches} required"
        )

    elo = EloConfig(
        initial_rating=request.initial_rating,
        k_factor=request.k_factor,
        scale=request.scale,
        home_advantage=request.home_advantage,
        draw_probability_at_even_strength=request.draw_probability_at_even_strength,
    )
    fingerprint = _fingerprint(observations)
    specification = json.dumps(
        {
            "algorithm_version": "davidson-elo-v1",
            "data_fingerprint": fingerprint,
            "feature_version": ELO_FEATURE_VERSION,
            "minimum_team_matches": request.minimum_team_matches,
            "training_start": training_start.isoformat(),
            "training_competition_ids": training_competition_ids,
            **elo.__dict__,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    specification_hash = hashlib.sha256(specification).hexdigest()
    version = f"elo1-c{request.competition_id}-{training_end:%Y%m%d%H%M}-{specification_hash[:8]}"
    existing = session.scalar(select(ModelVersion).where(ModelVersion.version == version))
    if existing is not None:
        return _model_view(existing)

    outcome_counts = {"HOME": 0, "DRAW": 0, "AWAY": 0}
    team_ids: set[int] = set()
    for result, event in observations:
        team_ids.update((event.home_team_id, event.away_team_id))
        outcome = (
            "HOME"
            if result.home_goals > result.away_goals
            else "DRAW"
            if result.home_goals == result.away_goals
            else "AWAY"
        )
        outcome_counts[outcome] += 1

    model = ModelVersion(
        name="Davidson Elo team-strength candidate",
        version=version,
        kind=ELO_MODEL_KIND,
        training_start=training_start,
        training_end=training_end,
        data_fingerprint=fingerprint,
        feature_version=ELO_FEATURE_VERSION,
        sample_size=len(observations),
        probability_evaluation_status="unvalidated",
        evaluation_status="unvalidated",
        config={
            "algorithm_version": "davidson-elo-v1",
            "competition_id": request.competition_id,
            "training_competition_ids": training_competition_ids,
            "training_competition_scope": "same_sport_name_country_all_seasons",
            "minimum_team_matches": request.minimum_team_matches,
            "training_cutoff_inclusive_for_observations": True,
            "training_kickoff_end_exclusive": True,
            "results_ordering": "observed_at_then_event_id",
            **elo.__dict__,
        },
        metrics={
            "metric_scope": "training_descriptive_only",
            "held_out_evaluation": False,
            "teams": len(team_ids),
            "outcome_counts": outcome_counts,
        },
        status="trained",
        is_demo=all(event.is_demo for _, event in observations),
    )
    session.add(model)
    session.commit()
    return _model_view(model)


def predict_event(
    session: Session,
    model_id: int,
    request: PredictEventRequest,
    *,
    now: datetime | None = None,
    lineup_snapshot_ids: list[int] | None = None,
) -> ModelOutputView:
    model = session.get(ModelVersion, model_id)
    if model is None:
        raise ModelingError("model version not found")
    if model.kind not in {MODEL_KIND, COLD_START_MODEL_KIND} or model.status != "trained":
        raise ModelingError("model version is not an active Poisson team-strength model")
    event = session.get(Event, request.event_id)
    if event is None:
        raise ModelingError("event not found")

    predicted_at = _utc(request.predicted_at or now or datetime.now(UTC))
    inputs_as_of = _utc(request.inputs_as_of or predicted_at)
    kickoff = _utc(event.kickoff_at)
    if predicted_at >= kickoff:
        raise ModelingError("prediction must be generated before kickoff")
    if inputs_as_of > predicted_at:
        raise ModelingError("inputs_as_of cannot be after predicted_at")
    if _utc(model.training_end) > inputs_as_of:
        raise ModelingError("model training window ends after the prediction input cutoff")
    competition_id = _config_int(model.config, "competition_id")
    if event.competition_id != competition_id:
        raise ModelingError("event competition does not match the model competition")

    confirmed_lineups = _validated_confirmed_lineups(
        session,
        event=event,
        cutoff=inputs_as_of,
        lineup_snapshot_ids=lineup_snapshot_ids,
    )
    evidence_class = "confirmed_lineup_context_unadjusted" if confirmed_lineups else "team_baseline"
    feature_activation = blocked_feature_activation(
        requested_contexts=["confirmed_lineups"] if confirmed_lineups else []
    )

    existing = session.scalar(
        select(ModelEventOutput).where(
            ModelEventOutput.event_id == event.id,
            ModelEventOutput.model_version_id == model.id,
            ModelEventOutput.predicted_at == predicted_at,
            ModelEventOutput.evidence_class == evidence_class,
        )
    )
    if existing is not None:
        return _output_view(session, existing, model)

    fitted = model_from_config(model.config, sample_size=model.sample_size)
    cold_start_venue_matches: tuple[int, int] | None = None
    cold_start_details: dict[str, object] = {}
    if model.kind == COLD_START_MODEL_KIND:
        forecast = fitted.expected_goals_with_league_priors(
            event.home_team_id,
            event.away_team_id,
        )
        home_lambda, away_lambda = forecast.home_lambda, forecast.away_lambda
        cold_start_venue_matches = (
            forecast.home_venue_matches,
            forecast.away_venue_matches,
        )
        _, reliability_weight = widen_match_result_probabilities(
            {outcome: 1 / len(OUTCOMES) for outcome in OUTCOMES},
            home_venue_matches=forecast.home_venue_matches,
            away_venue_matches=forecast.away_venue_matches,
        )
        cold_start_details = {
            "reliability_weight": reliability_weight,
            "uncertainty_class": cold_start_uncertainty_class(
                home_venue_matches=forecast.home_venue_matches,
                away_venue_matches=forecast.away_venue_matches,
                home_used_league_prior=forecast.home_used_league_prior,
                away_used_league_prior=forecast.away_used_league_prior,
            ),
            "home_venue_matches": forecast.home_venue_matches,
            "away_venue_matches": forecast.away_venue_matches,
            "home_used_league_prior": forecast.home_used_league_prior,
            "away_used_league_prior": forecast.away_used_league_prior,
        }
    else:
        minimum_team_matches = _config_int(model.config, "minimum_team_matches")
        _require_team_history(
            (
                fitted.teams[event.home_team_id].home_matches
                if event.home_team_id in fitted.teams
                else 0
            ),
            minimum_team_matches,
            "home team at home",
        )
        _require_team_history(
            (
                fitted.teams[event.away_team_id].away_matches
                if event.away_team_id in fitted.teams
                else 0
            ),
            minimum_team_matches,
            "away team away",
        )
        home_lambda, away_lambda = fitted.expected_goals(event.home_team_id, event.away_team_id)
    matrix = score_matrix(home_lambda, away_lambda)
    uncertainty, bootstrap_matrices = _prediction_uncertainty(
        session,
        model=model,
        event=event,
        allow_league_priors=model.kind == COLD_START_MODEL_KIND,
    )
    uncertainty.update(cold_start_details)
    calibration: dict[str, object]
    calibration_temperature: float | None
    if model.kind == COLD_START_MODEL_KIND:
        calibration, calibration_temperature = _cold_start_identity_calibration(model)
    else:
        calibration, calibration_temperature = _prediction_calibration(
            session,
            model=model,
            inputs_as_of=inputs_as_of,
        )
    output = ModelEventOutput(
        event_id=event.id,
        model_version_id=model.id,
        lineup_snapshot_id=(confirmed_lineups[-1].id if confirmed_lineups else None),
        matchup_feature_snapshot_id=None,
        predicted_at=predicted_at,
        inputs_as_of=inputs_as_of,
        evidence_class=evidence_class,
        home_lambda=home_lambda,
        away_lambda=away_lambda,
        score_matrix=matrix.tolist(),
        sample_size=model.sample_size,
        probability_uncertainty=uncertainty,
        probability_calibration=calibration,
        feature_activation=feature_activation,
    )
    session.add(output)
    session.flush()
    for lineup in confirmed_lineups:
        session.add(
            ModelOutputLineupSnapshot(
                output_id=output.id,
                lineup_snapshot_id=lineup.id,
            )
        )
    _persist_selection_predictions(
        session,
        output,
        event,
        matrix,
        bootstrap_matrices=bootstrap_matrices,
        confidence_level=_config_float(uncertainty, "confidence_level"),
        calibration_temperature=calibration_temperature,
        cold_start_venue_matches=cold_start_venue_matches,
    )
    session.commit()
    return _output_view(session, output, model)


def _validated_confirmed_lineups(
    session: Session,
    *,
    event: Event,
    cutoff: datetime,
    lineup_snapshot_ids: list[int] | None,
) -> list[LineupSnapshot]:
    if lineup_snapshot_ids is None:
        return []
    if len(set(lineup_snapshot_ids)) != 2:
        raise ModelingError("confirmed prediction requires exactly two distinct lineups")
    lineups = list(
        session.scalars(
            select(LineupSnapshot)
            .join(Provider, Provider.id == LineupSnapshot.provider_id)
            .where(
                LineupSnapshot.id.in_(lineup_snapshot_ids),
                LineupSnapshot.event_id == event.id,
                LineupSnapshot.lineup_type == "confirmed",
                LineupSnapshot.observed_at <= cutoff,
                LineupSnapshot.source_updated_at.is_not(None),
                LineupSnapshot.source_updated_at <= cutoff,
                Provider.is_demo.is_(False),
            )
            .order_by(LineupSnapshot.team_id, LineupSnapshot.id)
        )
    )
    if len(lineups) != 2 or {item.team_id for item in lineups} != {
        event.home_team_id,
        event.away_team_id,
    }:
        raise ModelingError("confirmed lineups must cover both event teams before cutoff")
    for lineup in lineups:
        starters = session.scalar(
            select(func.count())
            .select_from(LineupMember)
            .where(
                LineupMember.lineup_snapshot_id == lineup.id,
                LineupMember.starter.is_(True),
            )
        )
        if starters != 11:
            raise ModelingError("confirmed lineup must contain exactly 11 starters")
    return lineups


def list_models(session: Session) -> list[ModelVersionView]:
    models = session.scalars(
        select(ModelVersion).order_by(ModelVersion.created_at.desc(), ModelVersion.id.desc())
    ).all()
    return [_model_view(model) for model in models]


def get_model(session: Session, model_id: int) -> ModelVersionView | None:
    model = session.get(ModelVersion, model_id)
    return _model_view(model) if model is not None else None


def list_event_predictions(session: Session, event_id: int) -> list[ModelOutputView]:
    outputs = session.scalars(
        select(ModelEventOutput)
        .where(ModelEventOutput.event_id == event_id)
        .order_by(ModelEventOutput.predicted_at.desc(), ModelEventOutput.id.desc())
    ).all()
    models = {
        model.id: model
        for model in session.scalars(
            select(ModelVersion).where(
                ModelVersion.id.in_({output.model_version_id for output in outputs})
            )
        ).all()
    }
    return [_output_view(session, output, models[output.model_version_id]) for output in outputs]


def _training_observations(
    session: Session,
    *,
    competition_id: int,
    training_start: datetime,
    training_end: datetime,
) -> list[tuple[MatchResult, Event]]:
    competition = session.get(Competition, competition_id)
    if competition is None:
        raise ModelingError("competition not found")
    competition_ids = competition_family_ids(session, competition)
    rows = session.execute(
        select(MatchResult, Event)
        .join(Event, Event.id == MatchResult.event_id)
        .where(
            Event.competition_id.in_(competition_ids),
            Event.kickoff_at >= training_start,
            Event.kickoff_at < training_end,
            MatchResult.is_final.is_(True),
            MatchResult.settled_at >= Event.kickoff_at,
            MatchResult.observed_at >= Event.kickoff_at,
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
            raise ModelingError(
                "conflicting final scores exist for the same canonical training event"
            )
        if existing is None or _utc(result.observed_at) > _utc(existing[0].observed_at):
            canonical[key] = (result, event)
    return sorted(canonical.values(), key=lambda row: (_utc(row[1].kickoff_at), row[1].id))


def competition_family_ids(session: Session, competition: Competition) -> list[int]:
    return list(
        session.scalars(
            select(Competition.id)
            .where(
                Competition.sport_id == competition.sport_id,
                Competition.name == competition.name,
                Competition.country == competition.country,
            )
            .order_by(Competition.season, Competition.id)
        )
    )


def _persist_selection_predictions(
    session: Session,
    output: ModelEventOutput,
    event: Event,
    matrix: np.ndarray[tuple[int, int], np.dtype[np.float64]],
    *,
    bootstrap_matrices: list[np.ndarray[tuple[int, int], np.dtype[np.float64]]] | None,
    confidence_level: float,
    calibration_temperature: float | None,
    cold_start_venue_matches: tuple[int, int] | None,
) -> None:
    rows = session.execute(
        select(Market, Selection)
        .join(Selection, Selection.market_id == Market.id)
        .where(Market.event_id == event.id)
        .order_by(Market.id, Selection.id)
    ).all()
    grouped: dict[int, tuple[Market, list[Selection]]] = {}
    for market, selection in rows:
        grouped.setdefault(market.id, (market, []))[1].append(selection)
    for market, selections in grouped.values():
        if cold_start_venue_matches is not None and market.market_type != "MATCH_RESULT":
            continue
        line = float(market.line) if market.line is not None else None
        if line is not None and not _is_half_goal_line(line):
            continue
        raw_probabilities = _selection_probabilities(matrix, market, selections, line)
        if not raw_probabilities:
            continue
        probabilities = _calibrate_match_result(
            market,
            raw_probabilities,
            calibration_temperature,
        )
        if cold_start_venue_matches is not None:
            probabilities, _ = widen_match_result_probabilities(
                probabilities,
                home_venue_matches=cold_start_venue_matches[0],
                away_venue_matches=cold_start_venue_matches[1],
            )
        sampled_by_selection: dict[str, list[float]] = {
            selection.code: [] for selection in selections if selection.code in probabilities
        }
        if bootstrap_matrices is not None:
            for sample in bootstrap_matrices:
                sample_raw = _selection_probabilities(sample, market, selections, line)
                sample_probabilities = _calibrate_match_result(
                    market,
                    sample_raw,
                    calibration_temperature,
                )
                if cold_start_venue_matches is not None:
                    sample_probabilities, _ = widen_match_result_probabilities(
                        sample_probabilities,
                        home_venue_matches=cold_start_venue_matches[0],
                        away_venue_matches=cold_start_venue_matches[1],
                    )
                for code in sampled_by_selection:
                    sampled_by_selection[code].append(sample_probabilities[code])
        for selection in selections:
            probability = probabilities.get(selection.code)
            if probability is None:
                continue
            if bootstrap_matrices is None:
                lower, upper = _wilson_interval(probability, output.sample_size)
            else:
                lower, upper = bootstrap_probability_interval(
                    probability,
                    sampled_by_selection[selection.code],
                    confidence_level=confidence_level,
                )
            session.add(
                ModelPrediction(
                    output_id=output.id,
                    selection_id=selection.id,
                    probability=probability,
                    lower_probability=lower,
                    upper_probability=upper,
                    fair_odds=fair_odds(probability),
                )
            )


def _selection_probabilities(
    matrix: np.ndarray[tuple[int, int], np.dtype[np.float64]],
    market: Market,
    selections: list[Selection],
    line: float | None,
) -> dict[str, float]:
    probabilities: dict[str, float] = {}
    for selection in selections:
        try:
            probabilities[selection.code] = selection_probability(
                matrix,
                market.market_type,
                selection.code,
                line,
            )
        except ValueError:
            continue
    return probabilities


def _calibrate_match_result(
    market: Market,
    probabilities: dict[str, float],
    temperature: float | None,
) -> dict[str, float]:
    if (
        temperature is None
        or market.market_type != "MATCH_RESULT"
        or set(probabilities) != set(OUTCOMES)
    ):
        return probabilities
    return temperature_scale(probabilities, temperature)


def _output_view(
    session: Session,
    output: ModelEventOutput,
    model: ModelVersion,
) -> ModelOutputView:
    matrix = np.asarray(output.score_matrix, dtype=np.float64)
    rows = session.execute(
        select(ModelPrediction, Selection, Market)
        .join(Selection, Selection.id == ModelPrediction.selection_id)
        .join(Market, Market.id == Selection.market_id)
        .where(ModelPrediction.output_id == output.id)
        .order_by(Market.id, Selection.id)
    ).all()
    lineup_snapshot_ids = list(
        session.scalars(
            select(ModelOutputLineupSnapshot.lineup_snapshot_id)
            .where(ModelOutputLineupSnapshot.output_id == output.id)
            .order_by(ModelOutputLineupSnapshot.lineup_snapshot_id)
        )
    )
    return ModelOutputView(
        id=output.id,
        event_id=output.event_id,
        model_version_id=model.id,
        model_version=model.version,
        predicted_at=_utc(output.predicted_at),
        inputs_as_of=_utc(output.inputs_as_of),
        evidence_class=output.evidence_class,
        lineup_snapshot_ids=lineup_snapshot_ids,
        home_lambda=output.home_lambda,
        away_lambda=output.away_lambda,
        sample_size=output.sample_size,
        probability_uncertainty=_uncertainty_view(output, model),
        probability_calibration=_calibration_view(output),
        feature_activation=_feature_activation_view(output),
        score_matrix=[[float(value) for value in row] for row in matrix],
        derived_probabilities=_derived_probabilities(
            matrix,
            calibration_temperature=_output_calibration_temperature(output),
            cold_start_venue_matches=_stored_cold_start_venue_matches(output),
        ),
        predictions=[
            SelectionPredictionView(
                id=prediction.id,
                market_id=market.id,
                market_type=market.market_type,
                line=float(market.line) if market.line is not None else None,
                selection_id=selection.id,
                selection_code=selection.code,
                selection_name=selection.name,
                probability=prediction.probability,
                lower_probability=prediction.lower_probability,
                upper_probability=prediction.upper_probability,
                fair_odds=prediction.fair_odds,
            )
            for prediction, selection, market in rows
        ],
    )


def _derived_probabilities(
    matrix: np.ndarray[tuple[int, int], np.dtype[np.float64]],
    *,
    calibration_temperature: float | None,
    cold_start_venue_matches: tuple[int, int] | None = None,
) -> dict[str, dict[str, float]]:
    match_result = derive_market(matrix, "MATCH_RESULT")
    if calibration_temperature is not None:
        match_result = temperature_scale(match_result, calibration_temperature)
    if cold_start_venue_matches is not None:
        match_result, _ = widen_match_result_probabilities(
            match_result,
            home_venue_matches=cold_start_venue_matches[0],
            away_venue_matches=cold_start_venue_matches[1],
        )
        return {"MATCH_RESULT": match_result}
    return {
        "MATCH_RESULT": match_result,
        "TOTAL_GOALS_2.5": derive_market(matrix, "TOTAL_GOALS", 2.5),
        "BOTH_TEAMS_TO_SCORE": derive_market(matrix, "BOTH_TEAMS_TO_SCORE"),
        "DOUBLE_CHANCE": {
            "HOME_OR_DRAW": selection_probability(matrix, "DOUBLE_CHANCE", "HOME_OR_DRAW", None),
            "AWAY_OR_DRAW": selection_probability(matrix, "DOUBLE_CHANCE", "AWAY_OR_DRAW", None),
            "HOME_OR_AWAY": selection_probability(matrix, "DOUBLE_CHANCE", "HOME_OR_AWAY", None),
        },
        "TEAM_TOTAL_HOME_1.5": derive_market(matrix, "TEAM_TOTAL_HOME", 1.5),
        "TEAM_TOTAL_AWAY_1.5": derive_market(matrix, "TEAM_TOTAL_AWAY", 1.5),
    }


def _prediction_uncertainty(
    session: Session,
    *,
    model: ModelVersion,
    event: Event,
    allow_league_priors: bool = False,
) -> tuple[
    dict[str, object],
    list[np.ndarray[tuple[int, int], np.dtype[np.float64]]] | None,
]:
    settings = model.config.get("probability_uncertainty")
    if not isinstance(settings, dict) or settings.get("method") != UNCERTAINTY_METHOD:
        return (
            {
                "method": "wilson_training_sample_proxy",
                "version": "legacy-v1",
                "confidence_level": 0.95,
                "requested_refits": 0,
                "successful_refits": 0,
                "attempted_refits": 0,
                "block_length": None,
                "seed_fingerprint": None,
                "training_fingerprint": model.data_fingerprint,
            },
            None,
        )

    observations = _training_observations(
        session,
        competition_id=_config_int(model.config, "competition_id"),
        training_start=_utc(model.training_start),
        training_end=_utc(model.training_end),
    )
    if _fingerprint(observations) != model.data_fingerprint:
        raise ModelingError("uncertainty training fingerprint does not match the model version")
    scores = [
        HistoricalScore(
            home_team_id=historical_event.home_team_id,
            away_team_id=historical_event.away_team_id,
            home_goals=result.home_goals,
            away_goals=result.away_goals,
        )
        for result, historical_event in observations
    ]
    version = _setting_string(settings, "version")
    confidence_level = _setting_float(settings, "confidence_level")
    resamples = _setting_int(settings, "resamples")
    seed_material = f"{model.data_fingerprint}:{event.id}:{UNCERTAINTY_METHOD}:{version}"
    try:
        distribution = chronological_block_bootstrap_expected_goals(
            scores,
            home_team_id=event.home_team_id,
            away_team_id=event.away_team_id,
            shrinkage_matches=_config_float(model.config, "shrinkage_matches"),
            resamples=resamples,
            seed_material=seed_material,
            allow_league_priors=allow_league_priors,
        )
    except ValueError as exc:
        raise ModelingError(f"probability uncertainty failed closed: {exc}") from exc
    matrices = [score_matrix(home, away) for home, away in distribution.samples]
    return (
        {
            "method": (
                COLD_START_UNCERTAINTY_METHOD if allow_league_priors else UNCERTAINTY_METHOD
            ),
            "version": COLD_START_UNCERTAINTY_VERSION if allow_league_priors else version,
            "confidence_level": confidence_level,
            "requested_refits": distribution.requested_refits,
            "successful_refits": len(distribution.samples),
            "attempted_refits": distribution.attempted_refits,
            "block_length": distribution.block_length,
            "seed_fingerprint": distribution.seed_fingerprint,
            "training_fingerprint": model.data_fingerprint,
        },
        matrices,
    )


def _cold_start_identity_calibration(
    model: ModelVersion,
) -> tuple[dict[str, object], float]:
    fingerprint = hashlib.sha256(
        f"{ACTIVATION_CONTRACT_VERSION}:{model.version}:identity".encode()
    ).hexdigest()
    return (
        {
            "method": "identity",
            "version": COLD_START_CALIBRATION_VERSION,
            "applied": True,
            "temperature": 1.0,
            "sample_size": 0,
            "input_fingerprint": fingerprint,
            "fit_through": None,
            "evaluation_run_id": None,
        },
        1.0,
    )


def _uncertainty_view(
    output: ModelEventOutput,
    model: ModelVersion,
) -> ProbabilityUncertaintyView:
    values = output.probability_uncertainty or {
        "method": "wilson_training_sample_proxy",
        "version": "legacy-v1",
        "confidence_level": 0.95,
        "requested_refits": 0,
        "successful_refits": 0,
        "attempted_refits": 0,
        "block_length": None,
        "seed_fingerprint": None,
        "training_fingerprint": model.data_fingerprint,
    }
    return ProbabilityUncertaintyView.model_validate(values)


def _prediction_calibration(
    session: Session,
    *,
    model: ModelVersion,
    inputs_as_of: datetime,
) -> tuple[dict[str, object], float | None]:
    runs = session.scalars(
        select(BacktestRun)
        .where(
            BacktestRun.model_version_id == model.id,
            BacktestRun.status == "completed",
            BacktestRun.probability_evaluation_status == "probability_validated",
            BacktestRun.is_demo.is_(False),
            BacktestRun.test_end <= inputs_as_of,
        )
        .order_by(BacktestRun.test_end.desc(), BacktestRun.id.desc())
    ).all()
    for run in runs:
        checks = run.policy.get("probability_checks")
        if (
            run.policy.get("version") != PROMOTION_POLICY_VERSION
            or run.policy.get("probability_decision") != "probability_validated"
            or not isinstance(checks, dict)
            or checks.get("chronological_recalibration_accepted") is not True
        ):
            continue
        result = session.scalar(
            select(BacktestResult).where(
                BacktestResult.run_id == run.id,
                BacktestResult.benchmark == "temperature_scaled",
                BacktestResult.dimension == "overall",
                BacktestResult.dimension_value == "all",
            )
        )
        if result is None:
            continue
        final = result.metrics.get("final_calibrator")
        if not isinstance(final, dict) or final.get("accepted") is not True:
            continue
        fit_through = _setting_datetime(final, "fit_through")
        if fit_through > inputs_as_of:
            continue
        temperature = _setting_float(final, "temperature")
        if temperature <= 0:
            raise ModelingError("accepted probability calibrator has invalid temperature")
        method = _setting_string(final, "method")
        if method not in {"scalar_temperature_scaling", "identity"}:
            raise ModelingError("accepted probability calibrator has invalid method")
        return (
            {
                "method": method,
                "version": _setting_string(final, "version"),
                "applied": True,
                "temperature": temperature,
                "sample_size": _setting_int(final, "sample_size"),
                "input_fingerprint": _setting_string(final, "input_fingerprint"),
                "fit_through": fit_through.isoformat(),
                "evaluation_run_id": run.id,
            },
            temperature,
        )
    return (
        {
            "method": "none",
            "version": "raw-probability-v1",
            "applied": False,
            "temperature": None,
            "sample_size": 0,
            "input_fingerprint": None,
            "fit_through": None,
            "evaluation_run_id": None,
        },
        None,
    )


def _feature_activation_view(output: ModelEventOutput) -> FeatureActivationView:
    values = output.feature_activation or blocked_feature_activation(
        requested_contexts=(
            ["confirmed_lineups"]
            if output.evidence_class == "confirmed_lineup_context_unadjusted"
            else []
        )
    )
    return FeatureActivationView.model_validate(values)


def _calibration_view(output: ModelEventOutput) -> ProbabilityCalibrationView:
    values = output.probability_calibration or {
        "method": "none",
        "version": "raw-probability-v1",
        "applied": False,
        "temperature": None,
        "sample_size": 0,
        "input_fingerprint": None,
        "fit_through": None,
        "evaluation_run_id": None,
    }
    return ProbabilityCalibrationView.model_validate(values)


def _output_calibration_temperature(output: ModelEventOutput) -> float | None:
    calibration = _calibration_view(output)
    return calibration.temperature if calibration.applied else None


def _stored_cold_start_venue_matches(output: ModelEventOutput) -> tuple[int, int] | None:
    values = output.probability_uncertainty or {}
    home = values.get("home_venue_matches")
    away = values.get("away_venue_matches")
    if (
        isinstance(home, int)
        and not isinstance(home, bool)
        and isinstance(away, int)
        and not isinstance(away, bool)
    ):
        return (home, away)
    return None


def _fingerprint(observations: list[tuple[MatchResult, Event]]) -> str:
    payload = [
        {
            "event_id": event.id,
            "kickoff_at": _utc(event.kickoff_at).isoformat(),
            "home_team_id": event.home_team_id,
            "away_team_id": event.away_team_id,
            "result_id": result.id,
            "home_goals": result.home_goals,
            "away_goals": result.away_goals,
            "observed_at": _utc(result.observed_at).isoformat(),
        }
        for result, event in observations
    ]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _model_view(model: ModelVersion) -> ModelVersionView:
    return ModelVersionView(
        id=model.id,
        name=model.name,
        version=model.version,
        kind=model.kind,
        training_start=_utc(model.training_start),
        training_end=_utc(model.training_end),
        data_fingerprint=model.data_fingerprint,
        feature_version=model.feature_version,
        sample_size=model.sample_size,
        probability_evaluation_status=model.probability_evaluation_status,
        evaluation_status=model.evaluation_status,
        config=model.config,
        metrics=model.metrics,
        status=model.status,
        is_demo=model.is_demo,
        created_at=_utc(model.created_at),
    )


def _wilson_interval(probability: float, sample_size: int) -> tuple[float, float]:
    z = 1.96
    denominator = 1 + z**2 / sample_size
    centre = (probability + z**2 / (2 * sample_size)) / denominator
    spread = (
        z
        * math.sqrt(probability * (1 - probability) / sample_size + z**2 / (4 * sample_size**2))
        / denominator
    )
    return (max(0.0, centre - spread), min(1.0, centre + spread))


def _config_int(config: dict[str, object], key: str) -> int:
    value = config.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ModelingError(f"model configuration field {key} is invalid")
    return value


def _config_float(config: dict[str, object], key: str) -> float:
    value = config.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ModelingError(f"model configuration field {key} is invalid")
    return float(value)


def _setting_string(settings: dict[str, object], key: str) -> str:
    value = settings.get(key)
    if not isinstance(value, str) or not value:
        raise ModelingError(f"probability uncertainty setting {key} is invalid")
    return value


def _setting_float(settings: dict[str, object], key: str) -> float:
    value = settings.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ModelingError(f"probability uncertainty setting {key} is invalid")
    return float(value)


def _setting_int(settings: dict[str, object], key: str) -> int:
    value = settings.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ModelingError(f"probability uncertainty setting {key} is invalid")
    return value


def _setting_datetime(settings: dict[str, object], key: str) -> datetime:
    value = _setting_string(settings, key)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ModelingError(f"probability calibration setting {key} is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ModelingError(f"probability calibration setting {key} must include an offset")
    return _utc(parsed)


def _require_team_history(observed: int, required: int, label: str) -> None:
    if observed < required:
        raise ModelingError(
            f"insufficient {label} history: {observed} matches available, {required} required"
        )


def _is_half_goal_line(line: float) -> bool:
    doubled = round(line * 2)
    return math.isclose(line * 2, doubled) and doubled % 2 == 1


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
