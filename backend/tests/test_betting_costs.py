from decimal import Decimal

import pytest

from app.quant.arbitrage import ArbitrageMathError, StakeConstraint, TaxTerms
from app.quant.betting_costs import (
    cost_adjusted_expected_value,
    minimum_decimal_odds_for_positive_net_ev,
    valid_reference_stake,
)


def test_cost_adjusted_ev_applies_every_supported_deduction() -> None:
    constraint = StakeConstraint(
        minimum_stake=Decimal("1"),
        maximum_stake=Decimal("50"),
        stake_increment=Decimal("0.25"),
    )
    stake = valid_reference_stake(constraint)
    result = cost_adjusted_expected_value(
        probability=Decimal("0.58"),
        decimal_odds=Decimal("2.05"),
        stake=stake,
        tax=TaxTerms(
            stake_tax_rate=Decimal("0.02"),
            winnings_tax_rate=Decimal("0.10"),
            payout_withholding_rate=Decimal("0.01"),
            commission_rate=Decimal("0.02"),
            fixed_fee=Decimal("1"),
        ),
        constraint=constraint,
    )

    assert result.stake == Decimal("50.00")
    assert result.cash_outlay == Decimal("52.0000")
    assert result.net_payout_on_win == Decimal("95.1750")
    assert result.expected_net_profit == Decimal("3.201500")
    assert result.expected_net_roi == Decimal("3.201500") / Decimal("52")


def test_reference_stake_fails_when_rounding_cannot_reach_minimum() -> None:
    constraint = StakeConstraint(
        minimum_stake=Decimal("10.01"),
        maximum_stake=Decimal("10.02"),
        stake_increment=Decimal("1"),
    )

    with pytest.raises(ArbitrageMathError, match="no positive rounded reference stake"):
        valid_reference_stake(constraint)


def test_minimum_odds_threshold_matches_cost_adjusted_break_even() -> None:
    tax = TaxTerms(
        stake_tax_rate=Decimal("0.02"),
        winnings_tax_rate=Decimal("0.10"),
        payout_withholding_rate=Decimal("0.01"),
        commission_rate=Decimal("0.02"),
        fixed_fee=Decimal("1"),
    )
    threshold = minimum_decimal_odds_for_positive_net_ev(
        probability=Decimal("0.52"), stake=Decimal("50"), tax=tax
    )
    constraint = StakeConstraint(
        minimum_stake=Decimal("1"),
        maximum_stake=Decimal("50"),
        stake_increment=Decimal("0.25"),
    )
    at_threshold = cost_adjusted_expected_value(
        probability=Decimal("0.52"),
        decimal_odds=threshold,
        stake=Decimal("50"),
        tax=tax,
        constraint=constraint,
    )

    assert at_threshold.expected_net_profit == pytest.approx(Decimal("0"), abs=Decimal("1e-24"))
    assert threshold > Decimal("1") / Decimal("0.52")
