import pytest

from app.quant.calibration import (
    fit_temperature_calibrator,
    temperature_scale,
    walk_forward_temperature_scaling,
)
from app.quant.evaluation import multiclass_log_loss


def overconfident_rows(count: int = 90) -> list[tuple[dict[str, float], str]]:
    outcomes = ("HOME", "DRAW", "AWAY")
    rows: list[tuple[dict[str, float], str]] = []
    for index in range(count):
        predicted = outcomes[index % 3]
        actual = outcomes[(index + (1 if index % 4 == 0 else 0)) % 3]
        probabilities = {outcome: 0.05 for outcome in outcomes}
        probabilities[predicted] = 0.90
        rows.append((probabilities, actual))
    return rows


def test_temperature_scaling_preserves_probability_mass_and_order() -> None:
    raw = {"HOME": 0.6, "DRAW": 0.25, "AWAY": 0.15}

    scaled = temperature_scale(raw, 2.0)

    assert sum(scaled.values()) == pytest.approx(1)
    assert scaled["HOME"] > scaled["DRAW"] > scaled["AWAY"]
    assert scaled["HOME"] < raw["HOME"]
    assert temperature_scale(raw, 1.0) == pytest.approx(raw)


def test_fitted_temperature_improves_overconfident_training_log_loss() -> None:
    rows = overconfident_rows()

    calibrator = fit_temperature_calibrator(rows)
    raw_loss = sum(multiclass_log_loss(row, actual) for row, actual in rows) / len(rows)
    scaled_loss = sum(
        multiclass_log_loss(temperature_scale(row, calibrator.temperature), actual)
        for row, actual in rows
    ) / len(rows)

    assert calibrator.temperature > 1
    assert scaled_loss < raw_loss
    assert len(calibrator.input_fingerprint) == 64


def test_walk_forward_calibration_never_uses_current_or_future_outcomes() -> None:
    rows = overconfident_rows()
    original = walk_forward_temperature_scaling(rows, minimum_history=30)
    changed = list(rows)
    changed[50] = (changed[50][0], "HOME" if changed[50][1] != "HOME" else "AWAY")
    repeated = walk_forward_temperature_scaling(changed, minimum_history=30)

    before_changed_outcome = [item for item in original if item.index <= 50]
    repeated_before = [item for item in repeated if item.index <= 50]
    assert before_changed_outcome == repeated_before
    assert original[0].training_size == 30
    assert original[0].index == 30


def test_temperature_scaling_rejects_incomplete_probabilities() -> None:
    with pytest.raises(ValueError, match="exactly"):
        temperature_scale({"HOME": 0.5, "DRAW": 0.5}, 1.0)
