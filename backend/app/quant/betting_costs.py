from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

from app.quant.arbitrage import ArbitrageMathError, StakeConstraint, TaxTerms

ZERO = Decimal("0")
ONE = Decimal("1")
DEFAULT_REFERENCE_STAKE = Decimal("100")


@dataclass(frozen=True)
class CostAdjustedExpectedValue:
    stake: Decimal
    cash_outlay: Decimal
    net_payout_on_win: Decimal
    expected_net_profit: Decimal
    expected_net_roi: Decimal


def valid_reference_stake(
    constraint: StakeConstraint, *, target: Decimal = DEFAULT_REFERENCE_STAKE
) -> Decimal:
    if target <= ZERO:
        raise ArbitrageMathError("reference stake target must be positive")
    increment = constraint.stake_increment
    required = max(target, constraint.minimum_stake, increment)
    stake = (required / increment).to_integral_value(rounding=ROUND_CEILING) * increment
    maximum = constraint.maximum_stake
    if maximum is not None and stake > maximum:
        stake = (maximum / increment).to_integral_value(rounding=ROUND_FLOOR) * increment
    if stake <= ZERO or stake < constraint.minimum_stake:
        raise ArbitrageMathError("no positive rounded reference stake satisfies the constraints")
    return stake


def cost_adjusted_expected_value(
    *,
    probability: Decimal,
    decimal_odds: Decimal,
    stake: Decimal,
    tax: TaxTerms,
    constraint: StakeConstraint,
) -> CostAdjustedExpectedValue:
    if not ZERO <= probability <= ONE:
        raise ArbitrageMathError("probability must be in [0, 1]")
    if decimal_odds <= ONE:
        raise ArbitrageMathError("decimal_odds must be greater than one")
    if stake <= ZERO or stake < constraint.minimum_stake:
        raise ArbitrageMathError("stake is below the positive minimum stake")
    if constraint.maximum_stake is not None and stake > constraint.maximum_stake:
        raise ArbitrageMathError("stake exceeds the maximum stake")
    units = stake / constraint.stake_increment
    if units != units.to_integral_value():
        raise ArbitrageMathError("stake does not respect the stake increment")
    gross_payout = stake * decimal_odds
    gross_winnings = stake * (decimal_odds - ONE)
    deductions = (
        gross_winnings * (tax.winnings_tax_rate + tax.commission_rate)
        + gross_payout * tax.payout_withholding_rate
    )
    net_payout = gross_payout - deductions
    cash_outlay = stake * (ONE + tax.stake_tax_rate) + tax.fixed_fee
    expected_profit = probability * net_payout - cash_outlay
    return CostAdjustedExpectedValue(
        stake=stake,
        cash_outlay=cash_outlay,
        net_payout_on_win=net_payout,
        expected_net_profit=expected_profit,
        expected_net_roi=expected_profit / cash_outlay,
    )


def minimum_decimal_odds_for_positive_net_ev(
    *, probability: Decimal, stake: Decimal, tax: TaxTerms
) -> Decimal:
    """Return the strict break-even odds threshold after all configured costs."""
    if not ZERO < probability <= ONE:
        raise ArbitrageMathError("probability must be in (0, 1]")
    if stake <= ZERO:
        raise ArbitrageMathError("stake must be positive")
    winnings_rate = tax.winnings_tax_rate + tax.commission_rate
    odds_multiplier = ONE - winnings_rate - tax.payout_withholding_rate
    if odds_multiplier <= ZERO:
        raise ArbitrageMathError("configured deductions eliminate odds-linked payout")
    cash_outlay = stake * (ONE + tax.stake_tax_rate) + tax.fixed_fee
    return (cash_outlay / (probability * stake) - winnings_rate) / odds_multiplier
