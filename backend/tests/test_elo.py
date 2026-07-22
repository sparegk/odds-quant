from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.quant.elo import EloConfig, EloMatchResult, elo_probabilities_as_of

KICKOFF = datetime(2026, 1, 1, 15, 0, tzinfo=UTC)


def result(
    event_id: int,
    home_team_id: int,
    away_team_id: int,
    home_goals: int,
    away_goals: int,
    *,
    kickoff_offset: int,
    observed_offset: int,
) -> EloMatchResult:
    return EloMatchResult(
        event_id=event_id,
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        kickoff_at=KICKOFF + timedelta(days=kickoff_offset),
        observed_at=KICKOFF + timedelta(days=observed_offset),
        home_goals=home_goals,
        away_goals=away_goals,
    )


def test_elo_forecast_is_a_draw_aware_probability_distribution() -> None:
    forecast = elo_probabilities_as_of(
        [], home_team_id=1, away_team_id=2, as_of=KICKOFF, config=EloConfig(home_advantage=0)
    )

    assert sum(forecast.probabilities.values()) == pytest.approx(1)
    assert forecast.probabilities == pytest.approx({"HOME": 0.37, "DRAW": 0.26, "AWAY": 0.37})
    assert forecast.results_used == 0


def test_elo_uses_only_results_observed_by_the_forecast_cutoff() -> None:
    history = [
        result(1, 1, 2, 3, 0, kickoff_offset=-4, observed_offset=-3),
        result(2, 1, 2, 0, 4, kickoff_offset=-2, observed_offset=1),
    ]

    forecast = elo_probabilities_as_of(
        history, home_team_id=1, away_team_id=2, as_of=KICKOFF, config=EloConfig(home_advantage=0)
    )
    leaked = elo_probabilities_as_of(
        history,
        home_team_id=1,
        away_team_id=2,
        as_of=KICKOFF + timedelta(days=2),
        config=EloConfig(home_advantage=0),
    )

    assert forecast.results_used == 1
    assert forecast.home_rating > forecast.away_rating
    assert forecast.probabilities["HOME"] > forecast.probabilities["AWAY"]
    assert leaked.results_used == 2
    assert leaked.home_rating < forecast.home_rating


def test_elo_rejects_invalid_point_in_time_history() -> None:
    invalid = result(1, 1, 2, 1, 0, kickoff_offset=-1, observed_offset=-2)

    with pytest.raises(ValueError, match="observed before kickoff"):
        elo_probabilities_as_of([invalid], home_team_id=1, away_team_id=2, as_of=KICKOFF)

    with pytest.raises(ValueError, match="UTC offset"):
        elo_probabilities_as_of([], home_team_id=1, away_team_id=2, as_of=datetime(2026, 1, 1))
