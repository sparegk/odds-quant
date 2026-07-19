from __future__ import annotations

import numpy as np
import pytest

from app.quant.poisson import derive_market, joint_probability, score_matrix, selection_probability
from app.quant.team_strength import HistoricalScore, fit_poisson_team_strength


def test_score_matrix_and_canonical_markets_are_coherent() -> None:
    matrix = score_matrix(1.65, 0.9)

    assert float(matrix.sum()) == pytest.approx(1.0)
    assert sum(derive_market(matrix, "MATCH_RESULT").values()) == pytest.approx(1.0)
    assert sum(derive_market(matrix, "TOTAL_GOALS", 2.5).values()) == pytest.approx(1.0)
    assert sum(derive_market(matrix, "BOTH_TEAMS_TO_SCORE").values()) == pytest.approx(1.0)
    assert sum(derive_market(matrix, "TEAM_TOTAL_HOME", 1.5).values()) == pytest.approx(1.0)
    assert selection_probability(matrix, "DOUBLE_CHANCE", "AWAY_OR_DRAW", None) == pytest.approx(
        selection_probability(matrix, "DOUBLE_CHANCE", "DRAW_OR_AWAY", None)
    )


def test_invalid_selection_is_rejected_instead_of_treated_as_under() -> None:
    matrix = score_matrix(1.2, 1.0)

    with pytest.raises(ValueError, match="Unsupported TOTAL_GOALS selection"):
        selection_probability(matrix, "TOTAL_GOALS", "INVALID", 2.5)


def test_team_strength_is_shrunk_and_produces_positive_expected_goals() -> None:
    matches = [
        HistoricalScore(1, 2, 3, 0),
        HistoricalScore(2, 1, 0, 2),
        HistoricalScore(1, 3, 2, 1),
        HistoricalScore(3, 1, 1, 2),
        HistoricalScore(2, 3, 1, 1),
        HistoricalScore(3, 2, 1, 0),
    ]

    model = fit_poisson_team_strength(matches, shrinkage_matches=4)
    home_lambda, away_lambda = model.expected_goals(1, 2)

    assert model.sample_size == 6
    assert model.teams[1].home_attack > model.teams[2].home_attack
    assert 0.05 <= home_lambda <= 4
    assert 0.05 <= away_lambda <= 4


def test_joint_probability_uses_scorelines_not_marginal_product() -> None:
    matrix = score_matrix(1.8, 0.8)
    legs: list[dict[str, object]] = [
        {"market_type": "MATCH_RESULT", "selection": "HOME"},
        {"market_type": "TOTAL_GOALS", "selection": "OVER", "line": 2.5},
    ]
    joint = joint_probability(matrix, legs)
    independent = np.prod(
        [
            selection_probability(matrix, "MATCH_RESULT", "HOME", None),
            selection_probability(matrix, "TOTAL_GOALS", "OVER", 2.5),
        ]
    )

    assert joint != pytest.approx(float(independent))
