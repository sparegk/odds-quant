from collections.abc import Iterable

from scipy.optimize import brentq


def validate_decimal_odds(decimal_odds: float) -> float:
    if not 1.0 < decimal_odds < 1001.0:
        raise ValueError("Decimal odds must be greater than 1 and below 1001")
    return decimal_odds


def implied_probability(decimal_odds: float) -> float:
    return 1.0 / validate_decimal_odds(decimal_odds)


def overround(decimal_odds: Iterable[float]) -> float:
    values = list(decimal_odds)
    if len(values) < 2:
        raise ValueError("A complete market needs at least two outcomes")
    return sum(implied_probability(value) for value in values)


def bookmaker_margin(decimal_odds: Iterable[float]) -> float:
    return overround(decimal_odds) - 1.0


def devig_proportional(decimal_odds: Iterable[float]) -> list[float]:
    raw = [implied_probability(value) for value in decimal_odds]
    total = sum(raw)
    return [value / total for value in raw]


def devig_power(decimal_odds: Iterable[float]) -> list[float]:
    raw = [implied_probability(value) for value in decimal_odds]
    if len(raw) < 2:
        raise ValueError("A complete market needs at least two outcomes")
    if abs(sum(raw) - 1.0) < 1e-12:
        return raw

    def objective(power: float) -> float:
        return sum(value**power for value in raw) - 1.0

    exponent = brentq(objective, 0.01, 100.0)
    probabilities = [value**exponent for value in raw]
    total = sum(probabilities)
    return [value / total for value in probabilities]


def fair_odds(probability: float) -> float:
    if not 0.0 < probability <= 1.0:
        raise ValueError("Probability must be in (0, 1]")
    return 1.0 / probability


def expected_value(probability: float, decimal_odds: float) -> float:
    if not 0.0 <= probability <= 1.0:
        raise ValueError("Probability must be in [0, 1]")
    return probability * validate_decimal_odds(decimal_odds) - 1.0


def probability_edge(model_probability: float, market_probability: float) -> float:
    if not 0 <= model_probability <= 1 or not 0 <= market_probability <= 1:
        raise ValueError("Probabilities must be in [0, 1]")
    return model_probability - market_probability


def closing_line_value(taken_odds: float, closing_odds: float) -> float:
    return validate_decimal_odds(taken_odds) / validate_decimal_odds(closing_odds) - 1.0

