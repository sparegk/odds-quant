from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass

from scipy.optimize import minimize_scalar  # type: ignore[import-untyped]

from app.quant.evaluation import OUTCOMES, multiclass_log_loss

RECALIBRATION_VERSION = "walk-forward-temperature-scaling-v1"
PROMOTION_POLICY_VERSION = "market-relative-recalibration-v4"


@dataclass(frozen=True)
class TemperatureCalibrator:
    temperature: float
    sample_size: int
    input_fingerprint: str


@dataclass(frozen=True)
class WalkForwardCalibratedObservation:
    index: int
    probabilities: dict[str, float]
    temperature: float
    training_size: int
    training_fingerprint: str


def temperature_scale(
    probabilities: dict[str, float],
    temperature: float,
) -> dict[str, float]:
    _validate_probabilities(probabilities)
    if not math.isfinite(temperature) or temperature <= 0:
        raise ValueError("temperature must be finite and positive")
    powered = {
        outcome: math.exp(math.log(max(probabilities[outcome], 1e-15)) / temperature)
        for outcome in OUTCOMES
    }
    total = sum(powered.values())
    return {outcome: powered[outcome] / total for outcome in OUTCOMES}


def fit_temperature_calibrator(
    rows: list[tuple[dict[str, float], str]],
) -> TemperatureCalibrator:
    if len(rows) < 20:
        raise ValueError("temperature scaling requires at least 20 observations")
    for probabilities, actual in rows:
        _validate_probabilities(probabilities)
        if actual not in OUTCOMES:
            raise ValueError(f"actual outcome must be one of {OUTCOMES}")

    def objective(log_temperature: float) -> float:
        temperature = math.exp(log_temperature)
        return sum(
            multiclass_log_loss(temperature_scale(probabilities, temperature), actual)
            for probabilities, actual in rows
        ) / len(rows)

    result = minimize_scalar(
        objective,
        bounds=(math.log(0.1), math.log(10.0)),
        method="bounded",
        options={"xatol": 1e-10},
    )
    if not result.success or not math.isfinite(float(result.x)):
        raise ValueError("temperature scaling optimization failed")
    return TemperatureCalibrator(
        temperature=math.exp(float(result.x)),
        sample_size=len(rows),
        input_fingerprint=_calibration_fingerprint(rows),
    )


def walk_forward_temperature_scaling(
    rows: list[tuple[dict[str, float], str]],
    *,
    minimum_history: int,
) -> list[WalkForwardCalibratedObservation]:
    if minimum_history < 20:
        raise ValueError("minimum calibration history must be at least 20")
    calibrated: list[WalkForwardCalibratedObservation] = []
    for index in range(minimum_history, len(rows)):
        history = rows[:index]
        calibrator = fit_temperature_calibrator(history)
        calibrated.append(
            WalkForwardCalibratedObservation(
                index=index,
                probabilities=temperature_scale(rows[index][0], calibrator.temperature),
                temperature=calibrator.temperature,
                training_size=calibrator.sample_size,
                training_fingerprint=calibrator.input_fingerprint,
            )
        )
    return calibrated


def _calibration_fingerprint(rows: list[tuple[dict[str, float], str]]) -> str:
    payload = [
        {
            "probabilities": {outcome: probabilities[outcome] for outcome in OUTCOMES},
            "actual": actual,
        }
        for probabilities, actual in rows
    ]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _validate_probabilities(probabilities: dict[str, float]) -> None:
    if set(probabilities) != set(OUTCOMES):
        raise ValueError(f"probabilities must contain exactly {OUTCOMES}")
    if any(
        not math.isfinite(probabilities[outcome]) or probabilities[outcome] <= 0
        for outcome in OUTCOMES
    ):
        raise ValueError("probabilities must be finite and positive")
    if not math.isclose(sum(probabilities.values()), 1.0, abs_tol=1e-9):
        raise ValueError("probabilities must sum to 1")
