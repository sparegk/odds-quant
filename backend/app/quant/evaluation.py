from __future__ import annotations

import math
import random
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


@dataclass(frozen=True)
class BootstrapMeanInterval:
    estimate: float
    lower: float
    upper: float
    confidence_level: float
    resamples: int
    block_length: int
    observations: int
    seed: int

    def as_dict(self) -> dict[str, object]:
        return {
            "method": "moving_block_bootstrap",
            **asdict(self),
        }


def moving_block_mean_interval(
    values: list[float],
    *,
    confidence_level: float = 0.95,
    resamples: int = 2000,
    block_length: int | None = None,
    seed: int = 0,
) -> BootstrapMeanInterval:
    observations = [float(value) for value in values]
    if not observations:
        raise ValueError("bootstrap requires at least one observation")
    if any(not math.isfinite(value) for value in observations):
        raise ValueError("bootstrap observations must be finite")
    if (
        isinstance(confidence_level, bool)
        or not isinstance(confidence_level, (int, float))
        or not math.isfinite(confidence_level)
        or not 0 < confidence_level < 1
    ):
        raise ValueError("bootstrap confidence_level must be in (0, 1)")
    if isinstance(resamples, bool) or not isinstance(resamples, int) or resamples < 100:
        raise ValueError("bootstrap requires at least 100 resamples")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("bootstrap seed must be an integer")

    count = len(observations)
    if block_length is None:
        selected_block_length = min(count, max(1, round(count ** (1 / 3))))
    else:
        if isinstance(block_length, bool) or not isinstance(block_length, int):
            raise ValueError("bootstrap block_length must be an integer")
        selected_block_length = block_length
    if not 1 <= selected_block_length <= count:
        raise ValueError("bootstrap block_length must be between 1 and the sample size")

    generator = random.Random(seed)
    bootstrap_means: list[float] = []
    latest_start = count - selected_block_length
    for _ in range(resamples):
        sample: list[float] = []
        while len(sample) < count:
            start = generator.randint(0, latest_start)
            remaining = count - len(sample)
            sample.extend(observations[start : start + min(selected_block_length, remaining)])
        bootstrap_means.append(sum(sample) / count)
    bootstrap_means.sort()

    tail_probability = (1 - confidence_level) / 2
    return BootstrapMeanInterval(
        estimate=sum(observations) / count,
        lower=_percentile(bootstrap_means, tail_probability),
        upper=_percentile(bootstrap_means, 1 - tail_probability),
        confidence_level=confidence_level,
        resamples=resamples,
        block_length=selected_block_length,
        observations=count,
        seed=seed,
    )


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


def _percentile(sorted_values: list[float], probability: float) -> float:
    position = (len(sorted_values) - 1) * probability
    lower_index = math.floor(position)
    upper_index = math.ceil(position)
    weight = position - lower_index
    return sorted_values[lower_index] * (1 - weight) + sorted_values[upper_index] * weight


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
