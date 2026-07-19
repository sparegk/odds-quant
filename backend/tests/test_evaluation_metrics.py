from __future__ import annotations

import math

import pytest

from app.quant.evaluation import (
    calibration_buckets,
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
