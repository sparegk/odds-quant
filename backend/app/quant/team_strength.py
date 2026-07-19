from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HistoricalScore:
    home_team_id: int
    away_team_id: int
    home_goals: int
    away_goals: int


@dataclass(frozen=True)
class TeamStrength:
    home_attack: float
    home_defence: float
    away_attack: float
    away_defence: float
    home_matches: int
    away_matches: int


@dataclass(frozen=True)
class PoissonTeamStrengthModel:
    league_home_goals: float
    league_away_goals: float
    shrinkage_matches: float
    sample_size: int
    teams: dict[int, TeamStrength]

    def expected_goals(self, home_team_id: int, away_team_id: int) -> tuple[float, float]:
        try:
            home = self.teams[home_team_id]
            away = self.teams[away_team_id]
        except KeyError as exc:
            raise ValueError(f"team {exc.args[0]} is absent from the training window") from exc
        home_lambda = self.league_home_goals * home.home_attack * away.away_defence
        away_lambda = self.league_away_goals * away.away_attack * home.home_defence
        return (_bounded_lambda(home_lambda), _bounded_lambda(away_lambda))


def fit_poisson_team_strength(
    matches: list[HistoricalScore],
    *,
    shrinkage_matches: float = 5.0,
) -> PoissonTeamStrengthModel:
    if not matches:
        raise ValueError("at least one historical match is required")
    if shrinkage_matches < 0:
        raise ValueError("shrinkage_matches cannot be negative")
    league_home_goals = sum(match.home_goals for match in matches) / len(matches)
    league_away_goals = sum(match.away_goals for match in matches) / len(matches)
    if league_home_goals <= 0 or league_away_goals <= 0:
        raise ValueError("training data must contain positive home and away goal rates")

    team_ids = {
        team_id for match in matches for team_id in (match.home_team_id, match.away_team_id)
    }
    teams: dict[int, TeamStrength] = {}
    for team_id in team_ids:
        home_rows = [match for match in matches if match.home_team_id == team_id]
        away_rows = [match for match in matches if match.away_team_id == team_id]
        teams[team_id] = TeamStrength(
            home_attack=_shrunk_ratio(
                sum(match.home_goals for match in home_rows),
                len(home_rows),
                league_home_goals,
                shrinkage_matches,
            ),
            home_defence=_shrunk_ratio(
                sum(match.away_goals for match in home_rows),
                len(home_rows),
                league_away_goals,
                shrinkage_matches,
            ),
            away_attack=_shrunk_ratio(
                sum(match.away_goals for match in away_rows),
                len(away_rows),
                league_away_goals,
                shrinkage_matches,
            ),
            away_defence=_shrunk_ratio(
                sum(match.home_goals for match in away_rows),
                len(away_rows),
                league_home_goals,
                shrinkage_matches,
            ),
            home_matches=len(home_rows),
            away_matches=len(away_rows),
        )
    return PoissonTeamStrengthModel(
        league_home_goals=league_home_goals,
        league_away_goals=league_away_goals,
        shrinkage_matches=shrinkage_matches,
        sample_size=len(matches),
        teams=teams,
    )


def model_to_config(model: PoissonTeamStrengthModel) -> dict[str, object]:
    return {
        "league_home_goals": model.league_home_goals,
        "league_away_goals": model.league_away_goals,
        "shrinkage_matches": model.shrinkage_matches,
        "teams": {
            str(team_id): {
                "home_attack": strength.home_attack,
                "home_defence": strength.home_defence,
                "away_attack": strength.away_attack,
                "away_defence": strength.away_defence,
                "home_matches": strength.home_matches,
                "away_matches": strength.away_matches,
            }
            for team_id, strength in sorted(model.teams.items())
        },
    }


def model_from_config(config: dict[str, object], *, sample_size: int) -> PoissonTeamStrengthModel:
    raw_teams = config.get("teams")
    if not isinstance(raw_teams, dict):
        raise ValueError("model configuration has no team parameters")
    teams: dict[int, TeamStrength] = {}
    for raw_team_id, raw_strength in raw_teams.items():
        if not isinstance(raw_team_id, str) or not isinstance(raw_strength, dict):
            raise ValueError("model team parameters are malformed")
        teams[int(raw_team_id)] = TeamStrength(
            home_attack=_number(raw_strength, "home_attack"),
            home_defence=_number(raw_strength, "home_defence"),
            away_attack=_number(raw_strength, "away_attack"),
            away_defence=_number(raw_strength, "away_defence"),
            home_matches=_integer(raw_strength, "home_matches"),
            away_matches=_integer(raw_strength, "away_matches"),
        )
    return PoissonTeamStrengthModel(
        league_home_goals=_number(config, "league_home_goals"),
        league_away_goals=_number(config, "league_away_goals"),
        shrinkage_matches=_number(config, "shrinkage_matches"),
        sample_size=sample_size,
        teams=teams,
    )


def _shrunk_ratio(total: int, matches: int, league_rate: float, prior: float) -> float:
    rate = (total + prior * league_rate) / (matches + prior) if matches + prior else league_rate
    return rate / league_rate


def _bounded_lambda(value: float) -> float:
    return min(4.0, max(0.05, value))


def _number(values: dict[str, object], key: str) -> float:
    value = values.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"model parameter {key} must be numeric")
    return float(value)


def _integer(values: dict[str, object], key: str) -> int:
    value = values.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"model parameter {key} must be an integer")
    return value
