from enum import StrEnum

from app.quant.poisson import selection_wins


class Settlement(StrEnum):
    WIN = "WIN"
    LOSS = "LOSS"
    PUSH = "PUSH"
    VOID = "VOID"


def settle(home_goals: int | None, away_goals: int | None, market_type: str, code: str, line: float | None) -> Settlement:
    if home_goals is None or away_goals is None:
        return Settlement.VOID
    if line is not None and line.is_integer() and market_type in {
        "TOTAL_GOALS", "HOME_TEAM_TOTAL", "AWAY_TEAM_TOTAL"
    }:
        actual = home_goals + away_goals
        if market_type == "HOME_TEAM_TOTAL":
            actual = home_goals
        elif market_type == "AWAY_TEAM_TOTAL":
            actual = away_goals
        if actual == line:
            return Settlement.PUSH
    return Settlement.WIN if selection_wins(home_goals, away_goals, market_type, code, line) else Settlement.LOSS


def profit_units(result: Settlement, decimal_odds: float, stake: float = 1.0) -> float:
    if result == Settlement.WIN:
        return stake * (decimal_odds - 1.0)
    if result == Settlement.LOSS:
        return -stake
    return 0.0

