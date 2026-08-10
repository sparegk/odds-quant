from __future__ import annotations

COLD_START_VENUE_HISTORY_TARGET = 8


def widen_match_result_probabilities(
    probabilities: dict[str, float],
    *,
    home_venue_matches: int,
    away_venue_matches: int,
) -> tuple[dict[str, float], float]:
    if not probabilities:
        raise ValueError("cold-start probabilities cannot be empty")
    if home_venue_matches < 0 or away_venue_matches < 0:
        raise ValueError("cold-start venue histories cannot be negative")
    home_evidence = min(home_venue_matches, COLD_START_VENUE_HISTORY_TARGET)
    away_evidence = min(away_venue_matches, COLD_START_VENUE_HISTORY_TARGET)
    reliability_weight = (home_evidence + away_evidence) / (2 * COLD_START_VENUE_HISTORY_TARGET)
    uniform_weight = 1.0 - reliability_weight
    widened = {
        outcome: reliability_weight * probability + uniform_weight / len(probabilities)
        for outcome, probability in probabilities.items()
    }
    return widened, reliability_weight


def cold_start_uncertainty_class(
    *,
    home_venue_matches: int,
    away_venue_matches: int,
    home_used_league_prior: bool,
    away_used_league_prior: bool,
) -> str:
    if home_used_league_prior or away_used_league_prior:
        return "league_prior"
    if (
        home_venue_matches < COLD_START_VENUE_HISTORY_TARGET
        or away_venue_matches < COLD_START_VENUE_HISTORY_TARGET
    ):
        return "sparse_venue_history"
    return "standard_history"
