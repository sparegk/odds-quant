from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass

from app.quant.odds import (
    expected_value,
    fair_odds,
    implied_probability,
    probability_edge,
    validate_decimal_odds,
)


@dataclass(frozen=True)
class ModelMarketMetrics:
    market_consensus_probability: float
    market_probability_low: float
    market_probability_high: float
    devig_method_spread: float
    bookmaker_disagreement: float
    best_price_break_even_probability: float
    probability_edge: float
    conservative_edge: float
    price_probability_edge: float
    conservative_price_edge: float
    expected_value: float
    lower_expected_value: float
    lower_fair_odds: float | None
    model_uncertainty_width: float
    market_uncertainty_width: float
    pre_cost_advantage_survives_uncertainty: bool


def compare_model_to_market(
    *,
    model_probability: float,
    lower_probability: float,
    upper_probability: float,
    market_estimates: Iterable[tuple[float, float]],
    best_odds: float,
) -> ModelMarketMetrics:
    """Compare a model interval with complete, already de-vigged bookmaker prices.

    Each tuple contains the proportional and power de-vig estimates for one
    bookmaker. The consensus gives every bookmaker one vote by averaging its two
    estimates first. It is descriptive arithmetic, not a signal qualification.
    """

    _validate_probability("lower_probability", lower_probability)
    _validate_probability("model_probability", model_probability)
    _validate_probability("upper_probability", upper_probability)
    if not lower_probability <= model_probability <= upper_probability:
        raise ValueError("Model probability must be inside its uncertainty interval")
    validate_decimal_odds(best_odds)

    estimates = list(market_estimates)
    if not estimates:
        raise ValueError("At least one bookmaker market estimate is required")

    bookmaker_midpoints: list[float] = []
    all_estimates: list[float] = []
    method_spreads: list[float] = []
    for proportional, power in estimates:
        _validate_probability("proportional market probability", proportional)
        _validate_probability("power market probability", power)
        bookmaker_midpoints.append((proportional + power) / 2.0)
        all_estimates.extend((proportional, power))
        method_spreads.append(abs(proportional - power))

    consensus = sum(bookmaker_midpoints) / len(bookmaker_midpoints)
    market_low = min(all_estimates)
    market_high = max(all_estimates)
    break_even = implied_probability(best_odds)
    lower_expected_value = expected_value(lower_probability, best_odds)
    conservative_edge = probability_edge(lower_probability, market_high)
    return ModelMarketMetrics(
        market_consensus_probability=consensus,
        market_probability_low=market_low,
        market_probability_high=market_high,
        devig_method_spread=max(method_spreads),
        bookmaker_disagreement=max(bookmaker_midpoints) - min(bookmaker_midpoints),
        best_price_break_even_probability=break_even,
        probability_edge=probability_edge(model_probability, consensus),
        conservative_edge=conservative_edge,
        price_probability_edge=probability_edge(model_probability, break_even),
        conservative_price_edge=probability_edge(lower_probability, break_even),
        expected_value=expected_value(model_probability, best_odds),
        lower_expected_value=lower_expected_value,
        lower_fair_odds=fair_odds(lower_probability) if lower_probability > 0 else None,
        model_uncertainty_width=upper_probability - lower_probability,
        market_uncertainty_width=market_high - market_low,
        pre_cost_advantage_survives_uncertainty=(
            conservative_edge > 0 and lower_expected_value > 0
        ),
    )


def _validate_probability(label: str, value: float) -> None:
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError(f"{label} must be a finite probability in [0, 1]")
