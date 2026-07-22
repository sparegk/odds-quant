from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import minimize  # type: ignore[import-untyped]
from scipy.stats import poisson  # type: ignore[import-untyped]

from app.quant.poisson import derive_market

ScoreMatrix = NDArray[np.float64]


@dataclass(frozen=True)
class DixonColesMatch:
    event_id: int
    home_team_id: int
    away_team_id: int
    kickoff_at: datetime
    observed_at: datetime
    home_goals: int
    away_goals: int


@dataclass(frozen=True)
class DixonColesModel:
    fitted_as_of: datetime
    decay_rate: float
    home_advantage: float
    intercept: float
    rho: float
    attacks: dict[int, float]
    defences: dict[int, float]
    sample_size: int

    def expected_goals(self, home_team_id: int, away_team_id: int) -> tuple[float, float]:
        if home_team_id not in self.attacks or away_team_id not in self.attacks:
            raise ValueError("Dixon-Coles target team is absent from the training window")
        home_lambda = math.exp(
            self.intercept
            + self.home_advantage
            + self.attacks[home_team_id]
            + self.defences[away_team_id]
        )
        away_lambda = math.exp(
            self.intercept + self.attacks[away_team_id] + self.defences[home_team_id]
        )
        return home_lambda, away_lambda

    def probabilities(self, home_team_id: int, away_team_id: int) -> dict[str, float]:
        home_lambda, away_lambda = self.expected_goals(home_team_id, away_team_id)
        return derive_market(
            dixon_coles_score_matrix(home_lambda, away_lambda, self.rho), "MATCH_RESULT"
        )


def fit_dixon_coles(
    matches: list[DixonColesMatch],
    *,
    as_of: datetime,
    decay_rate: float = 0.0018,
) -> DixonColesModel:
    cutoff = _utc(as_of)
    if decay_rate < 0:
        raise ValueError("Dixon-Coles decay_rate cannot be negative")
    event_ids: set[int] = set()
    eligible: list[DixonColesMatch] = []
    for match in matches:
        _validate_match(match)
        if match.event_id in event_ids:
            raise ValueError("Dixon-Coles history contains duplicate event IDs")
        event_ids.add(match.event_id)
        if _utc(match.kickoff_at) < cutoff and _utc(match.observed_at) <= cutoff:
            eligible.append(match)
    if len(eligible) < 4:
        raise ValueError("Dixon-Coles fitting requires at least four known results")

    team_ids = sorted(
        {team_id for match in eligible for team_id in (match.home_team_id, match.away_team_id)}
    )
    if len(team_ids) < 2:
        raise ValueError("Dixon-Coles fitting requires at least two teams")
    team_index = {team_id: index for index, team_id in enumerate(team_ids)}
    team_count = len(team_ids)
    average_goals = max(
        0.1,
        sum(match.home_goals + match.away_goals for match in eligible) / (2 * len(eligible)),
    )
    initial = np.zeros(2 * team_count + 3, dtype=np.float64)
    initial[2 * team_count] = math.log(average_goals)
    initial[2 * team_count + 1] = 0.15
    bounds = [(-3.0, 3.0)] * (2 * team_count) + [(-3.0, 2.0), (-1.0, 1.0), (-0.2, 0.2)]
    constraints = [
        {"type": "eq", "fun": lambda values: float(np.sum(values[:team_count]))},
        {
            "type": "eq",
            "fun": lambda values: float(np.sum(values[team_count : 2 * team_count])),
        },
    ]
    result = minimize(
        _negative_log_likelihood,
        initial,
        args=(eligible, team_index, cutoff, decay_rate),
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"ftol": 1e-10, "maxiter": 1000},
    )
    if not result.success or not np.all(np.isfinite(result.x)):
        raise ValueError(f"Dixon-Coles optimization failed: {result.message}")
    values = result.x
    return DixonColesModel(
        fitted_as_of=cutoff,
        decay_rate=decay_rate,
        home_advantage=float(values[2 * team_count + 1]),
        intercept=float(values[2 * team_count]),
        rho=float(values[2 * team_count + 2]),
        attacks={team_id: float(values[index]) for team_id, index in team_index.items()},
        defences={
            team_id: float(values[team_count + index]) for team_id, index in team_index.items()
        },
        sample_size=len(eligible),
    )


def dixon_coles_score_matrix(
    home_lambda: float,
    away_lambda: float,
    rho: float,
    *,
    max_goals: int = 20,
) -> ScoreMatrix:
    if home_lambda <= 0 or away_lambda <= 0:
        raise ValueError("Dixon-Coles expected goals must be positive")
    if not -0.2 <= rho <= 0.2:
        raise ValueError("Dixon-Coles rho must be between -0.2 and 0.2")
    goals = np.arange(max_goals + 1)
    matrix = np.outer(poisson.pmf(goals, home_lambda), poisson.pmf(goals, away_lambda))
    for home_goals, away_goals in ((0, 0), (0, 1), (1, 0), (1, 1)):
        correction = _tau(home_goals, away_goals, home_lambda, away_lambda, rho)
        if correction <= 0:
            raise ValueError("Dixon-Coles low-score correction is not positive")
        matrix[home_goals, away_goals] *= correction
    total = float(matrix.sum())
    if total <= 0 or not math.isfinite(total):
        raise ValueError("Dixon-Coles score matrix is invalid")
    return np.asarray(matrix / total, dtype=np.float64)


def _negative_log_likelihood(
    values: NDArray[np.float64],
    matches: list[DixonColesMatch],
    team_index: dict[int, int],
    cutoff: datetime,
    decay_rate: float,
) -> float:
    team_count = len(team_index)
    attacks = values[:team_count]
    defences = values[team_count : 2 * team_count]
    intercept = float(values[2 * team_count])
    home_advantage = float(values[2 * team_count + 1])
    rho = float(values[2 * team_count + 2])
    likelihood = 0.0
    for match in matches:
        home_index = team_index[match.home_team_id]
        away_index = team_index[match.away_team_id]
        home_lambda = math.exp(
            intercept + home_advantage + attacks[home_index] + defences[away_index]
        )
        away_lambda = math.exp(intercept + attacks[away_index] + defences[home_index])
        correction = _tau(
            match.home_goals,
            match.away_goals,
            home_lambda,
            away_lambda,
            rho,
        )
        if correction <= 0:
            return 1e12
        age_days = max(0.0, (cutoff - _utc(match.kickoff_at)).total_seconds() / 86400)
        weight = math.exp(-decay_rate * age_days)
        log_probability = (
            poisson.logpmf(match.home_goals, home_lambda)
            + poisson.logpmf(match.away_goals, away_lambda)
            + math.log(correction)
        )
        likelihood -= weight * float(log_probability)
    return likelihood


def _tau(
    home_goals: int,
    away_goals: int,
    home_lambda: float,
    away_lambda: float,
    rho: float,
) -> float:
    if home_goals == 0 and away_goals == 0:
        return 1 - home_lambda * away_lambda * rho
    if home_goals == 0 and away_goals == 1:
        return 1 + home_lambda * rho
    if home_goals == 1 and away_goals == 0:
        return 1 + away_lambda * rho
    if home_goals == 1 and away_goals == 1:
        return 1 - rho
    return 1.0


def _validate_match(match: DixonColesMatch) -> None:
    if match.event_id <= 0 or match.home_team_id <= 0 or match.away_team_id <= 0:
        raise ValueError("Dixon-Coles IDs must be positive")
    if match.home_team_id == match.away_team_id:
        raise ValueError("Dixon-Coles match requires two different teams")
    if match.home_goals < 0 or match.away_goals < 0:
        raise ValueError("Dixon-Coles goals cannot be negative")
    if _utc(match.observed_at) < _utc(match.kickoff_at):
        raise ValueError("Dixon-Coles result cannot be observed before kickoff")


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Dixon-Coles timestamps must include a UTC offset")
    return value.astimezone(UTC)
