from decimal import Decimal

import pytest

from app.quant.arbitrage import ArbitrageMathError, StakeConstraint, TaxTerms
from app.quant.betting_costs import cost_adjusted_expected_value, valid_reference_stake


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
