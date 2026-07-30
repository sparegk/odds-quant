import pytest

from app.quant.model_market import compare_model_to_market


def test_model_market_consensus_weights_each_bookmaker_once() -> None:
    result = compare_model_to_market(
        model_probability=0.58,
        lower_probability=0.52,
        upper_probability=0.64,
        market_estimates=[(0.50, 0.48), (0.54, 0.52)],
        best_odds=2.0,
    )

    assert result.market_consensus_probability == pytest.approx(0.51)
    assert result.market_probability_low == pytest.approx(0.48)
    assert result.market_probability_high == pytest.approx(0.54)
    assert result.devig_method_spread == pytest.approx(0.02)
    assert result.bookmaker_disagreement == pytest.approx(0.04)
    assert result.probability_edge == pytest.approx(0.07)
    assert result.conservative_edge == pytest.approx(-0.02)
    assert result.expected_value == pytest.approx(0.16)
    assert result.lower_expected_value == pytest.approx(0.04)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"market_estimates": []}, "At least one bookmaker"),
        ({"model_probability": 0.7, "upper_probability": 0.6}, "uncertainty interval"),
        ({"market_estimates": [(float("nan"), 0.5)]}, "finite probability"),
        ({"best_odds": 1.0}, "Decimal odds"),
    ],
)
def test_model_market_rejects_incomplete_or_invalid_inputs(
    kwargs: dict[str, object], message: str
) -> None:
    inputs: dict[str, object] = {
        "model_probability": 0.55,
        "lower_probability": 0.5,
        "upper_probability": 0.6,
        "market_estimates": [(0.51, 0.49)],
        "best_odds": 2.1,
    }
    inputs.update(kwargs)

    with pytest.raises(ValueError, match=message):
        compare_model_to_market(**inputs)  # type: ignore[arg-type]
