from __future__ import annotations

import pytest

from app.quant.ensemble import ENSEMBLE_WEIGHT_GRID, walk_forward_ensemble


def _models() -> dict[str, dict[str, float]]:
    return {
        "poisson": {"HOME": 0.7, "DRAW": 0.2, "AWAY": 0.1},
        "elo": {"HOME": 0.5, "DRAW": 0.3, "AWAY": 0.2},
        "dixon_coles": {"HOME": 0.6, "DRAW": 0.25, "AWAY": 0.15},
    }


def test_ensemble_grid_contains_only_multi_model_simplex_weights() -> None:
    assert len(ENSEMBLE_WEIGHT_GRID) == 12
    assert all(sum(weights) == pytest.approx(1.0) for weights in ENSEMBLE_WEIGHT_GRID)
    assert all(sum(weight > 0 for weight in weights) >= 2 for weights in ENSEMBLE_WEIGHT_GRID)


def test_walk_forward_ensemble_uses_only_prior_outcomes() -> None:
    rows = [(_models(), "HOME") for _ in range(20)] + [(_models(), "AWAY") for _ in range(5)]

    forecasts = walk_forward_ensemble(rows, minimum_history=20)

    assert len(forecasts) == 5
    assert forecasts[0].history_size == 20
    assert len(forecasts[0].history_fingerprint) == 64
    assert sum(forecasts[0].weights.values()) == pytest.approx(1.0)
    assert sum(forecasts[0].probabilities.values()) == pytest.approx(1.0)

    changed_future = rows[:20] + [(_models(), "DRAW") for _ in range(5)]
    repeated = walk_forward_ensemble(changed_future, minimum_history=20)
    assert repeated[0] == forecasts[0]


def test_walk_forward_ensemble_rejects_missing_model() -> None:
    models = _models()
    del models["dixon_coles"]

    with pytest.raises(ValueError, match="model set"):
        walk_forward_ensemble([(models, "HOME") for _ in range(20)], minimum_history=20)
