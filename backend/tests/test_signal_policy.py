from __future__ import annotations

import pytest

from app.signals.policy import SignalInput, classify_signal


def _input(**overrides: float | int) -> SignalInput:
    values: dict[str, float | int] = {
        "offered_odds": 2.5,
        "market_probability": 0.38,
        "model_probability": 0.45,
        "lower_probability": 0.42,
        "sample_size_per_team": 20,
        "calibration_error": 0.04,
        "age_minutes": 5,
        "bookmaker_count": 3,
        "odds_move_ratio": 0,
        "implied_move_points": 0,
    }
    values.update(overrides)
    return SignalInput(**values)  # type: ignore[arg-type]


def test_value_requires_positive_lower_bound_ev_and_reliability() -> None:
    result = classify_signal(_input())

    assert result["signal"] == "VALUE"
    assert result["expected_value"] == pytest.approx(0.125)
    assert result["lower_expected_value"] == pytest.approx(0.05)
    assert result["edge"] == pytest.approx(0.07)


def test_uncertainty_and_movement_prevent_strong_value() -> None:
    uncertain = classify_signal(_input(lower_probability=0.35))
    moved = classify_signal(_input(odds_move_ratio=0.12))

    assert uncertain["signal"] == "WATCH"
    assert uncertain["lower_expected_value"] < 0  # type: ignore[operator]
    assert moved["signal"] == "WATCH"
    risks = moved["risks"]
    assert isinstance(risks, list)
    assert any(isinstance(risk, str) and "moved" in risk for risk in risks)


def test_stale_or_uncalibrated_inputs_are_insufficient() -> None:
    assert classify_signal(_input(age_minutes=61))["signal"] == "INSUFFICIENT_DATA"
    assert classify_signal(_input(calibration_error=0.11))["signal"] == "INSUFFICIENT_DATA"


@pytest.mark.parametrize(
    "overrides",
    [
        {"offered_odds": 1.0},
        {"model_probability": 1.1},
        {"lower_probability": 0.6},
        {"age_minutes": -1},
    ],
)
def test_invalid_signal_inputs_are_rejected(overrides: dict[str, float]) -> None:
    with pytest.raises(ValueError):
        _input(**overrides)
