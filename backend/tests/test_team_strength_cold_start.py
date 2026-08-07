import pytest

from app.quant.team_strength import HistoricalScore, fit_poisson_team_strength


def test_cold_start_uses_league_prior_only_for_unseen_team() -> None:
    model = fit_poisson_team_strength(
        [
            HistoricalScore(1, 2, 2, 0),
            HistoricalScore(2, 1, 1, 1),
            HistoricalScore(1, 3, 3, 1),
            HistoricalScore(3, 2, 0, 2),
        ],
        shrinkage_matches=5,
    )

    forecast = model.expected_goals_with_league_priors(99, 2)

    assert forecast.home_lambda == pytest.approx(
        model.league_home_goals * model.teams[2].away_defence
    )
    assert forecast.away_lambda == pytest.approx(
        model.league_away_goals * model.teams[2].away_attack
    )
    assert forecast.home_venue_matches == 0
    assert forecast.away_venue_matches == model.teams[2].away_matches
    assert forecast.home_used_league_prior is True
    assert forecast.away_used_league_prior is False


def test_strict_expected_goals_still_rejects_unseen_team() -> None:
    model = fit_poisson_team_strength([HistoricalScore(1, 2, 1, 0), HistoricalScore(2, 1, 0, 1)])

    with pytest.raises(ValueError, match="team 99 is absent from the training window"):
        model.expected_goals(99, 2)
