import pytest

from app.quant.team_strength import HistoricalScore
from app.quant.uncertainty import (
    bootstrap_probability_interval,
    chronological_block_bootstrap_expected_goals,
)


def history(rounds: int = 20) -> list[HistoricalScore]:
    rows: list[HistoricalScore] = []
    for index in range(rounds):
        rows.extend(
            [
                HistoricalScore(1, 2, 2 + index % 2, 1),
                HistoricalScore(3, 4, 1, index % 2),
                HistoricalScore(2, 3, 1, 1),
                HistoricalScore(4, 1, 0, 2),
            ]
        )
    return rows


def test_block_bootstrap_is_deterministic_and_does_not_mutate_history() -> None:
    matches = history()
    original = list(matches)
    first = chronological_block_bootstrap_expected_goals(
        matches,
        home_team_id=1,
        away_team_id=2,
        shrinkage_matches=5,
        resamples=120,
        seed_material="training-fingerprint:event-7:uncertainty-v1",
    )
    repeated = chronological_block_bootstrap_expected_goals(
        matches,
        home_team_id=1,
        away_team_id=2,
        shrinkage_matches=5,
        resamples=120,
        seed_material="training-fingerprint:event-7:uncertainty-v1",
    )

    assert first == repeated
    assert matches == original
    assert first.block_length == round(len(matches) ** 0.5)
    assert len(first.samples) == 120
    assert all(home > 0 and away > 0 for home, away in first.samples)


def test_probability_interval_uses_empirical_quantiles_and_contains_point() -> None:
    samples = [index / 100 for index in range(100)]

    lower, upper = bootstrap_probability_interval(
        0.9,
        samples,
        confidence_level=0.8,
    )

    assert lower == pytest.approx(0.099)
    assert upper == pytest.approx(0.9)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"matches": history(0)}, "at least four"),
        ({"home_team_id": 1, "away_team_id": 1}, "different teams"),
        ({"resamples": 99}, "at least 100"),
        ({"block_length": 10_000}, "block length"),
    ],
)
def test_block_bootstrap_rejects_invalid_configuration(
    change: dict[str, object], message: str
) -> None:
    values: dict[str, object] = {
        "matches": history(),
        "home_team_id": 1,
        "away_team_id": 2,
        "shrinkage_matches": 5,
        "resamples": 100,
        "seed_material": "seed",
    }
    values.update(change)

    with pytest.raises(ValueError, match=message):
        chronological_block_bootstrap_expected_goals(**values)  # type: ignore[arg-type]
