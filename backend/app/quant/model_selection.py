from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass

from app.quant.evaluation import OUTCOMES, multiclass_brier, multiclass_log_loss

NESTED_SELECTION_VERSION = "chronological-candidate-selection-v1"


@dataclass(frozen=True)
class SelectedCandidateForecast:
    index: int
    candidate: str
    probabilities: dict[str, float]
    history_size: int
    history_fingerprint: str
    mean_log_loss: float
    mean_brier_score: float


def walk_forward_candidate_selection(
    rows: list[tuple[dict[str, dict[str, float]], str]],
    *,
    minimum_history: int,
) -> list[SelectedCandidateForecast]:
    if minimum_history < 20:
        raise ValueError("nested candidate selection requires at least 20 prior forecasts")
    if not rows:
        return []
    candidate_names = _validate_rows(rows)
    selected: list[SelectedCandidateForecast] = []
    for index in range(minimum_history, len(rows)):
        history = rows[:index]
        ranking: list[tuple[float, float, str]] = []
        for candidate in candidate_names:
            log_loss = sum(
                multiclass_log_loss(probabilities[candidate], actual)
                for probabilities, actual in history
            ) / len(history)
            brier = sum(
                multiclass_brier(probabilities[candidate], actual)
                for probabilities, actual in history
            ) / len(history)
            ranking.append((log_loss, brier, candidate))
        mean_log_loss, mean_brier_score, candidate = min(ranking)
        selected.append(
            SelectedCandidateForecast(
                index=index,
                candidate=candidate,
                probabilities=rows[index][0][candidate],
                history_size=len(history),
                history_fingerprint=_history_fingerprint(history),
                mean_log_loss=mean_log_loss,
                mean_brier_score=mean_brier_score,
            )
        )
    return selected


def _validate_rows(rows: list[tuple[dict[str, dict[str, float]], str]]) -> tuple[str, ...]:
    candidate_names = tuple(sorted(rows[0][0]))
    if len(candidate_names) < 2:
        raise ValueError("nested selection requires at least two candidates")
    expected = set(candidate_names)
    for candidates, actual in rows:
        if set(candidates) != expected:
            raise ValueError("nested selection candidate set changed within the replay")
        if actual not in OUTCOMES:
            raise ValueError(f"actual outcome must be one of {OUTCOMES}")
        for probabilities in candidates.values():
            if set(probabilities) != set(OUTCOMES):
                raise ValueError(f"candidate probabilities must contain exactly {OUTCOMES}")
            if any(not math.isfinite(value) or value <= 0 for value in probabilities.values()):
                raise ValueError("candidate probabilities must be finite and positive")
            if not math.isclose(sum(probabilities.values()), 1.0, abs_tol=1e-9):
                raise ValueError("candidate probabilities must sum to 1")
    return candidate_names


def _history_fingerprint(rows: list[tuple[dict[str, dict[str, float]], str]]) -> str:
    payload = [
        {
            "actual": actual,
            "candidates": {
                candidate: {outcome: probabilities[candidate][outcome] for outcome in OUTCOMES}
                for candidate in sorted(probabilities)
            },
        }
        for probabilities, actual in rows
    ]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()
