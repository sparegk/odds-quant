from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class RecommendationQuality:
    probability_interval_retention: float
    calibration_quality: float
    price_freshness_quality: float
    market_agreement_quality: float
    net_economics_quality: float
    bookmaker_disagreement: float
    overall_quality_score: float


def recommendation_quality(
    *,
    model_probability: float,
    lower_probability: float,
    calibration_error: float,
    price_age_minutes: float,
    maximum_price_age_minutes: float,
    bookmaker_disagreement: float,
    lower_net_expected_value: float,
) -> RecommendationQuality:
    values = {
        "model_probability": model_probability,
        "lower_probability": lower_probability,
        "calibration_error": calibration_error,
        "price_age_minutes": price_age_minutes,
        "maximum_price_age_minutes": maximum_price_age_minutes,
        "bookmaker_disagreement": bookmaker_disagreement,
        "lower_net_expected_value": lower_net_expected_value,
    }
    if any(not math.isfinite(value) for value in values.values()):
        raise ValueError("recommendation quality inputs must be finite")
    if not 0 < model_probability <= 1 or not 0 <= lower_probability <= model_probability:
        raise ValueError("probability interval is invalid")
    if calibration_error < 0 or price_age_minutes < 0 or maximum_price_age_minutes <= 0:
        raise ValueError("reliability inputs are invalid")
    if bookmaker_disagreement < 0 or lower_net_expected_value <= 0:
        raise ValueError("market disagreement and lower net EV are invalid")

    components = (
        lower_probability / model_probability,
        max(0.0, 1.0 - calibration_error / 0.15),
        max(0.0, 1.0 - price_age_minutes / maximum_price_age_minutes),
        max(0.0, 1.0 - bookmaker_disagreement / 0.10),
        min(lower_net_expected_value / 0.10, 1.0),
    )
    overall = math.prod(components) ** (1.0 / len(components))
    return RecommendationQuality(
        probability_interval_retention=components[0],
        calibration_quality=components[1],
        price_freshness_quality=components[2],
        market_agreement_quality=components[3],
        net_economics_quality=components[4],
        bookmaker_disagreement=bookmaker_disagreement,
        overall_quality_score=overall,
    )
