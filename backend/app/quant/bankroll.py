from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class BankrollBet:
    observation_id: int
    day: date
    profit_per_unit: float
    decimal_odds: float
    probability: float


@dataclass(frozen=True)
class BankrollPoint:
    observation_id: int
    bankroll: float
    stake: float
    profit: float
    drawdown: float


@dataclass(frozen=True)
class BankrollSimulation:
    points: list[BankrollPoint]
    final_bankroll: float
    total_staked: float
    net_profit: float
    roi: float
    maximum_drawdown: float
    maximum_drawdown_fraction: float
    bets_placed: int
    bets_skipped: int


def simulate_bankroll(
    bets: list[BankrollBet],
    *,
    initial_bankroll: float,
    strategy: str,
    flat_stake: float,
    stake_fraction: float,
    kelly_fraction: float,
    maximum_stake_fraction: float,
    maximum_daily_exposure_fraction: float,
) -> BankrollSimulation:
    if initial_bankroll <= 0:
        raise ValueError("initial bankroll must be positive")
    if strategy not in {"flat", "percentage", "fractional_kelly"}:
        raise ValueError("unsupported bankroll strategy")
    if flat_stake <= 0 or not 0 < stake_fraction <= 1:
        raise ValueError("staking inputs must be positive")
    if not 0 < kelly_fraction <= 1 or not 0 < maximum_stake_fraction <= 1:
        raise ValueError("Kelly inputs must be between zero and one")
    if not 0 < maximum_daily_exposure_fraction <= 1:
        raise ValueError("daily exposure fraction must be between zero and one")

    bankroll = initial_bankroll
    peak = bankroll
    maximum_drawdown = 0.0
    maximum_drawdown_fraction = 0.0
    total_staked = 0.0
    points: list[BankrollPoint] = []
    daily_exposure: dict[date, float] = {}
    skipped = 0

    for bet in bets:
        if bankroll <= 0:
            skipped += 1
            continue
        if strategy == "flat":
            desired = flat_stake
        elif strategy == "percentage":
            desired = bankroll * stake_fraction
        else:
            if bet.decimal_odds <= 1 or not 0 <= bet.probability <= 1:
                raise ValueError("Kelly inputs require valid odds and probability")
            full_kelly = max(
                0.0,
                (bet.probability * bet.decimal_odds - 1) / (bet.decimal_odds - 1),
            )
            desired = bankroll * min(
                maximum_stake_fraction,
                full_kelly * kelly_fraction,
            )
        daily_limit = initial_bankroll * maximum_daily_exposure_fraction
        remaining_daily = max(0.0, daily_limit - daily_exposure.get(bet.day, 0.0))
        stake = min(desired, bankroll * maximum_stake_fraction, remaining_daily, bankroll)
        if stake <= 1e-12:
            skipped += 1
            continue
        profit = stake * bet.profit_per_unit
        bankroll += profit
        total_staked += stake
        daily_exposure[bet.day] = daily_exposure.get(bet.day, 0.0) + stake
        peak = max(peak, bankroll)
        drawdown = peak - bankroll
        maximum_drawdown = max(maximum_drawdown, drawdown)
        drawdown_fraction = drawdown / peak if peak else 0.0
        maximum_drawdown_fraction = max(maximum_drawdown_fraction, drawdown_fraction)
        points.append(
            BankrollPoint(
                observation_id=bet.observation_id,
                bankroll=bankroll,
                stake=stake,
                profit=profit,
                drawdown=drawdown,
            )
        )

    net_profit = bankroll - initial_bankroll
    return BankrollSimulation(
        points=points,
        final_bankroll=bankroll,
        total_staked=total_staked,
        net_profit=net_profit,
        roi=net_profit / total_staked if total_staked else 0.0,
        maximum_drawdown=maximum_drawdown,
        maximum_drawdown_fraction=maximum_drawdown_fraction,
        bets_placed=len(points),
        bets_skipped=skipped,
    )
