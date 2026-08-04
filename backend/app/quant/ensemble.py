from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass

from app.quant.evaluation import OUTCOMES, multiclass_brier, multiclass_log_loss

ENSEMBLE_VERSION = "chronological-simplex-ensemble-v1"
ENSEMBLE_MODELS = ("poisson", "elo", "dixon_coles")
ENSEMBLE_WEIGHT_STEP = 0.25
ENSEMBLE_WEIGHT_GRID = tuple(
    (home / 4, elo / 4, dixon / 4)
    for home in range(5)
    for elo in range(5)
    for dixon in range(5)
    if home + elo + dixon == 4 and sum(value > 0 for value in (home, elo, dixon)) >= 2
)


@dataclass(frozen=True)
class EnsembleForecast:
    index: int
    weights: dict[str, float]
    probabilities: dict[str, float]
    history_size: int
    history_fingerprint: str
    mean_log_loss: float
    mean_brier_score: float


def walk_forward_ensemble(
    rows: list[tuple[dict[str, dict[str, float]], str]],
    *,
    minimum_history: int,
) -> list[EnsembleForecast]:
    if minimum_history < 20:
        raise ValueError("chronological ensemble requires at least 20 prior forecasts")
    if not rows:
        return []
    _validate_rows(rows)
    forecasts: list[EnsembleForecast] = []
    for index in range(minimum_history, len(rows)):
        history = rows[:index]
        ranking: list[tuple[float, float, tuple[float, float, float]]] = []
        for weights in ENSEMBLE_WEIGHT_GRID:
            historical_blends = [(_blend(models, weights), actual) for models, actual in history]
            log_loss = sum(
                multiclass_log_loss(probabilities, actual)
                for probabilities, actual in historical_blends
            ) / len(historical_blends)
            brier = sum(
                multiclass_brier(probabilities, actual)
                for probabilities, actual in historical_blends
            ) / len(historical_blends)
            ranking.append((log_loss, brier, weights))
        mean_log_loss, mean_brier_score, weights = min(ranking)
        forecasts.append(
            EnsembleForecast(
                index=index,
                weights=dict(zip(ENSEMBLE_MODELS, weights, strict=True)),
                probabilities=_blend(rows[index][0], weights),
                history_size=len(history),
                history_fingerprint=_history_fingerprint(history),
                mean_log_loss=mean_log_loss,
                mean_brier_score=mean_brier_score,
            )
        )
    return forecasts


def _blend(
    models: dict[str, dict[str, float]],
    weights: tuple[float, float, float],
) -> dict[str, float]:
    return {
        outcome: sum(
            weight * models[model][outcome]
            for model, weight in zip(ENSEMBLE_MODELS, weights, strict=True)
        )
        for outcome in OUTCOMES
    }


def _validate_rows(rows: list[tuple[dict[str, dict[str, float]], str]]) -> None:
    expected = set(ENSEMBLE_MODELS)
    for models, actual in rows:
        if set(models) != expected:
            raise ValueError("ensemble model set must contain Poisson, Elo, and Dixon-Coles")
        if actual not in OUTCOMES:
            raise ValueError(f"actual outcome must be one of {OUTCOMES}")
        for probabilities in models.values():
            if set(probabilities) != set(OUTCOMES):
                raise ValueError(f"model probabilities must contain exactly {OUTCOMES}")
            if any(not math.isfinite(value) or value <= 0 for value in probabilities.values()):
                raise ValueError("model probabilities must be finite and positive")
            if not math.isclose(sum(probabilities.values()), 1.0, abs_tol=1e-9):
                raise ValueError("model probabilities must sum to 1")


def _history_fingerprint(rows: list[tuple[dict[str, dict[str, float]], str]]) -> str:
    payload = [
        {
            "actual": actual,
            "models": {
                model: {outcome: probabilities[model][outcome] for outcome in OUTCOMES}
                for model in ENSEMBLE_MODELS
            },
        }
        for probabilities, actual in rows
    ]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()
