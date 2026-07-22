from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.quant.dixon_coles import (
    DixonColesMatch,
    dixon_coles_score_matrix,
    fit_dixon_coles,
)

AS_OF = datetime(2026, 7, 1, tzinfo=UTC)


def history() -> list[DixonColesMatch]:
    scores = [
        (1, 2, 3, 0),
        (3, 4, 1, 1),
        (2, 3, 0, 2),
        (4, 1, 0, 2),
        (1, 3, 2, 0),
        (2, 4, 1, 1),
        (3, 1, 0, 1),
        (4, 2, 1, 2),
        (1, 4, 3, 1),
        (2, 1, 0, 2),
        (3, 2, 2, 1),
        (4, 3, 0, 0),
    ]
    return [
        DixonColesMatch(
            event_id=index,
            home_team_id=home,
            away_team_id=away,
            kickoff_at=AS_OF - timedelta(days=100 - index * 5),
            observed_at=AS_OF - timedelta(days=100 - index * 5, hours=-2),
            home_goals=home_goals,
            away_goals=away_goals,
        )
        for index, (home, away, home_goals, away_goals) in enumerate(scores, start=1)
    ]


def test_dixon_coles_fits_time_weighted_team_strength_and_1x2_probabilities() -> None:
    model = fit_dixon_coles(history(), as_of=AS_OF)
    probabilities = model.probabilities(1, 4)

    assert model.sample_size == 12
    assert sum(probabilities.values()) == pytest.approx(1)
    assert probabilities["HOME"] > probabilities["AWAY"]
    assert set(model.attacks) == {1, 2, 3, 4}
    assert sum(model.attacks.values()) == pytest.approx(0, abs=1e-7)
    assert sum(model.defences.values()) == pytest.approx(0, abs=1e-7)


def test_dixon_coles_excludes_results_not_observed_by_cutoff() -> None:
    matches = history()
    matches.append(
        DixonColesMatch(
            event_id=99,
            home_team_id=4,
            away_team_id=1,
            kickoff_at=AS_OF - timedelta(days=1),
            observed_at=AS_OF + timedelta(hours=1),
            home_goals=9,
            away_goals=0,
        )
    )

    baseline = fit_dixon_coles(history(), as_of=AS_OF)
    cutoff_model = fit_dixon_coles(matches, as_of=AS_OF)

    assert cutoff_model.sample_size == baseline.sample_size
    assert cutoff_model.probabilities(1, 4) == pytest.approx(baseline.probabilities(1, 4))


def test_dixon_coles_low_score_adjustment_is_normalized_and_bounded() -> None:
    matrix = dixon_coles_score_matrix(1.4, 0.9, -0.1)

    assert float(matrix.sum()) == pytest.approx(1)
    assert matrix[0, 0] > 0
    with pytest.raises(ValueError, match="rho"):
        dixon_coles_score_matrix(1.4, 0.9, 0.3)
