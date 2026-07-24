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
    LineupSnapshot,
    Market,
    MatchResult,
    ModelEventOutput,
    OddsSnapshot,
    PlayerStatistic,
    Team,
    ValueSignal,
)
from app.quant.match_suggestions import BookmakerCode
from app.schemas.api import EventSummary
from app.schemas.matchday import (
    MatchdayCompetitionView,
    MatchdayEventDetailView,
    MatchdayEventView,
    MatchdayView,
    RecentTeamResultView,
    ResearchGateView,
    TeamFormView,
)
from app.services.builder import list_bet_builder_quotes
from app.services.catalog import get_event, odds_comparison
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
    lineup_count = (
        session.scalar(
            select(func.count())
            .select_from(LineupSnapshot)
            .where(LineupSnapshot.event_id == event.id, LineupSnapshot.observed_at <= cutoff)
        )
        or 0
    )
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
            "No timestamp-valid expected or confirmed lineup is stored for this match."
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

    return MatchdayEventDetailView(
        event=event_summary,
        competition_group=group_key,
        competition_group_label=group_label,
        as_of=cutoff,
        team_form=[
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
        ],
        markets=markets,
        latest_prediction=latest_prediction,
        signals=signals,
        builder_quotes=builder_quotes,
        suggestions=suggestions,
        selected_bookmakers=sorted(selected),
        bookmaker_options=bookmaker_options(markets, selected),
        suggestion_market_statuses=market_statuses(markets, selected, ranked_suggestions),
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
