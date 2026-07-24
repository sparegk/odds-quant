from __future__ import annotations

import unicodedata
from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, aliased

from app.db.models import (
    Bookmaker,
    Competition,
    Event,
    Market,
    MatchResult,
    ModelEventOutput,
    OddsSnapshot,
    PlayerStatistic,
    Team,
    ValueSignal,
)
from app.quant.match_suggestions import BookmakerCode
from app.schemas.api import EventSummary, MarketComparison
from app.schemas.builder import BetBuilderQuoteView
from app.schemas.lineups import ExpectedLineupScenarioView, StoredLineupView
from app.schemas.matchday import (
    AvailabilityAuditItemView,
    MatchdayCompetitionView,
    MatchdayEventDetailView,
    MatchdayEventView,
    MatchdayView,
    RecentTeamResultView,
    ResearchGateView,
    SuggestionMarketStatusView,
    TeamFormView,
)
from app.schemas.models import ModelOutputView
from app.schemas.signals import ValueSignalView
from app.services.builder import list_bet_builder_quotes
from app.services.catalog import get_event, odds_comparison
from app.services.lineup_projection import latest_stored_lineups, project_expected_lineups
from app.services.match_suggestions import (
    bookmaker_options,
    build_match_suggestions,
    market_statuses,
)
from app.services.modeling import list_event_predictions
from app.services.signals import list_value_signals


class MatchdayError(ValueError):
    pass


_COMPETITION_GROUPS = (
    ("champions-league", "UEFA Champions League", 10, ("champions league",)),
    ("premier-league", "Premier League", 20, ("premier league", "english premier")),
    ("la-liga", "La Liga", 30, ("la liga", "primera division")),
    ("bundesliga", "Bundesliga", 40, ("bundesliga",)),
    ("ligue-1", "Ligue 1", 50, ("ligue 1",)),
    ("europa-league", "UEFA Europa League", 60, ("europa league",)),
    ("conference-league", "UEFA Conference League", 70, ("conference league",)),
    (
        "top-cups",
        "Top domestic cups",
        80,
        (
            "fa cup",
            "efl cup",
            "league cup",
            "carabao cup",
            "copa del rey",
            "dfb pokal",
            "coupe de france",
            "coppa italia",
            "uefa super cup",
        ),
    ),
    (
        "major-events",
        "Major events",
        90,
        (
            "world cup",
            "european championship",
            "uefa euro",
            "copa america",
            "nations league",
            "club world cup",
        ),
    ),
)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _normalized(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return " ".join("".join(char for char in decomposed if not unicodedata.combining(char)).split())


def competition_group(name: str) -> tuple[str, str, int, bool]:
    normalized = _normalized(name)
    for key, label, priority, terms in _COMPETITION_GROUPS:
        if any(term in normalized for term in terms):
            return key, label, priority, True
    return "other", "Other tracked competitions", 999, False


def _availability_audit(
    *,
    markets: list[MarketComparison],
    market_status_items: list[SuggestionMarketStatusView],
    team_form: list[TeamFormView],
    latest_prediction: ModelOutputView | None,
    signals: list[ValueSignalView],
    builder_quotes: list[BetBuilderQuoteView],
    stored_lineups: list[StoredLineupView],
    lineup_projections: list[ExpectedLineupScenarioView],
    lineup_gate: ResearchGateView,
    player_records: int,
    player_reasons: list[str],
) -> list[AvailabilityAuditItemView]:
    status_by_code = {item.code: item for item in market_status_items}
    definitions = (
        ("match_result", "1X2", lambda value: value == "MATCH_RESULT"),
        ("double_chance", "Double chance", lambda value: value == "DOUBLE_CHANCE"),
        (
            "goals",
            "Goals, BTTS & team totals",
            lambda value: value in {"TOTALS", "BOTH_TEAMS_TO_SCORE", "TEAM_TOTALS", "TEAM_TOTAL"},
        ),
        ("corners", "Corners", lambda value: "CORNER" in value),
        (
            "shots",
            "Shots",
            lambda value: "SHOT" in value and "TARGET" not in value and "PLAYER" not in value,
        ),
        (
            "shots_on_target",
            "Shots on target",
            lambda value: "SHOT" in value and "TARGET" in value and "PLAYER" not in value,
        ),
        ("player_props", "Player props", lambda value: "PLAYER" in value),
    )
    unlocks = {
        "match_result": ["Import a fresh, complete 1X2 snapshot from an allowed source."],
        "double_chance": [
            "Import timestamped double-chance prices with matching settlement rules."
        ],
        "goals": ["Import timestamped totals, BTTS, or team-total prices for this event."],
        "corners": ["Import complete corner-market prices and their settlement metadata."],
        "shots": ["Import validated team shot markets with timestamped prices."],
        "shots_on_target": [
            "Import validated team shots-on-target markets with timestamped prices."
        ],
        "player_props": [
            "Validate player-level targets and settlement independently before enabling outputs.",
            "Store timestamp-valid player history with minimum minutes and position adjustment.",
        ],
    }
    audit: list[AvailabilityAuditItemView] = []
    for code, label, matches in definitions:
        compatible = [market for market in markets if matches(market.market_type)]
        snapshots = [snapshot for market in compatible for snapshot in market.snapshots]
        best_prices = sum(len(market.best_prices) for market in compatible)
        stale = sum(snapshot.is_stale for snapshot in snapshots)
        source_status = status_by_code.get(code)
        status = (
            "available"
            if source_status is not None and source_status.status == "available"
            else "partial"
            if compatible or snapshots
            else "blocked"
        )
        blockers = []
        if status != "available":
            blockers.append(
                source_status.reason
                if source_status is not None
                else "No compatible, timestamp-valid market evidence is stored."
            )
        unlock_requirements = unlocks[code]
        if code == "match_result" and snapshots:
            unlock_requirements = [
                "Evaluate a leakage-safe model, persist its pre-kickoff prediction, and generate "
                "a qualified value signal against the stored price."
            ]
        audit.append(
            AvailabilityAuditItemView(
                code=code,
                label=label,
                status=status,
                present_records=len(snapshots),
                research_only=(
                    status != "available" or (bool(snapshots) and stale == len(snapshots))
                ),
                evidence=[
                    f"{len(compatible)} compatible market(s) stored.",
                    f"{len(snapshots)} bookmaker snapshot(s), including {stale} stale.",
                    f"{best_prices} selection-level best price(s) retained for inspection.",
                ],
                blockers=blockers,
                unlock_requirements=unlock_requirements,
            )
        )

    builder_status = status_by_code.get("builder")
    audit.append(
        AvailabilityAuditItemView(
            code="builder",
            label="Bet builder",
            status=(
                "available"
                if builder_status is not None and builder_status.status == "available"
                else "partial"
                if builder_quotes
                else "blocked"
            ),
            present_records=len(builder_quotes),
            research_only=not (builder_status is not None and builder_status.status == "available"),
            evidence=[f"{len(builder_quotes)} timestamp-valid builder quote(s) stored."],
            blockers=(
                []
                if builder_status is not None and builder_status.status == "available"
                else [
                    builder_status.reason
                    if builder_status is not None
                    else "No timestamp-valid builder quote is stored."
                ]
            ),
            unlock_requirements=[
                "Store an identical offered combination whose lower-bound expected value "
                "is positive."
            ],
        )
    )
    prediction_records = int(latest_prediction is not None) + len(signals)
    audit.append(
        AvailabilityAuditItemView(
            code="model_prediction",
            label="Model prediction & value signals",
            status=(
                "available"
                if signals
                else "partial"
                if latest_prediction is not None
                else "blocked"
            ),
            present_records=prediction_records,
            research_only=not bool(signals),
            evidence=[
                f"{int(latest_prediction is not None)} pre-kickoff prediction(s) selected.",
                f"{len(signals)} timestamp-valid value signal(s) stored.",
            ],
            blockers=(
                [] if signals else ["No qualified, timestamp-valid value signal is available."]
            ),
            unlock_requirements=[
                "Persist a pre-kickoff prediction from an evaluated model and generate a "
                "qualified signal."
            ],
        )
    )
    lineup_records = lineup_gate.available_records
    audit.append(
        AvailabilityAuditItemView(
            code="lineups",
            label="Expected & confirmed lineups",
            status=(
                "available"
                if lineup_gate.status == "available"
                else "partial"
                if lineup_records or lineup_projections
                else "blocked"
            ),
            present_records=lineup_records,
            research_only=lineup_gate.status != "available",
            evidence=[
                f"{len(stored_lineups)} stored third-party lineup(s).",
                f"{len(lineup_projections)} point-in-time fallback scenario(s).",
                f"{lineup_records} proposed or stored starter record(s).",
            ],
            blockers=([] if lineup_gate.status == "available" else lineup_gate.reasons),
            unlock_requirements=[
                "Provide 11 position-valid starters for both teams from timestamp-valid evidence."
            ],
        )
    )
    form_records = sum(item.sample_size for item in team_form)
    covered_form_teams = sum(item.sample_size > 0 for item in team_form)
    audit.append(
        AvailabilityAuditItemView(
            code="team_form",
            label="Team form",
            status="available"
            if covered_form_teams == 2
            else "partial"
            if form_records
            else "blocked",
            present_records=form_records,
            research_only=covered_form_teams < 2,
            evidence=[
                f"{form_records} timestamp-valid final result(s) across "
                f"{covered_form_teams}/2 teams."
            ],
            blockers=[warning for item in team_form for warning in item.warnings],
            unlock_requirements=["Import timestamp-valid prior final results for both teams."],
        )
    )
    audit.append(
        AvailabilityAuditItemView(
            code="player_evidence",
            label="Player performance evidence",
            status="partial" if player_records else "blocked",
            present_records=player_records,
            research_only=True,
            evidence=[f"{player_records} timestamp-valid player performance record(s) stored."],
            blockers=player_reasons,
            unlock_requirements=[
                "Add position-appropriate metrics, minimum minutes, recency and opponent "
                "adjustment.",
                "Pass chronological ablation and independent target/settlement validation.",
            ],
        )
    )
    return audit


def _timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise MatchdayError(f"unknown IANA timezone: {name}") from exc


def list_matchday(
    session: Session,
    *,
    match_date: date | None,
    timezone_name: str,
    as_of: datetime | None = None,
) -> MatchdayView:
    zone = _timezone(timezone_name)
    reference = _utc(as_of or datetime.now(UTC))
    local_date = match_date or reference.astimezone(zone).date()
    local_start = datetime.combine(local_date, time.min, tzinfo=zone)
    local_end = datetime.combine(local_date + timedelta(days=1), time.min, tzinfo=zone)
    utc_start = local_start.astimezone(UTC)
    utc_end = local_end.astimezone(UTC)

    home = aliased(Team)
    away = aliased(Team)
    rows = session.execute(
        select(Event, Competition, home.name, away.name)
        .join(Competition, Competition.id == Event.competition_id)
        .join(home, home.id == Event.home_team_id)
        .join(away, away.id == Event.away_team_id)
        .where(Event.kickoff_at >= utc_start, Event.kickoff_at < utc_end)
        .order_by(Event.kickoff_at, Event.id)
    ).all()

    grouped: dict[int, list[MatchdayEventView]] = defaultdict(list)
    competitions: dict[int, Competition] = {}
    for event, competition, home_name, away_name in rows:
        competitions[competition.id] = competition
        cutoff = _event_cutoff(event, reference)
        latest_odds = session.scalar(
            select(func.max(OddsSnapshot.observed_at))
            .join(Market, Market.id == OddsSnapshot.market_id)
            .where(Market.event_id == event.id, OddsSnapshot.observed_at <= cutoff)
        )
        market_count = session.scalar(
            select(func.count()).select_from(Market).where(Market.event_id == event.id)
        )
        bookmaker_count = session.scalar(
            select(func.count(func.distinct(Bookmaker.id)))
            .select_from(OddsSnapshot)
            .join(Market, Market.id == OddsSnapshot.market_id)
            .join(Bookmaker, Bookmaker.id == OddsSnapshot.bookmaker_id)
            .where(Market.event_id == event.id, OddsSnapshot.observed_at <= cutoff)
        )
        latest_prediction = session.scalar(
            select(func.max(ModelEventOutput.predicted_at)).where(
                ModelEventOutput.event_id == event.id,
                ModelEventOutput.predicted_at <= cutoff,
                ModelEventOutput.inputs_as_of <= cutoff,
            )
        )
        signal_count = session.scalar(
            select(func.count())
            .select_from(ValueSignal)
            .where(
                ValueSignal.event_id == event.id,
                ValueSignal.signal_type == "VALUE",
                ValueSignal.generated_at <= cutoff,
            )
        )
        grouped[competition.id].append(
            MatchdayEventView(
                event=EventSummary(
                    id=event.id,
                    provider_event_key=event.provider_event_key,
                    competition_id=competition.id,
                    competition=competition.name,
                    country=competition.country,
                    season=competition.season,
                    home_team=home_name,
                    away_team=away_name,
                    kickoff_at=_utc(event.kickoff_at),
                    status=event.status,
                    is_demo=event.is_demo,
                    latest_odds_at=_utc(latest_odds) if latest_odds is not None else None,
                ),
                market_count=market_count or 0,
                bookmaker_count=bookmaker_count or 0,
                latest_prediction_at=(
                    _utc(latest_prediction) if latest_prediction is not None else None
                ),
                qualified_signal_count=signal_count or 0,
            )
        )

    schedule: list[MatchdayCompetitionView] = []
    for competition_id, events in grouped.items():
        stored = competitions[competition_id]
        group_key, group_label, priority, featured = competition_group(stored.name)
        schedule.append(
            MatchdayCompetitionView(
                competition_id=stored.id,
                name=stored.name,
                country=stored.country,
                season=stored.season,
                group_key=group_key,
                group_label=group_label,
                priority=priority,
                is_featured=featured,
                events=events,
            )
        )
    schedule.sort(key=lambda value: (value.priority, value.name, value.competition_id))
    return MatchdayView(
        date=local_date,
        timezone=timezone_name,
        local_start=local_start,
        local_end=local_end,
        as_of=reference,
        total_events=sum(len(item.events) for item in schedule),
        competitions=schedule,
        data_note=(
            "Only imported, timestamped fixtures are shown. Odds, predictions, and signals are "
            "limited to records available before each kickoff."
        ),
    )


def get_matchday_event_detail(
    session: Session,
    *,
    event_id: int,
    as_of: datetime | None = None,
    stale_after_seconds: int = 300,
    form_matches: int = 5,
    selected_bookmakers: set[BookmakerCode] | None = None,
) -> MatchdayEventDetailView | None:
    event_summary = get_event(session, event_id)
    event = session.get(Event, event_id)
    if event_summary is None or event is None:
        return None
    reference = _utc(as_of or datetime.now(UTC))
    cutoff = _event_cutoff(event, reference)
    group_key, group_label, _, _ = competition_group(event_summary.competition)

    predictions = [
        prediction
        for prediction in list_event_predictions(session, event.id)
        if _utc(prediction.predicted_at) <= cutoff and _utc(prediction.inputs_as_of) <= cutoff
    ]
    latest_prediction = predictions[0] if predictions else None
    signals = [
        signal
        for signal in list_value_signals(session, event_id=event.id)
        if _utc(signal.generated_at) <= cutoff
    ]
    builder_quotes = [
        quote
        for quote in list_bet_builder_quotes(session, event_id=event.id)
        if _utc(quote.quoted_at) <= cutoff
    ]
    selected = selected_bookmakers or {"allwyn", "novibet"}
    markets = odds_comparison(
        session,
        event_id=event.id,
        as_of=cutoff,
        stale_after_seconds=stale_after_seconds,
    )
    suggestions, ranked_suggestions = build_match_suggestions(
        signals=signals,
        builder_quotes=builder_quotes,
        selected_bookmakers=selected,
        cutoff=cutoff,
        max_price_age_minutes=stale_after_seconds / 60,
        event_is_demo=event.is_demo,
    )

    player_records = (
        session.scalar(
            select(func.count())
            .select_from(PlayerStatistic)
            .join(Event, Event.id == PlayerStatistic.event_id)
            .where(
                or_(
                    Event.home_team_id == event.home_team_id,
                    Event.away_team_id == event.home_team_id,
                ),
                Event.kickoff_at < event.kickoff_at,
                PlayerStatistic.observed_at <= cutoff,
            )
        )
        or 0
    )
    player_records += (
        session.scalar(
            select(func.count())
            .select_from(PlayerStatistic)
            .join(Event, Event.id == PlayerStatistic.event_id)
            .where(
                or_(
                    Event.home_team_id == event.away_team_id,
                    Event.away_team_id == event.away_team_id,
                ),
                Event.kickoff_at < event.kickoff_at,
                PlayerStatistic.observed_at <= cutoff,
            )
        )
        or 0
    )
    stored_lineups = latest_stored_lineups(session, event_id=event.id, as_of=cutoff)
    complete_stored_teams = {
        lineup.team_id
        for lineup in stored_lineups
        if sum(member.starter for member in lineup.members) == 11
    }
    lineup_projections = [
        scenario
        for scenario in project_expected_lineups(
            session,
            event_id=event.id,
            as_of=cutoff,
            history_matches=form_matches,
        )
        if scenario.team_id not in complete_stored_teams
    ]
    complete_projected_teams = {
        scenario.team_id
        for scenario in lineup_projections
        if scenario.scenario_kind == "availability_weighted" and scenario.status == "projected"
    }
    lineup_covered_teams = complete_stored_teams | complete_projected_teams
    lineup_count = len(stored_lineups)
    player_reasons = [
        "Player-level targets and settlement rules have not been independently validated.",
        "Position-adjusted minimum minutes, shrinkage, and chronological ablations are required "
        "before player betting outputs can be enabled.",
    ]
    if player_records == 0:
        player_reasons.append(
            "No timestamp-valid player performance history is stored for these teams."
        )
    if lineup_count == 0:
        player_reasons.append(
            "No timestamp-valid third-party expected or confirmed lineup is stored for this match."
        )

    lineup_reasons = [
        "Confirmed, third-party expected, and OddsQuant fallback lineups remain separate "
        "evidence classes.",
        "Fallback projections use only timestamp-valid prior appearances and availability "
        "known at the cutoff.",
        "Lineup projections widen decision uncertainty; they do not create model edge until "
        "chronological ablation validates an adjustment.",
    ]
    if lineup_projections:
        lineup_reasons.append(
            "Fallback scenarios are shown because a complete stored lineup was unavailable "
            "for at least one team."
        )
    if len(lineup_covered_teams) < 2:
        lineup_reasons.append(
            "At least one team lacks enough position-valid evidence for a complete XI."
        )
    baseline_projections = [
        scenario
        for scenario in lineup_projections
        if scenario.scenario_kind == "availability_weighted"
    ]
    lineup_gate = ResearchGateView(
        status="available" if len(lineup_covered_teams) == 2 else "blocked",
        title=(
            "Lineup scenarios available"
            if len(lineup_covered_teams) == 2
            else "Lineup uncertainty remains high"
        ),
        available_records=(
            sum(len(lineup.members) for lineup in stored_lineups)
            + sum(len(scenario.starters) for scenario in baseline_projections)
        ),
        reasons=lineup_reasons,
    )

    qualified_builder_quotes = [
        quote
        for quote in builder_quotes
        if not quote.is_demo
        and quote.offered_odds is not None
        and quote.offered_odds_observed_at is not None
        and quote.lower_expected_value is not None
        and quote.lower_expected_value > 0
    ]
    if qualified_builder_quotes:
        builder_gate = ResearchGateView(
            status="available",
            title="Conservatively positive builder quotes",
            available_records=len(qualified_builder_quotes),
            reasons=[
                "These are stored, timestamped offered prices whose lower probability bound "
                "remains positive-EV. Recheck identical legs and settlement rules before use."
            ],
        )
    else:
        builder_gate = ResearchGateView(
            status="blocked",
            title="No verified builder value",
            available_records=len(builder_quotes),
            reasons=[
                "A likely combination is not automatically value.",
                "An identical timestamped bookmaker quote must exceed the model fair price even "
                "at the lower probability bound.",
            ],
        )

    team_form = [
        _team_form(
            session,
            event,
            event.home_team_id,
            event_summary.home_team,
            cutoff,
            form_matches,
        ),
        _team_form(
            session,
            event,
            event.away_team_id,
            event_summary.away_team,
            cutoff,
            form_matches,
        ),
    ]
    suggestion_market_statuses = market_statuses(markets, selected, ranked_suggestions)
    availability_audit = _availability_audit(
        markets=markets,
        market_status_items=suggestion_market_statuses,
        team_form=team_form,
        latest_prediction=latest_prediction,
        signals=signals,
        builder_quotes=builder_quotes,
        stored_lineups=stored_lineups,
        lineup_projections=lineup_projections,
        lineup_gate=lineup_gate,
        player_records=player_records,
        player_reasons=player_reasons,
    )

    return MatchdayEventDetailView(
        event=event_summary,
        competition_group=group_key,
        competition_group_label=group_label,
        as_of=cutoff,
        team_form=team_form,
        markets=markets,
        latest_prediction=latest_prediction,
        signals=signals,
        builder_quotes=builder_quotes,
        suggestions=suggestions,
        selected_bookmakers=sorted(selected),
        bookmaker_options=bookmaker_options(markets, selected),
        suggestion_market_statuses=suggestion_market_statuses,
        availability_audit=availability_audit,
        stored_lineups=stored_lineups,
        lineup_projections=lineup_projections,
        lineup_research=lineup_gate,
        player_research=ResearchGateView(
            status="blocked",
            title="Player markets remain research-only",
            available_records=player_records + lineup_count,
            reasons=player_reasons,
        ),
        builder_value=builder_gate,
        bookmaker_guidance=(
            "There is no universal best bookmaker for a match. Use the best timestamp-valid price "
            "for each identical selection; compare parlays only when every leg, period, line, and "
            "settlement rule matches."
        ),
        evidence_note=(
            "High probability is not the same as a betting edge. A bet candidate appears only when "
            "stored calibrated signals or conservatively positive builder quotes support it."
        ),
    )


def _event_cutoff(event: Event, reference: datetime) -> datetime:
    kickoff = _utc(event.kickoff_at)
    return min(reference, kickoff - timedelta(microseconds=1))


def _team_form(
    session: Session,
    target: Event,
    team_id: int,
    team_name: str,
    cutoff: datetime,
    limit: int,
) -> TeamFormView:
    home = aliased(Team)
    away = aliased(Team)
    rows = session.execute(
        select(MatchResult, Event, home.name, away.name)
        .join(Event, Event.id == MatchResult.event_id)
        .join(home, home.id == Event.home_team_id)
        .join(away, away.id == Event.away_team_id)
        .where(
            or_(Event.home_team_id == team_id, Event.away_team_id == team_id),
            Event.kickoff_at < target.kickoff_at,
            MatchResult.is_final.is_(True),
            MatchResult.settled_at <= cutoff,
            MatchResult.observed_at <= cutoff,
        )
        .order_by(Event.kickoff_at.desc(), MatchResult.observed_at.desc(), MatchResult.id.desc())
    ).all()

    latest_by_event: dict[int, tuple[MatchResult, Event, str, str]] = {}
    for result, event, home_name, away_name in rows:
        latest_by_event.setdefault(event.id, (result, event, home_name, away_name))

    canonical: dict[tuple[datetime, int, int], tuple[MatchResult, Event, str, str]] = {}
    conflicted: set[tuple[datetime, int, int]] = set()
    for row in latest_by_event.values():
        result, event, _, _ = row
        key = (_utc(event.kickoff_at), event.home_team_id, event.away_team_id)
        existing = canonical.get(key)
        if existing is not None and (
            existing[0].home_goals,
            existing[0].away_goals,
        ) != (result.home_goals, result.away_goals):
            conflicted.add(key)
            canonical.pop(key, None)
            continue
        if key not in conflicted and (
            existing is None or _utc(result.observed_at) > _utc(existing[0].observed_at)
        ):
            canonical[key] = row

    selected = sorted(
        canonical.values(), key=lambda row: (_utc(row[1].kickoff_at), row[1].id), reverse=True
    )[:limit]
    recent: list[RecentTeamResultView] = []
    wins = draws = losses = goals_for = goals_against = clean_sheets = 0
    for result, event, home_name, away_name in selected:
        at_home = event.home_team_id == team_id
        scored = result.home_goals if at_home else result.away_goals
        conceded = result.away_goals if at_home else result.home_goals
        if scored > conceded:
            outcome = "W"
            wins += 1
        elif scored == conceded:
            outcome = "D"
            draws += 1
        else:
            outcome = "L"
            losses += 1
        goals_for += scored
        goals_against += conceded
        clean_sheets += int(conceded == 0)
        recent.append(
            RecentTeamResultView(
                event_id=event.id,
                kickoff_at=_utc(event.kickoff_at),
                opponent=away_name if at_home else home_name,
                venue="home" if at_home else "away",
                goals_for=scored,
                goals_against=conceded,
                outcome=outcome,
                observed_at=_utc(result.observed_at),
            )
        )
    sample_size = len(recent)
    warnings: list[str] = []
    if sample_size == 0:
        warnings.append("No timestamp-valid prior final results are stored for this team.")
    elif sample_size < limit:
        warnings.append(
            f"Only {sample_size} timestamp-valid prior finals are stored (target {limit})."
        )
    if conflicted:
        warnings.append("Conflicting provider scores were excluded from this form sample.")
    return TeamFormView(
        team_id=team_id,
        team=team_name,
        sample_size=sample_size,
        wins=wins,
        draws=draws,
        losses=losses,
        goals_for=goals_for,
        goals_against=goals_against,
        clean_sheets=clean_sheets,
        points_per_game=(round((wins * 3 + draws) / sample_size, 3) if sample_size else None),
        results=recent,
        warnings=warnings,
    )
