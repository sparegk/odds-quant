from __future__ import annotations

import math

import pytest

from app.quant.evaluation import (
    calibration_buckets,
    moving_block_mean_interval,
    multiclass_brier,
    multiclass_log_loss,
    summarize_probabilities,
)


def test_multiclass_proper_scores_have_documented_scale() -> None:
    perfect = {"HOME": 1.0, "DRAW": 0.0, "AWAY": 0.0}
    uniform = {"HOME": 1 / 3, "DRAW": 1 / 3, "AWAY": 1 / 3}

    assert multiclass_brier(perfect, "HOME") == 0
    assert multiclass_log_loss(perfect, "HOME") == 0
    assert multiclass_brier(uniform, "HOME") == pytest.approx(2 / 3)
    assert multiclass_log_loss(uniform, "HOME") == pytest.approx(math.log(3))


def test_calibration_is_bucketed_one_vs_rest_for_every_outcome() -> None:
    observations = [
        ({"HOME": 0.8, "DRAW": 0.1, "AWAY": 0.1}, "HOME"),
        ({"HOME": 0.6, "DRAW": 0.2, "AWAY": 0.2}, "AWAY"),
    ]

    metrics, buckets = summarize_probabilities(observations, bins=5)

    assert metrics["observations"] == 2
    assert metrics["calibration_bins"] == 5
    assert sum(bucket.count for bucket in buckets) == 6
    assert metrics["expected_calibration_error"] == pytest.approx(
        sum(bucket.count * bucket.absolute_error for bucket in buckets) / 6
    )
    assert calibration_buckets(observations, bins=5) == buckets


@pytest.mark.parametrize(
    "probabilities",
    [
        {"HOME": 0.5, "DRAW": 0.5},
        {"HOME": 0.7, "DRAW": 0.2, "AWAY": 0.2},
        {"HOME": -0.1, "DRAW": 0.5, "AWAY": 0.6},
    ],
)
def test_invalid_probability_vectors_are_rejected(
    probabilities: dict[str, float],
) -> None:
    with pytest.raises(ValueError):
        multiclass_brier(probabilities, "HOME")


def test_moving_block_bootstrap_is_deterministic_and_chronology_aware() -> None:
    values = [0.10, 0.12, 0.14, 0.35, 0.37, 0.39, 0.20, 0.22]

    first = moving_block_mean_interval(values, resamples=500, block_length=2, seed=17)
    second = moving_block_mean_interval(values, resamples=500, block_length=2, seed=17)

    assert first == second
    assert first.estimate == pytest.approx(sum(values) / len(values))
    assert first.lower < first.estimate < first.upper
    assert first.block_length == 2
    assert first.observations == len(values)
    assert first.as_dict()["method"] == "moving_block_bootstrap"


def test_moving_block_bootstrap_is_degenerate_for_constant_losses() -> None:
    interval = moving_block_mean_interval([0.25] * 12, resamples=200, seed=9)

    assert interval.estimate == pytest.approx(0.25)
    assert interval.lower == pytest.approx(0.25)
    assert interval.upper == pytest.approx(0.25)
    assert interval.block_length == 2


def test_moving_block_bootstrap_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="at least one observation"):
        moving_block_mean_interval([])
    with pytest.raises(ValueError, match="finite"):
        moving_block_mean_interval([math.nan])
    with pytest.raises(ValueError, match="confidence_level"):
        moving_block_mean_interval([0.1], confidence_level=1)
    with pytest.raises(ValueError, match="at least 100"):
        moving_block_mean_interval([0.1], resamples=99)
    with pytest.raises(ValueError, match="between 1"):
        moving_block_mean_interval([0.1, 0.2], block_length=0)
    with pytest.raises(ValueError, match="must be an integer"):
        moving_block_mean_interval([0.1, 0.2], block_length=1.5)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="seed must be an integer"):
        moving_block_mean_interval([0.1], seed=True)
