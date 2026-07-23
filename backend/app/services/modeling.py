from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, datetime

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Competition,
    Event,
    Market,
    MatchResult,
    ModelEventOutput,
    ModelPrediction,
    ModelVersion,
    Selection,
)
from app.quant.odds import fair_odds
from app.quant.poisson import derive_market, score_matrix, selection_probability
from app.quant.team_strength import (
    HistoricalScore,
    fit_poisson_team_strength,
    model_from_config,
    model_to_config,
)
from app.schemas.models import (
    ModelOutputView,
    ModelVersionView,
    PredictEventRequest,
    SelectionPredictionView,
    TrainPoissonRequest,
)

MODEL_KIND = "poisson_team_strength"
FEATURE_VERSION = "final-score-home-away-v2-cross-season"


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
    training_competition_ids = _competition_family_ids(session, competition)

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


def predict_event(
    session: Session,
    model_id: int,
    request: PredictEventRequest,
    *,
    now: datetime | None = None,
) -> ModelOutputView:
    model = session.get(ModelVersion, model_id)
    if model is None:
        raise ModelingError("model version not found")
    if model.kind != MODEL_KIND or model.status != "trained":
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

    existing = session.scalar(
        select(ModelEventOutput).where(
            ModelEventOutput.event_id == event.id,
            ModelEventOutput.model_version_id == model.id,
            ModelEventOutput.predicted_at == predicted_at,
        )
    )
    if existing is not None:
        return _output_view(session, existing, model)

    fitted = model_from_config(model.config, sample_size=model.sample_size)
    minimum_team_matches = _config_int(model.config, "minimum_team_matches")
    _require_team_history(
        fitted.teams[event.home_team_id].home_matches if event.home_team_id in fitted.teams else 0,
        minimum_team_matches,
        "home team at home",
    )
    _require_team_history(
        fitted.teams[event.away_team_id].away_matches if event.away_team_id in fitted.teams else 0,
        minimum_team_matches,
        "away team away",
    )
    home_lambda, away_lambda = fitted.expected_goals(event.home_team_id, event.away_team_id)
    matrix = score_matrix(home_lambda, away_lambda)
    output = ModelEventOutput(
        event_id=event.id,
        model_version_id=model.id,
        lineup_snapshot_id=None,
        matchup_feature_snapshot_id=None,
        predicted_at=predicted_at,
        inputs_as_of=inputs_as_of,
        evidence_class="team_baseline",
        home_lambda=home_lambda,
        away_lambda=away_lambda,
        score_matrix=matrix.tolist(),
        sample_size=model.sample_size,
    )
    session.add(output)
    session.flush()
    _persist_selection_predictions(session, output, event, matrix)
    session.commit()
    return _output_view(session, output, model)


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
    competition_ids = _competition_family_ids(session, competition)
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


def _competition_family_ids(session: Session, competition: Competition) -> list[int]:
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
) -> None:
    rows = session.execute(
        select(Market, Selection)
        .join(Selection, Selection.market_id == Market.id)
        .where(Market.event_id == event.id)
        .order_by(Market.id, Selection.id)
    ).all()
    for market, selection in rows:
        line = float(market.line) if market.line is not None else None
        if line is not None and not _is_half_goal_line(line):
            continue
        try:
            probability = selection_probability(
                matrix,
                market.market_type,
                selection.code,
                line,
            )
        except ValueError:
            continue
        lower, upper = _wilson_interval(probability, output.sample_size)
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
    return ModelOutputView(
        id=output.id,
        event_id=output.event_id,
        model_version_id=model.id,
        model_version=model.version,
        predicted_at=_utc(output.predicted_at),
        inputs_as_of=_utc(output.inputs_as_of),
        evidence_class=output.evidence_class,
        home_lambda=output.home_lambda,
        away_lambda=output.away_lambda,
        sample_size=output.sample_size,
        score_matrix=[[float(value) for value in row] for row in matrix],
        derived_probabilities=_derived_probabilities(matrix),
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
) -> dict[str, dict[str, float]]:
    return {
        "MATCH_RESULT": derive_market(matrix, "MATCH_RESULT"),
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
