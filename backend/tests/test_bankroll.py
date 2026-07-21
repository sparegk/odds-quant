from datetime import date

import pytest

from app.quant.bankroll import BankrollBet, simulate_bankroll


def test_flat_bankroll_path_tracks_drawdown_and_daily_exposure() -> None:
    bets = [
        BankrollBet(1, date(2026, 1, 1), 1.0, 2.0, 0.6),
        BankrollBet(2, date(2026, 1, 1), -1.0, 2.0, 0.6),
        BankrollBet(3, date(2026, 1, 2), -1.0, 2.0, 0.6),
    ]

    result = simulate_bankroll(
        bets,
        initial_bankroll=100,
        strategy="flat",
        flat_stake=10,
        stake_fraction=0.01,
        kelly_fraction=0.25,
        maximum_stake_fraction=0.2,
        maximum_daily_exposure_fraction=0.15,
    )

    assert result.bets_placed == 3
    assert result.total_staked == pytest.approx(25)
    assert result.final_bankroll == pytest.approx(95)
    assert result.maximum_drawdown == pytest.approx(15)
    assert result.maximum_drawdown_fraction == pytest.approx(15 / 110)


def test_fractional_kelly_uses_probability_and_caps_stake() -> None:
    bets = [
        BankrollBet(1, date(2026, 1, 1), 2.0, 3.0, 0.5),
        BankrollBet(2, date(2026, 1, 2), -1.0, 3.0, 0.2),
    ]

    result = simulate_bankroll(
        bets,
        initial_bankroll=100,
        strategy="fractional_kelly",
        flat_stake=10,
        stake_fraction=0.01,
        kelly_fraction=0.5,
        maximum_stake_fraction=0.1,
        maximum_daily_exposure_fraction=0.2,
    )

    assert result.points[0].stake == pytest.approx(10)
    assert result.final_bankroll == pytest.approx(120)
    assert result.bets_skipped == 1
