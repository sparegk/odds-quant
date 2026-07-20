from __future__ import annotations

from decimal import Decimal

import pytest

from app.quant.arbitrage import (
    ArbitrageMathError,
    ArbitrageQuote,
    StakeConstraint,
    TaxTerms,
    gross_inverse_sum,
    optimize_rounded_stakes,
)

D = Decimal


def _quote(
    code: str,
    odds: str,
    *,
    tax: TaxTerms | None = None,
    minimum: str = "0",
    maximum: str | None = None,
    increment: str = "0.01",
) -> ArbitrageQuote:
    return ArbitrageQuote(
        selection_code=code,
        decimal_odds=D(odds),
        tax=tax or TaxTerms(),
        constraint=StakeConstraint(
            minimum_stake=D(minimum),
            maximum_stake=D(maximum) if maximum is not None else None,
            stake_increment=D(increment),
        ),
    )


def test_rounding_preserves_positive_worst_case_profit() -> None:
    quotes = [
        _quote("HOME", "2.20"),
        _quote("DRAW", "3.60"),
        _quote("AWAY", "4.20"),
    ]

    allocation = optimize_rounded_stakes(quotes, budget=D("100"))

    assert gross_inverse_sum(quotes) < 1
    assert allocation.total_cash_outlay <= D("100")
    assert allocation.worst_case_net_profit > 0
    assert allocation.minimum_net_payout == min(leg.net_payout for leg in allocation.legs)
    assert all(leg.stake % D("0.01") == 0 for leg in allocation.legs)


def test_explicit_taxes_can_remove_a_gross_arbitrage() -> None:
    heavy_tax = TaxTerms(
        stake_tax_rate=D("0.03"),
        winnings_tax_rate=D("0.15"),
        payout_withholding_rate=D("0.02"),
        commission_rate=D("0.02"),
        fixed_fee=D("0.50"),
    )
    quotes = [
        _quote("OVER", "2.10", tax=heavy_tax),
        _quote("UNDER", "2.10", tax=heavy_tax),
    ]

    allocation = optimize_rounded_stakes(quotes, budget=D("100"))

    assert allocation.inverse_sum < 1
    assert allocation.worst_case_net_profit < 0
    assert allocation.net_roi < 0


def test_stake_limits_and_increments_are_enforced() -> None:
    quotes = [
        _quote("YES", "2.20", minimum="10", maximum="30", increment="1"),
        _quote("NO", "2.20", minimum="10", maximum="100", increment="0.50"),
    ]

    allocation = optimize_rounded_stakes(quotes, budget=D("100"))

    yes, no = allocation.legs
    assert yes.stake <= D("30")
    assert yes.stake % D("1") == 0
    assert no.stake % D("0.50") == 0
    assert allocation.total_cash_outlay <= D("100")


def test_no_gross_arbitrage_and_impossible_constraints_are_rejected() -> None:
    with pytest.raises(ArbitrageMathError, match="gross"):
        optimize_rounded_stakes(
            [_quote("OVER", "1.90"), _quote("UNDER", "1.90")],
            budget=D("100"),
        )
    with pytest.raises(ArbitrageMathError, match="no rounded"):
        optimize_rounded_stakes(
            [
                _quote("OVER", "2.10", minimum="60"),
                _quote("UNDER", "2.10", minimum="60"),
            ],
            budget=D("100"),
        )


@pytest.mark.parametrize(
    "terms",
    [
        {"stake_tax_rate": D("-0.01")},
        {"winnings_tax_rate": D("1.01")},
        {"fixed_fee": D("-1")},
    ],
)
def test_invalid_tax_terms_are_rejected(terms: dict[str, Decimal]) -> None:
    with pytest.raises(ArbitrageMathError):
        TaxTerms(**terms)
