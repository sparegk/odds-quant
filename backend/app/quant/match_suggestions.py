from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

BookmakerCode = Literal["allwyn", "novibet"]
SuggestionKind = Literal["single", "builder"]

BOOKMAKER_NAMES: dict[BookmakerCode, str] = {
    "allwyn": "Allwyn / Pamestoixima",
    "novibet": "Novibet",
}

SINGLE_MARKETS = frozenset(
    {
        "MATCH_RESULT",
        "TOTAL_GOALS",
        "BOTH_TEAMS_TO_SCORE",
        "DOUBLE_CHANCE",
        "TEAM_TOTAL_HOME",
        "TEAM_TOTAL_AWAY",
    }
)


@dataclass(frozen=True)
class SuggestionCandidate:
    source_id: int
    kind: SuggestionKind
    bookmaker: str
    market_type: str
    offered_odds: float | None
    lower_probability: float
    lower_expected_value: float | None
    confidence: float
    price_observed_at: datetime | None
    generated_at: datetime
    cutoff: datetime
    is_demo: bool = False
    qualified: bool = True


@dataclass(frozen=True)
class RankedSuggestion:
    candidate: SuggestionCandidate
    bookmaker_code: BookmakerCode
    conservative_score: float


def bookmaker_code(name: str) -> BookmakerCode | None:
    normalized = " ".join(name.casefold().replace("/", " ").split())
    if normalized in {"allwyn", "pamestoixima", "allwyn pamestoixima"}:
        return "allwyn"
    if normalized == "novibet":
        return "novibet"
    return None


def rank_match_suggestions(
    candidates: list[SuggestionCandidate],
    *,
    selected_bookmakers: set[BookmakerCode],
    max_price_age_minutes: float,
    min_single_probability: float = 0.5,
    min_builder_probability: float = 0.25,
) -> list[RankedSuggestion]:
    """Fail closed and rank only executable, conservatively positive candidates."""

    if not selected_bookmakers:
        return []
    if max_price_age_minutes < 0:
        raise ValueError("max_price_age_minutes cannot be negative")

    ranked: list[RankedSuggestion] = []
    for candidate in candidates:
        code = bookmaker_code(candidate.bookmaker)
        minimum_probability = (
            min_builder_probability if candidate.kind == "builder" else min_single_probability
        )
        market_supported = (
            candidate.market_type == "BET_BUILDER"
            if candidate.kind == "builder"
            else candidate.market_type in SINGLE_MARKETS
        )
        timestamps_valid = (
            candidate.price_observed_at is not None
            and candidate.price_observed_at.tzinfo is not None
            and candidate.generated_at.tzinfo is not None
            and candidate.cutoff.tzinfo is not None
            and candidate.price_observed_at <= candidate.generated_at <= candidate.cutoff
        )
        price_age_minutes = (
            (candidate.generated_at - candidate.price_observed_at).total_seconds() / 60
            if timestamps_valid and candidate.price_observed_at is not None
            else float("inf")
        )
        if (
            code is None
            or code not in selected_bookmakers
            or not candidate.qualified
            or candidate.is_demo
            or not market_supported
            or candidate.offered_odds is None
            or candidate.offered_odds <= 1
            or candidate.lower_expected_value is None
            or candidate.lower_expected_value <= 0
            or not 0 <= candidate.confidence <= 1
            or candidate.confidence <= 0
            or not 0 <= candidate.lower_probability <= 1
            or candidate.lower_probability < minimum_probability
            or price_age_minutes > max_price_age_minutes
        ):
            continue

        ranked.append(
            RankedSuggestion(
                candidate=candidate,
                bookmaker_code=code,
                conservative_score=candidate.lower_expected_value * candidate.confidence,
            )
        )

    return sorted(
        ranked,
        key=lambda item: (
            -item.conservative_score,
            -item.candidate.lower_probability,
            -float(item.candidate.offered_odds or 0),
            item.candidate.source_id,
        ),
    )
