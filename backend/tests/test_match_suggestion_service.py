from datetime import UTC, datetime

import pytest

from app.schemas.signals import ValueSignalView
from app.services.match_suggestions import build_match_suggestions


def test_builds_ranked_api_view_from_qualified_signal() -> None:
    generated_at = datetime(2026, 7, 24, 12, tzinfo=UTC)
    signal = ValueSignalView(
        id=7,
        event_id=3,
        output_id=4,
        model_version_id=5,
        model_version="poisson-production-v1",
        evaluation_run_id=6,
        prediction_id=8,
        market_id=9,
        market_type="DOUBLE_CHANCE",
        line=None,
        selection_id=10,
        selection_code="HOME_OR_DRAW",
        selection_name="Home or draw",
        bookmaker_id=11,
        bookmaker="Novibet",
        odds_snapshot_id=12,
        signal_type="VALUE",
        offered_odds=1.8,
        raw_implied_probability=0.5556,
        market_fair_probability=0.56,
        model_probability=0.68,
        lower_probability=0.62,
        expected_value=0.224,
        lower_expected_value=0.116,
        probability_edge=0.12,
        confidence=0.8,
        calibration_error=0.03,
        odds_age_minutes=2,
        bookmaker_count=2,
        odds_move_ratio=0,
        implied_move_points=0,
        generated_at=generated_at,
        reasons=["Calibrated lower bound clears the market price."],
        risks=["Prices can move before placement."],
    )

    views, ranked = build_match_suggestions(
        signals=[signal],
        builder_quotes=[],
        selected_bookmakers={"novibet"},
        cutoff=generated_at,
        max_price_age_minutes=5,
        event_is_demo=False,
    )

    assert len(ranked) == 1
    assert len(views) == 1
    suggestion = views[0]
    assert suggestion.rank == 1
    assert suggestion.bookmaker_code == "novibet"
    assert suggestion.selection_code == "HOME_OR_DRAW"
    assert suggestion.offered_odds == 1.8
    assert suggestion.lower_probability == 0.62
    assert suggestion.lower_expected_value == 0.116
    assert suggestion.conservative_score == pytest.approx(0.0928)
    assert suggestion.price_observed_at < suggestion.generated_at


def test_api_view_builder_respects_bookmaker_filter() -> None:
    generated_at = datetime(2026, 7, 24, 12, tzinfo=UTC)
    signal = ValueSignalView(
        id=7,
        event_id=3,
        output_id=4,
        model_version_id=5,
        model_version="poisson-production-v1",
        evaluation_run_id=6,
        prediction_id=8,
        market_id=9,
        market_type="MATCH_RESULT",
        line=None,
        selection_id=10,
        selection_code="HOME",
        selection_name="Home",
        bookmaker_id=11,
        bookmaker="Novibet",
        odds_snapshot_id=12,
        signal_type="VALUE",
        offered_odds=2.0,
        raw_implied_probability=0.5,
        market_fair_probability=0.48,
        model_probability=0.6,
        lower_probability=0.55,
        expected_value=0.2,
        lower_expected_value=0.1,
        probability_edge=0.12,
        confidence=0.7,
        calibration_error=0.03,
        odds_age_minutes=1,
        bookmaker_count=2,
        odds_move_ratio=0,
        implied_move_points=0,
        generated_at=generated_at,
        reasons=[],
        risks=[],
    )

    views, ranked = build_match_suggestions(
        signals=[signal],
        builder_quotes=[],
        selected_bookmakers={"allwyn"},
        cutoff=generated_at,
        max_price_age_minutes=5,
        event_is_demo=False,
    )

    assert views == []
    assert ranked == []
