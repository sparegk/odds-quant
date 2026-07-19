from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from scipy.stats import poisson  # type: ignore[import-untyped]

from app.quant.odds import fair_odds

ScoreMatrix = NDArray[np.float64]


def score_matrix(home_lambda: float, away_lambda: float, max_goals: int = 20) -> ScoreMatrix:
    if home_lambda <= 0 or away_lambda <= 0:
        raise ValueError("Expected goals must be positive")
    goals = np.arange(max_goals + 1)
    home_probabilities = np.asarray(poisson.pmf(goals, home_lambda), dtype=np.float64)
    away_probabilities = np.asarray(poisson.pmf(goals, away_lambda), dtype=np.float64)
    matrix = np.outer(home_probabilities, away_probabilities)
    omitted = 1.0 - float(matrix.sum())
    if omitted > 1e-8:
        raise ValueError("Score grid omits too much probability mass")
    return np.asarray(matrix / matrix.sum(), dtype=np.float64)


def selection_probability(
    matrix: ScoreMatrix, market_type: str, code: str, line: float | None
) -> float:
    probability = 0.0
    for home_goals in range(matrix.shape[0]):
        for away_goals in range(matrix.shape[1]):
            if selection_wins(home_goals, away_goals, market_type, code, line):
                probability += float(matrix[home_goals, away_goals])
    return probability


def selection_wins(
    home_goals: int, away_goals: int, market_type: str, code: str, line: float | None
) -> bool:
    if market_type == "MATCH_RESULT":
        outcomes = {
            "HOME": home_goals > away_goals,
            "DRAW": home_goals == away_goals,
            "AWAY": home_goals < away_goals,
        }
        if code not in outcomes:
            raise ValueError(f"Unsupported MATCH_RESULT selection: {code}")
        return outcomes[code]
    if market_type in {"BTTS", "BOTH_TEAMS_TO_SCORE"}:
        if code not in {"YES", "NO"}:
            raise ValueError(f"Unsupported {market_type} selection: {code}")
        yes = home_goals > 0 and away_goals > 0
        return yes if code == "YES" else not yes
    if market_type == "DOUBLE_CHANCE":
        outcomes = {
            "HOME_OR_DRAW": home_goals >= away_goals,
            "DRAW_OR_AWAY": home_goals <= away_goals,
            "AWAY_OR_DRAW": home_goals <= away_goals,
            "HOME_OR_AWAY": home_goals != away_goals,
        }
        if code not in outcomes:
            raise ValueError(f"Unsupported DOUBLE_CHANCE selection: {code}")
        return outcomes[code]
    if line is None:
        raise ValueError(f"{market_type} requires a line")
    goals = home_goals + away_goals
    if market_type in {"HOME_TEAM_TOTAL", "TEAM_TOTAL_HOME"}:
        goals = home_goals
    elif market_type in {"AWAY_TEAM_TOTAL", "TEAM_TOTAL_AWAY"}:
        goals = away_goals
    elif market_type != "TOTAL_GOALS":
        raise ValueError(f"Unsupported market type: {market_type}")
    if code not in {"OVER", "UNDER"}:
        raise ValueError(f"Unsupported {market_type} selection: {code}")
    return goals > line if code == "OVER" else goals < line


def derive_market(
    matrix: ScoreMatrix, market_type: str, line: float | None = None
) -> dict[str, float]:
    codes = {
        "MATCH_RESULT": ["HOME", "DRAW", "AWAY"],
        "TOTAL_GOALS": ["OVER", "UNDER"],
        "BTTS": ["YES", "NO"],
        "BOTH_TEAMS_TO_SCORE": ["YES", "NO"],
        "DOUBLE_CHANCE": ["HOME_OR_DRAW", "DRAW_OR_AWAY", "HOME_OR_AWAY"],
        "HOME_TEAM_TOTAL": ["OVER", "UNDER"],
        "AWAY_TEAM_TOTAL": ["OVER", "UNDER"],
        "TEAM_TOTAL_HOME": ["OVER", "UNDER"],
        "TEAM_TOTAL_AWAY": ["OVER", "UNDER"],
    }.get(market_type)
    if codes is None:
        raise ValueError(f"Unsupported market type: {market_type}")
    return {code: selection_probability(matrix, market_type, code, line) for code in codes}


def _line_value(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Bet-builder lines must be numeric")
    return float(value)


def joint_probability(matrix: ScoreMatrix, legs: list[dict[str, object]]) -> float:
    if not 2 <= len(legs) <= 4:
        raise ValueError("Bet builder requires two to four legs")
    normalized = [
        (str(x["market_type"]), str(x["selection"]), _line_value(x.get("line"))) for x in legs
    ]
    if len(normalized) != len(set(normalized)):
        raise ValueError("Duplicate legs are not supported")
    probability = 0.0
    for home_goals in range(matrix.shape[0]):
        for away_goals in range(matrix.shape[1]):
            if all(
                selection_wins(
                    home_goals,
                    away_goals,
                    market_type,
                    code,
                    line,
                )
                for market_type, code, line in normalized
            ):
                probability += float(matrix[home_goals, away_goals])
    return probability


def evaluate_builder(
    matrix: ScoreMatrix, legs: list[dict[str, object]], offered_odds: float | None
) -> dict[str, object]:
    marginals = [
        selection_probability(
            matrix,
            str(leg["market_type"]),
            str(leg["selection"]),
            _line_value(leg.get("line")),
        )
        for leg in legs
    ]
    joint = joint_probability(matrix, legs)
    independent = float(np.prod(marginals))
    ratio = joint / independent if independent else 0.0
    return {
        "leg_probabilities": marginals,
        "independent_product": independent,
        "joint_probability": joint,
        "fair_odds": fair_odds(joint) if joint else None,
        "offered_odds": offered_odds,
        "expected_value": joint * offered_odds - 1 if offered_odds else None,
        "dependence_ratio": ratio,
        "dependence_warning": (
            "Legs are correlated; joint probability is summed from scorelines, not multiplied."
        ),
        "uncertainty": (
            "Parameter uncertainty is wider than the conditional scoreline uncertainty shown here."
        ),
    }
