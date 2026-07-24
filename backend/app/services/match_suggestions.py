from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.quant.match_suggestions import (
    BOOKMAKER_NAMES,
    BookmakerCode,
    RankedSuggestion,
    SuggestionCandidate,
    bookmaker_code,
    rank_match_suggestions,
)
from app.schemas.api import MarketComparison
from app.schemas.builder import BetBuilderQuoteView
from app.schemas.matchday import (
    MatchdayBookmakerOptionView,
    MatchSuggestionView,
    SuggestionMarketStatusView,
)
from app.schemas.signals import ValueSignalView

BOOKMAKER_CODES: tuple[BookmakerCode, BookmakerCode] = ("allwyn", "novibet")


def build_match_suggestions(
    *,
    signals: list[ValueSignalView],
    builder_quotes: list[BetBuilderQuoteView],
    selected_bookmakers: set[BookmakerCode],
    cutoff: datetime,
    max_price_age_minutes: float,
    event_is_demo: bool,
) -> tuple[list[MatchSuggestionView], list[RankedSuggestion]]:
    candidates = [
        SuggestionCandidate(
            source_id=signal.id,
            kind="single",
            bookmaker=signal.bookmaker,
            market_type=signal.market_type,
            offered_odds=signal.offered_odds,
            lower_probability=signal.lower_probability,
            lower_expected_value=signal.lower_expected_value,
            confidence=signal.confidence,
            price_observed_at=_utc(signal.generated_at)
            - timedelta(minutes=signal.odds_age_minutes),
            generated_at=_utc(signal.generated_at),
            cutoff=cutoff,
            is_demo=event_is_demo,
            qualified=signal.signal_type == "VALUE",
        )
        for signal in signals
    ]
    candidates.extend(
        SuggestionCandidate(
            source_id=quote.id,
            kind="builder",
            bookmaker=quote.offered_odds_source or "",
            market_type="BET_BUILDER",
            offered_odds=quote.offered_odds,
            lower_probability=quote.lower_joint_probability,
            lower_expected_value=quote.lower_expected_value,
            confidence=1.0,
            price_observed_at=quote.offered_odds_observed_at,
            generated_at=_utc(quote.quoted_at),
            cutoff=cutoff,
            is_demo=quote.is_demo,
            qualified=quote.evidence_class == "team_baseline",
        )
        for quote in builder_quotes
    )
    ranked = rank_match_suggestions(
        candidates,
        selected_bookmakers=selected_bookmakers,
        max_price_age_minutes=max_price_age_minutes,
    )
    views = [
        _suggestion_view(item, signals=signals, builder_quotes=builder_quotes, rank=index)
        for index, item in enumerate(ranked, start=1)
    ]
    return views, ranked


def bookmaker_options(
    markets: list[MarketComparison],
    selected: set[BookmakerCode],
) -> list[MatchdayBookmakerOptionView]:
    offered: dict[BookmakerCode, set[str]] = {
        "allwyn": set(),
        "novibet": set(),
    }
    for market in markets:
        for snapshot in market.snapshots:
            code = bookmaker_code(snapshot.bookmaker)
            if code is not None and not snapshot.is_stale:
                offered[code].add(market.market_type)
    return [
        MatchdayBookmakerOptionView(
            code=code,
            name=BOOKMAKER_NAMES[code],
            selected=code in selected,
            has_current_prices=bool(offered[code]),
            offered_market_types=sorted(offered[code]),
        )
        for code in BOOKMAKER_CODES
    ]


def market_statuses(
    markets: list[MarketComparison],
    selected: set[BookmakerCode],
    suggestions: list[RankedSuggestion],
) -> list[SuggestionMarketStatusView]:
    offered_types = {
        market.market_type
        for market in markets
        if any(
            bookmaker_code(snapshot.bookmaker) in selected and not snapshot.is_stale
            for snapshot in market.snapshots
        )
    }
    suggested_types = {item.candidate.market_type for item in suggestions}

    def status(
        code: str,
        label: str,
        market_types: set[str],
    ) -> SuggestionMarketStatusView:
        if suggested_types.intersection(market_types):
            return SuggestionMarketStatusView(
                code=code,
                label=label,
                status="available",
                reason="A selected bookmaker has an exact qualified value suggestion.",
            )
        if offered_types.intersection(market_types):
            return SuggestionMarketStatusView(
                code=code,
                label=label,
                status="price_only",
                reason=(
                    "An exact selected-bookmaker price is stored, but no calibrated "
                    "conservative-value signal qualifies."
                ),
            )
        return SuggestionMarketStatusView(
            code=code,
            label=label,
            status="blocked",
            reason="No fresh exact price from a selected bookmaker is stored.",
        )

    result = [
        status("match_result", "1X2", {"MATCH_RESULT"}),
        status("double_chance", "Double chance (1X / X2 / 12)", {"DOUBLE_CHANCE"}),
        status(
            "goals",
            "Goals / BTTS / team totals",
            {
                "TOTAL_GOALS",
                "BOTH_TEAMS_TO_SCORE",
                "TEAM_TOTAL_HOME",
                "TEAM_TOTAL_AWAY",
            },
        ),
        status("builder", "Bet builder", {"BET_BUILDER"}),
    ]
    corner_prices = "TOTAL_CORNERS" in offered_types
    result.append(
        SuggestionMarketStatusView(
            code="corners",
            label="Corners",
            status="price_only" if corner_prices else "blocked",
            reason=(
                "A fresh corner price is stored, but no validated corner target exists, "
                "so it is not a recommendation."
                if corner_prices
                else "No fresh exact corner price is stored and no validated corner target exists."
            ),
        )
    )
    for code, label in (
        ("shots", "Shots"),
        ("shots_on_target", "Shots on target"),
        ("player_props", "Player props"),
    ):
        result.append(
            SuggestionMarketStatusView(
                code=code,
                label=label,
                status="blocked",
                reason=(
                    "Player-level targets and settlement are not independently validated; "
                    "this market cannot produce a suggestion."
                ),
            )
        )
    return result


def _suggestion_view(
    ranked: RankedSuggestion,
    *,
    signals: list[ValueSignalView],
    builder_quotes: list[BetBuilderQuoteView],
    rank: int,
) -> MatchSuggestionView:
    candidate = ranked.candidate
    if candidate.kind == "single":
        signal = next(item for item in signals if item.id == candidate.source_id)
        return MatchSuggestionView(
            rank=rank,
            source_kind="single",
            source_id=signal.id,
            bookmaker_code=ranked.bookmaker_code,
            bookmaker=signal.bookmaker,
            market_type=signal.market_type,
            selection_code=signal.selection_code,
            selection_name=signal.selection_name,
            line=signal.line,
            legs=[],
            offered_odds=signal.offered_odds,
            model_probability=signal.model_probability,
            lower_probability=signal.lower_probability,
            market_fair_probability=signal.market_fair_probability,
            expected_value=signal.expected_value,
            lower_expected_value=signal.lower_expected_value,
            confidence=signal.confidence,
            conservative_score=ranked.conservative_score,
            price_observed_at=_utc(signal.generated_at)
            - timedelta(minutes=signal.odds_age_minutes),
            generated_at=_utc(signal.generated_at),
            reasons=signal.reasons,
            risks=signal.risks,
        )
    quote = next(item for item in builder_quotes if item.id == candidate.source_id)
    selection_name = " + ".join(
        f"{leg.market_type} {leg.selection}" + (f" {leg.line:g}" if leg.line is not None else "")
        for leg in quote.legs
    )
    assert quote.offered_odds is not None
    assert quote.expected_value is not None
    assert quote.lower_expected_value is not None
    assert quote.offered_odds_observed_at is not None
    return MatchSuggestionView(
        rank=rank,
        source_kind="builder",
        source_id=quote.id,
        bookmaker_code=ranked.bookmaker_code,
        bookmaker=quote.offered_odds_source or "",
        market_type="BET_BUILDER",
        selection_code="BUILDER",
        selection_name=selection_name,
        line=None,
        legs=quote.legs,
        offered_odds=quote.offered_odds,
        model_probability=quote.joint_probability,
        lower_probability=quote.lower_joint_probability,
        market_fair_probability=None,
        expected_value=quote.expected_value,
        lower_expected_value=quote.lower_expected_value,
        confidence=None,
        conservative_score=ranked.conservative_score,
        price_observed_at=quote.offered_odds_observed_at,
        generated_at=_utc(quote.quoted_at),
        reasons=[
            "The identical stored builder quote remains positive value at the lower "
            "joint-probability bound."
        ],
        risks=quote.warnings
        + ["Recheck every leg, line, period, and settlement rule in the bookmaker app."],
    )


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
