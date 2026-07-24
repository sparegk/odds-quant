from datetime import UTC, datetime, timedelta

import pytest

from app.quant.match_suggestions import SuggestionCandidate, rank_match_suggestions

NOW = datetime(2026, 7, 24, 12, tzinfo=UTC)


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
