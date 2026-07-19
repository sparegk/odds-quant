from __future__ import annotations

import math
from dataclasses import asdict, dataclass

OUTCOMES = ("HOME", "DRAW", "AWAY")


@dataclass(frozen=True)
class CalibrationBucket:
    selection_code: str
    bucket_index: int
    lower_bound: float
    upper_bound: float
    count: int
    mean_predicted: float
    observed_frequency: float
    absolute_error: float

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def multiclass_brier(probabilities: dict[str, float], actual_outcome: str) -> float:
    values = _validated(probabilities, actual_outcome)
    return sum(
        (values[outcome] - (1.0 if outcome == actual_outcome else 0.0)) ** 2 for outcome in OUTCOMES
    )


def multiclass_log_loss(probabilities: dict[str, float], actual_outcome: str) -> float:
    values = _validated(probabilities, actual_outcome)
    return -math.log(max(values[actual_outcome], 1e-15))


def summarize_probabilities(
    observations: list[tuple[dict[str, float], str]],
    *,
    bins: int,
) -> tuple[dict[str, object], list[CalibrationBucket]]:
    if not observations:
        raise ValueError("at least one probability observation is required")
    if not 2 <= bins <= 50:
        raise ValueError("calibration bins must be between 2 and 50")
    for probabilities, actual in observations:
        _validated(probabilities, actual)

    brier_scores = [
        multiclass_brier(probabilities, actual) for probabilities, actual in observations
    ]
    log_losses = [
        multiclass_log_loss(probabilities, actual) for probabilities, actual in observations
    ]
    accuracy = sum(
        max(OUTCOMES, key=probabilities.__getitem__) == actual
        for probabilities, actual in observations
    ) / len(observations)
    buckets = calibration_buckets(observations, bins=bins)
    total_binary_predictions = len(observations) * len(OUTCOMES)
    expected_calibration_error = (
        sum(bucket.count * bucket.absolute_error for bucket in buckets) / total_binary_predictions
    )
    return (
        {
            "observations": len(observations),
            "brier_score": sum(brier_scores) / len(brier_scores),
            "log_loss": sum(log_losses) / len(log_losses),
            "accuracy": accuracy,
            "expected_calibration_error": expected_calibration_error,
            "calibration_bins": bins,
            "outcome_counts": {
                outcome: sum(actual == outcome for _, actual in observations)
                for outcome in OUTCOMES
            },
        },
        buckets,
    )


def calibration_buckets(
    observations: list[tuple[dict[str, float], str]],
    *,
    bins: int,
) -> list[CalibrationBucket]:
    grouped: dict[tuple[str, int], list[tuple[float, int]]] = {}
    for probabilities, actual in observations:
        values = _validated(probabilities, actual)
        for outcome in OUTCOMES:
            probability = values[outcome]
            index = min(int(probability * bins), bins - 1)
            grouped.setdefault((outcome, index), []).append((probability, int(actual == outcome)))

    buckets: list[CalibrationBucket] = []
    for (outcome, index), bucket_values in sorted(grouped.items()):
        count = len(bucket_values)
        mean_predicted = sum(value[0] for value in bucket_values) / count
        observed_frequency = sum(value[1] for value in bucket_values) / count
        buckets.append(
            CalibrationBucket(
                selection_code=outcome,
                bucket_index=index,
                lower_bound=index / bins,
                upper_bound=(index + 1) / bins,
                count=count,
                mean_predicted=mean_predicted,
                observed_frequency=observed_frequency,
                absolute_error=abs(mean_predicted - observed_frequency),
            )
        )
    return buckets


def _validated(
    probabilities: dict[str, float],
    actual_outcome: str,
) -> dict[str, float]:
    if actual_outcome not in OUTCOMES:
        raise ValueError(f"unsupported actual outcome: {actual_outcome}")
    if set(probabilities) != set(OUTCOMES):
        raise ValueError("probabilities must contain exactly HOME, DRAW, and AWAY")
    values = {outcome: float(probabilities[outcome]) for outcome in OUTCOMES}
    if any(not math.isfinite(value) or value < 0 or value > 1 for value in values.values()):
        raise ValueError("probabilities must be finite values in [0, 1]")
    if not math.isclose(sum(values.values()), 1.0, abs_tol=1e-9):
        raise ValueError("probabilities must sum to one")
    return values
