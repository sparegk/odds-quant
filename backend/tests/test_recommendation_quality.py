import math

import pytest

from app.quant.recommendation_quality import recommendation_quality


def test_decomposes_recommendation_quality_and_uses_geometric_mean() -> None:
    quality = recommendation_quality(
        model_probability=0.68,
        lower_probability=0.62,
        calibration_error=0.03,
        price_age_minutes=2,
        maximum_price_age_minutes=5,
        bookmaker_disagreement=0.02,
        lower_net_expected_value=0.08,
    )
    components = (0.62 / 0.68, 0.8, 0.6, 0.8, 0.8)
    assert quality.probability_interval_retention == pytest.approx(components[0])
    assert quality.calibration_quality == pytest.approx(components[1])
    assert quality.price_freshness_quality == pytest.approx(components[2])
    assert quality.market_agreement_quality == pytest.approx(components[3])
    assert quality.net_economics_quality == pytest.approx(components[4])
    assert quality.bookmaker_disagreement == pytest.approx(0.02)
    assert quality.overall_quality_score == pytest.approx(
        math.prod(components) ** (1 / len(components))
    )


def test_zero_component_cannot_be_hidden_by_strong_components() -> None:
    quality = recommendation_quality(
        model_probability=0.7,
        lower_probability=0.7,
        calibration_error=0,
        price_age_minutes=5,
        maximum_price_age_minutes=5,
        bookmaker_disagreement=0,
        lower_net_expected_value=0.2,
    )
    assert quality.price_freshness_quality == 0
    assert quality.overall_quality_score == 0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("model_probability", 0.0),
        ("lower_probability", 0.8),
        ("calibration_error", -0.01),
        ("price_age_minutes", -1),
        ("maximum_price_age_minutes", 0),
        ("bookmaker_disagreement", -0.01),
        ("lower_net_expected_value", 0),
        ("lower_net_expected_value", math.inf),
    ],
)
def test_rejects_invalid_quality_inputs(field: str, value: float) -> None:
    inputs = {
        "model_probability": 0.6,
        "lower_probability": 0.55,
        "calibration_error": 0.03,
        "price_age_minutes": 1.0,
        "maximum_price_age_minutes": 5.0,
        "bookmaker_disagreement": 0.02,
        "lower_net_expected_value": 0.05,
    }
    inputs[field] = value
    with pytest.raises(ValueError):
        recommendation_quality(**inputs)
