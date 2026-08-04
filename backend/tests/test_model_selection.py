from __future__ import annotations

import pytest

from app.quant.model_selection import walk_forward_candidate_selection


def test_walk_forward_selection_uses_only_prior_candidate_outcomes() -> None:
    rows = []
    for index in range(25):
        actual = "HOME" if index < 20 else "AWAY"
        rows.append(
            (
                {
                    "home_model": {"HOME": 0.8, "DRAW": 0.1, "AWAY": 0.1},
                    "away_model": {"HOME": 0.1, "DRAW": 0.1, "AWAY": 0.8},
                },
                actual,
            )
        )

    selected = walk_forward_candidate_selection(rows, minimum_history=20)

    assert len(selected) == 5
    assert selected[0].candidate == "home_model"
    assert selected[0].history_size == 20
    assert len(selected[0].history_fingerprint) == 64
    assert selected[0].probabilities["HOME"] == pytest.approx(0.8)

    changed_future = rows[:20] + [
        (
            candidates,
            "DRAW",
        )
        for candidates, _ in rows[20:]
    ]
    repeated = walk_forward_candidate_selection(changed_future, minimum_history=20)
    assert repeated[0] == selected[0]


def test_walk_forward_selection_rejects_candidate_drift() -> None:
    probabilities = {
        "a": {"HOME": 0.4, "DRAW": 0.3, "AWAY": 0.3},
        "b": {"HOME": 0.3, "DRAW": 0.3, "AWAY": 0.4},
    }
    rows = [(probabilities, "HOME") for _ in range(20)]
    rows.append(({"a": probabilities["a"]}, "HOME"))

    with pytest.raises(ValueError, match="candidate set changed"):
        walk_forward_candidate_selection(rows, minimum_history=20)
