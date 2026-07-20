from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from itertools import product

ZERO = Decimal("0")
ONE = Decimal("1")


class ArbitrageMathError(ValueError):
    pass


@dataclass(frozen=True)
class TaxTerms:
    stake_tax_rate: Decimal = ZERO
    winnings_tax_rate: Decimal = ZERO
    payout_withholding_rate: Decimal = ZERO
    commission_rate: Decimal = ZERO
    fixed_fee: Decimal = ZERO

    def __post_init__(self) -> None:
        for name, rate in (
            ("stake_tax_rate", self.stake_tax_rate),
            ("winnings_tax_rate", self.winnings_tax_rate),
            ("payout_withholding_rate", self.payout_withholding_rate),
            ("commission_rate", self.commission_rate),
        ):
            if not ZERO <= rate <= ONE:
                raise ArbitrageMathError(f"{name} must be in [0, 1]")
        if self.fixed_fee < ZERO:
            raise ArbitrageMathError("fixed_fee cannot be negative")


@dataclass(frozen=True)
class StakeConstraint:
    minimum_stake: Decimal = ZERO
    maximum_stake: Decimal | None = None
    stake_increment: Decimal = Decimal("0.01")

    def __post_init__(self) -> None:
        if self.minimum_stake < ZERO:
            raise ArbitrageMathError("minimum_stake cannot be negative")
        if self.maximum_stake is not None and self.maximum_stake <= ZERO:
            raise ArbitrageMathError("maximum_stake must be positive")
        if self.maximum_stake is not None and self.maximum_stake < self.minimum_stake:
            raise ArbitrageMathError("maximum_stake cannot be below minimum_stake")
        if self.stake_increment <= ZERO:
            raise ArbitrageMathError("stake_increment must be positive")


@dataclass(frozen=True)
class ArbitrageQuote:
    selection_code: str
    decimal_odds: Decimal
    tax: TaxTerms
    constraint: StakeConstraint

    def __post_init__(self) -> None:
        if not self.selection_code:
            raise ArbitrageMathError("selection_code is required")
        if self.decimal_odds <= ONE:
            raise ArbitrageMathError("decimal_odds must be greater than one")


@dataclass(frozen=True)
class AllocatedLeg:
    selection_code: str
    decimal_odds: Decimal
    stake: Decimal
    cash_outlay: Decimal
    gross_payout: Decimal
    win_deductions: Decimal
    net_payout: Decimal


@dataclass(frozen=True)
class ArbitrageAllocation:
    inverse_sum: Decimal
    budget: Decimal
    total_cash_outlay: Decimal
    minimum_net_payout: Decimal
    worst_case_net_profit: Decimal
    net_roi: Decimal
    legs: tuple[AllocatedLeg, ...]


def gross_inverse_sum(quotes: list[ArbitrageQuote]) -> Decimal:
    _validate_quotes(quotes)
    return sum((ONE / quote.decimal_odds for quote in quotes), start=ZERO)


def optimize_rounded_stakes(
    quotes: list[ArbitrageQuote],
    *,
    budget: Decimal,
) -> ArbitrageAllocation:
    _validate_quotes(quotes)
    if budget <= ZERO:
        raise ArbitrageMathError("budget must be positive")
    inverse_sum = gross_inverse_sum(quotes)
    if inverse_sum >= ONE:
        raise ArbitrageMathError("quotes do not form a gross theoretical arbitrage")

    payout_multipliers = [_net_payout_multiplier(quote) for quote in quotes]
    outlay_multipliers = [ONE + quote.tax.stake_tax_rate for quote in quotes]
    fixed_fees = sum((quote.tax.fixed_fee for quote in quotes), start=ZERO)
    if fixed_fees >= budget:
        raise ArbitrageMathError("fixed fees consume the available budget")
    target_payout = (budget - fixed_fees) / sum(
        (
            outlay / payout
            for outlay, payout in zip(outlay_multipliers, payout_multipliers, strict=True)
        ),
        start=ZERO,
    )
    for quote, multiplier in zip(quotes, payout_multipliers, strict=True):
        maximum = quote.constraint.maximum_stake
        if maximum is not None:
            target_payout = min(target_payout, maximum * multiplier)

    stake_candidates = [
        _stake_candidates(quote, target_payout / payout_multiplier)
        for quote, payout_multiplier in zip(quotes, payout_multipliers, strict=True)
    ]
    best: tuple[tuple[Decimal, Decimal, Decimal, Decimal], ArbitrageAllocation] | None = None
    for stakes in product(*stake_candidates):
        allocation = _allocation(
            quotes,
            tuple(stakes),
            inverse_sum=inverse_sum,
            budget=budget,
        )
        if allocation.total_cash_outlay > budget:
            continue
        rank = (
            allocation.worst_case_net_profit,
            allocation.net_roi,
            allocation.minimum_net_payout,
            -allocation.total_cash_outlay,
        )
        if best is None or rank > best[0]:
            best = (rank, allocation)
    if best is None:
        raise ArbitrageMathError("no rounded stake allocation satisfies the constraints")
    return best[1]


def _allocation(
    quotes: list[ArbitrageQuote],
    stakes: tuple[Decimal, ...],
    *,
    inverse_sum: Decimal,
    budget: Decimal,
) -> ArbitrageAllocation:
    legs = tuple(_allocated_leg(quote, stake) for quote, stake in zip(quotes, stakes, strict=True))
    total_cash_outlay = sum((leg.cash_outlay for leg in legs), start=ZERO)
    minimum_net_payout = min(leg.net_payout for leg in legs)
    worst_case_net_profit = minimum_net_payout - total_cash_outlay
    net_roi = worst_case_net_profit / total_cash_outlay if total_cash_outlay > ZERO else ZERO
    return ArbitrageAllocation(
        inverse_sum=inverse_sum,
        budget=budget,
        total_cash_outlay=total_cash_outlay,
        minimum_net_payout=minimum_net_payout,
        worst_case_net_profit=worst_case_net_profit,
        net_roi=net_roi,
        legs=legs,
    )


def _allocated_leg(quote: ArbitrageQuote, stake: Decimal) -> AllocatedLeg:
    gross_payout = stake * quote.decimal_odds
    gross_winnings = stake * (quote.decimal_odds - ONE)
    win_deductions = (
        gross_winnings * (quote.tax.winnings_tax_rate + quote.tax.commission_rate)
        + gross_payout * quote.tax.payout_withholding_rate
    )
    cash_outlay = stake + stake * quote.tax.stake_tax_rate + quote.tax.fixed_fee
    return AllocatedLeg(
        selection_code=quote.selection_code,
        decimal_odds=quote.decimal_odds,
        stake=stake,
        cash_outlay=cash_outlay,
        gross_payout=gross_payout,
        win_deductions=win_deductions,
        net_payout=gross_payout - win_deductions,
    )


def _net_payout_multiplier(quote: ArbitrageQuote) -> Decimal:
    multiplier = (
        quote.decimal_odds
        - (quote.decimal_odds - ONE) * (quote.tax.winnings_tax_rate + quote.tax.commission_rate)
        - quote.decimal_odds * quote.tax.payout_withholding_rate
    )
    if multiplier <= ZERO:
        raise ArbitrageMathError(f"taxes eliminate the winning payout for {quote.selection_code}")
    return multiplier


def _stake_candidates(quote: ArbitrageQuote, continuous_stake: Decimal) -> tuple[Decimal, ...]:
    constraint = quote.constraint
    increment = constraint.stake_increment
    floor_units = (continuous_stake / increment).to_integral_value(rounding=ROUND_FLOOR)
    ceil_units = (continuous_stake / increment).to_integral_value(rounding=ROUND_CEILING)
    units = {
        floor_units + offset for offset in (Decimal("-2"), Decimal("-1"), ZERO, ONE, Decimal("2"))
    }
    units.update(
        {ceil_units + offset for offset in (Decimal("-2"), Decimal("-1"), ZERO, ONE, Decimal("2"))}
    )
    minimum_units = (constraint.minimum_stake / increment).to_integral_value(rounding=ROUND_CEILING)
    units.add(minimum_units)
    if constraint.maximum_stake is not None:
        maximum_units = (constraint.maximum_stake / increment).to_integral_value(
            rounding=ROUND_FLOOR
        )
        units.add(maximum_units)
    values: set[Decimal] = set()
    for unit in units:
        stake = unit * increment
        if stake < constraint.minimum_stake or stake <= ZERO:
            continue
        if constraint.maximum_stake is not None and stake > constraint.maximum_stake:
            continue
        values.add(stake)
    if not values:
        raise ArbitrageMathError(f"no valid rounded stake exists for {quote.selection_code}")
    return tuple(sorted(values))


def _validate_quotes(quotes: list[ArbitrageQuote]) -> None:
    if len(quotes) not in {2, 3}:
        raise ArbitrageMathError("arbitrage requires exactly two or three outcomes")
    codes = [quote.selection_code for quote in quotes]
    if len(set(codes)) != len(codes):
        raise ArbitrageMathError("arbitrage outcome codes must be unique")
