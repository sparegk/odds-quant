from datetime import UTC, datetime, timedelta

import pytest

from app.quant.match_suggestions import SuggestionCandidate, rank_match_suggestions
from app.schemas.api import MarketComparison, PriceComparison, SnapshotComparison
from app.schemas.models import ModelOutputView, SelectionPredictionView
from app.services.match_suggestions import build_model_market_comparisons

NOW = datetime(2026, 7, 24, 12, tzinfo=UTC)


def market_price(
    *, bookmaker: str, probability: float, odds: float, stale: bool = False
) -> SnapshotComparison:
    return SnapshotComparison(
        snapshot_id=1 if bookmaker == "Novibet" else 2,
        bookmaker_id=1 if bookmaker == "Novibet" else 2,
        bookmaker=bookmaker,
        provider="licensed-feed",
        observed_at=NOW - timedelta(minutes=2),
        source_updated_at=NOW - timedelta(minutes=2),
        is_closing=False,
        is_demo=False,
        source_label="licensed",
        freshness_seconds=120,
        is_stale=stale,
        overround=1.05,
        bookmaker_margin=0.05,
        prices=[
            PriceComparison(
                selection_code="HOME",
                selection_name="Home",
                decimal_odds=odds,
                raw_implied_probability=1 / odds,
                proportional_fair_probability=probability,
                proportional_fair_odds=1 / probability,
                power_fair_probability=probability - 0.02,
                power_fair_odds=1 / (probability - 0.02),
            )
        ],
    )


def prediction_output() -> ModelOutputView:
    return ModelOutputView(
        id=1,
        event_id=1,
        model_version_id=1,
        model_version="poisson-v1",
        predicted_at=NOW - timedelta(minutes=10),
        inputs_as_of=NOW - timedelta(minutes=10),
        evidence_class="team_baseline",
        lineup_snapshot_ids=[],
        home_lambda=1.5,
        away_lambda=1.0,
        sample_size=100,
        probability_uncertainty={
            "method": "wilson_training_sample_proxy",
            "version": "legacy-v1",
            "confidence_level": 0.95,
            "requested_refits": 0,
            "successful_refits": 0,
            "attempted_refits": 0,
            "block_length": None,
            "seed_fingerprint": None,
            "training_fingerprint": "fixture-training-fingerprint",
        },
        probability_calibration={
            "method": "none",
            "version": "raw-probability-v1",
            "applied": False,
            "temperature": None,
            "sample_size": 0,
            "input_fingerprint": None,
            "fit_through": None,
            "evaluation_run_id": None,
        },
        score_matrix=[[1.0]],
        derived_probabilities={},
        predictions=[
            SelectionPredictionView(
                id=1,
                market_id=7,
                market_type="MATCH_RESULT",
                line=None,
                selection_id=11,
                selection_code="HOME",
                selection_name="Home",
                probability=0.58,
                lower_probability=0.52,
                upper_probability=0.64,
                fair_odds=1 / 0.58,
            )
        ],
    )


def comparison_market(*snapshots: SnapshotComparison) -> MarketComparison:
    return MarketComparison(
        market_id=7,
        market_type="MATCH_RESULT",
        line=None,
        period="FULL_TIME",
        currency="EUR",
        settlement_rule_key="football.match-result.v1",
        snapshots=list(snapshots),
        best_prices=[],
    )


def candidate(**overrides: object) -> SuggestionCandidate:
    values: dict[str, object] = {
        "source_id": 1,
        "kind": "single",
        "bookmaker": "Novibet",
        "market_type": "DOUBLE_CHANCE",
        "offered_odds": 1.8,
        "lower_probability": 0.62,
        "lower_expected_value": 0.116,
        "confidence": 0.8,
        "price_observed_at": NOW - timedelta(minutes=2),
        "generated_at": NOW,
        "cutoff": NOW,
    }
    values.update(overrides)
    return SuggestionCandidate(**values)  # type: ignore[arg-type]


def test_filters_by_selected_supported_bookmaker() -> None:
    allwyn = candidate(source_id=2, bookmaker="Allwyn / Pamestoixima")
    unrelated = candidate(source_id=3, bookmaker="Other book")

    ranked = rank_match_suggestions(
        [candidate(), allwyn, unrelated],
        selected_bookmakers={"allwyn"},
        max_price_age_minutes=5,
    )

    assert [item.candidate.source_id for item in ranked] == [2]
    assert ranked[0].bookmaker_code == "allwyn"


@pytest.mark.parametrize(
    ("change", "value"),
    [
        ("qualified", False),
        ("is_demo", True),
        ("market_type", "TOTAL_CORNERS"),
        ("offered_odds", None),
        ("lower_expected_value", 0.0),
        ("confidence", 0.0),
        ("lower_probability", 0.49),
        ("price_observed_at", None),
        ("price_observed_at", NOW - timedelta(minutes=6)),
        ("generated_at", NOW + timedelta(seconds=1)),
    ],
)
def test_fails_closed_when_evidence_is_not_executable(change: str, value: object) -> None:
    ranked = rank_match_suggestions(
        [candidate(**{change: value})],
        selected_bookmakers={"novibet"},
        max_price_age_minutes=5,
    )

    assert ranked == []


def test_allows_builder_with_lower_joint_probability_and_exact_quote() -> None:
    builder = candidate(
        kind="builder",
        market_type="BET_BUILDER",
        lower_probability=0.3,
        offered_odds=4.0,
        lower_expected_value=0.2,
    )

    ranked = rank_match_suggestions(
        [builder],
        selected_bookmakers={"novibet"},
        max_price_age_minutes=5,
    )

    assert [item.candidate.source_id for item in ranked] == [1]


def test_ranks_by_confidence_weighted_conservative_value() -> None:
    lower_raw_value = candidate(source_id=2, lower_expected_value=0.1, confidence=0.9)
    higher_raw_but_less_reliable = candidate(
        source_id=1,
        lower_expected_value=0.12,
        confidence=0.5,
    )

    ranked = rank_match_suggestions(
        [higher_raw_but_less_reliable, lower_raw_value],
        selected_bookmakers={"novibet"},
        max_price_age_minutes=5,
    )

    assert [item.candidate.source_id for item in ranked] == [2, 1]
    assert ranked[0].conservative_score == pytest.approx(0.09)


def test_empty_bookmaker_selection_returns_no_suggestions() -> None:
    assert (
        rank_match_suggestions(
            [candidate()],
            selected_bookmakers=set(),
            max_price_age_minutes=5,
        )
        == []
    )


def test_price_must_still_be_fresh_at_matchday_cutoff() -> None:
    ranked = rank_match_suggestions(
        [
            candidate(
                price_observed_at=NOW - timedelta(minutes=11),
                generated_at=NOW - timedelta(minutes=10),
            )
        ],
        selected_bookmakers={"novibet"},
        max_price_age_minutes=5,
    )

    assert ranked == []


def test_model_market_comparison_uses_only_fresh_selected_bookmakers() -> None:
    comparisons = build_model_market_comparisons(
        latest_prediction=prediction_output(),
        markets=[
            comparison_market(
                market_price(bookmaker="Novibet", probability=0.52, odds=2.05),
                market_price(bookmaker="Allwyn", probability=0.48, odds=2.1),
                market_price(bookmaker="Other", probability=0.8, odds=3.0),
            )
        ],
        selected_bookmakers={"novibet"},
    )

    assert len(comparisons) == 1
    comparison = comparisons[0]
    assert comparison.bookmaker_count == 1
    assert comparison.best_bookmaker == "Novibet"
    assert comparison.market_consensus_probability == pytest.approx(0.51)
    assert comparison.probability_edge == pytest.approx(0.07)
    assert comparison.conservative_edge == pytest.approx(0.0)
    assert comparison.research_only is True
    assert "no calibrated VALUE signal" in comparison.qualification_blockers[0]


def test_model_market_comparison_fails_closed_without_fresh_exact_price() -> None:
    comparisons = build_model_market_comparisons(
        latest_prediction=prediction_output(),
        markets=[
            comparison_market(
                market_price(bookmaker="Novibet", probability=0.52, odds=2.05, stale=True)
            )
        ],
        selected_bookmakers={"novibet"},
    )

    assert comparisons == []
