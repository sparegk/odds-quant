from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class EloConfig:
    initial_rating: float = 1500.0
    k_factor: float = 20.0
    scale: float = 400.0
    home_advantage: float = 75.0
    draw_probability_at_even_strength: float = 0.26

    def __post_init__(self) -> None:
        if self.k_factor <= 0 or self.scale <= 0:
            raise ValueError("Elo k_factor and scale must be positive")
        if not 0 < self.draw_probability_at_even_strength < 1:
            raise ValueError("Elo draw probability must be in (0, 1)")


@dataclass(frozen=True)
class EloMatchResult:
    event_id: int
    home_team_id: int
    away_team_id: int
    kickoff_at: datetime
    observed_at: datetime
    home_goals: int
    away_goals: int


@dataclass(frozen=True)
class EloForecast:
    probabilities: dict[str, float]
    home_rating: float
    away_rating: float
    results_used: int


def elo_probabilities_as_of(
    results: list[EloMatchResult],
    *,
    home_team_id: int,
    away_team_id: int,
    as_of: datetime,
    config: EloConfig | None = None,
) -> EloForecast:
    """Fit ratings from results known by ``as_of`` and forecast a 1X2 match.

    Result availability, rather than fixture order alone, controls eligibility. This
    keeps late settlements and corrections out of earlier forecasts.
    """
    settings = config or EloConfig()
    cutoff = _utc(as_of)
    if home_team_id == away_team_id:
        raise ValueError("Elo forecast requires two different teams")

    event_ids: set[int] = set()
    eligible: list[EloMatchResult] = []
    for result in results:
        _validate_result(result)
        if result.event_id in event_ids:
            raise ValueError("Elo history contains duplicate event IDs")
        event_ids.add(result.event_id)
        if _utc(result.kickoff_at) < cutoff and _utc(result.observed_at) <= cutoff:
            eligible.append(result)

    ratings: dict[int, float] = {}
    for result in sorted(eligible, key=lambda item: (_utc(item.observed_at), item.event_id)):
        home_rating = ratings.get(result.home_team_id, settings.initial_rating)
        away_rating = ratings.get(result.away_team_id, settings.initial_rating)
        probabilities = _probabilities(home_rating, away_rating, settings)
        expected_home_score = probabilities["HOME"] + 0.5 * probabilities["DRAW"]
        actual_home_score = (
            1.0
            if result.home_goals > result.away_goals
            else 0.5
            if result.home_goals == result.away_goals
            else 0.0
        )
        adjustment = settings.k_factor * (actual_home_score - expected_home_score)
        ratings[result.home_team_id] = home_rating + adjustment
        ratings[result.away_team_id] = away_rating - adjustment

    home_rating = ratings.get(home_team_id, settings.initial_rating)
    away_rating = ratings.get(away_team_id, settings.initial_rating)
    return EloForecast(
        probabilities=_probabilities(home_rating, away_rating, settings),
        home_rating=home_rating,
        away_rating=away_rating,
        results_used=len(eligible),
    )


def _probabilities(
    home_rating: float,
    away_rating: float,
    config: EloConfig,
) -> dict[str, float]:
    strength_ratio = 10 ** ((home_rating + config.home_advantage - away_rating) / config.scale)
    root_ratio = math.sqrt(strength_ratio)
    draw_parameter = (
        2
        * config.draw_probability_at_even_strength
        / (1 - config.draw_probability_at_even_strength)
    )
    denominator = strength_ratio + 1 + draw_parameter * root_ratio
    return {
        "HOME": strength_ratio / denominator,
        "DRAW": draw_parameter * root_ratio / denominator,
        "AWAY": 1 / denominator,
    }


def _validate_result(result: EloMatchResult) -> None:
    if result.event_id <= 0 or result.home_team_id <= 0 or result.away_team_id <= 0:
        raise ValueError("Elo result IDs must be positive")
    if result.home_team_id == result.away_team_id:
        raise ValueError("Elo result requires two different teams")
    if result.home_goals < 0 or result.away_goals < 0:
        raise ValueError("Elo result goals cannot be negative")
    kickoff = _utc(result.kickoff_at)
    observed = _utc(result.observed_at)
    if observed < kickoff:
        raise ValueError("Elo result cannot be observed before kickoff")


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Elo timestamps must include a UTC offset")
    return value.astimezone(UTC)
