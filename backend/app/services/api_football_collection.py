from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from app.db.models import Competition, Event, LineupSnapshot, RawIngestion, Team
from app.providers.api_football import (
    ApiFootballClient,
    ApiFootballFixture,
    ApiFootballLeagueCoverage,
)
from app.services.api_football_intelligence import (
    ApiFootballIntelligenceError,
    build_injury_intelligence_request,
    build_lineup_intelligence_request,
    build_player_intelligence_request,
)
from app.services.intelligence_import import (
    IntelligenceImportError,
    import_intelligence_bundle,
)

_FINISHED_STATUSES = frozenset({"FT", "AET", "PEN"})
_LEAGUE_COMPETITION_PREFIXES = {
    2: ("UEFA Champions League",),
    3: ("UEFA Europa League",),
    848: ("UEFA Conference League",),
    39: ("Premier League",),
    140: ("La Liga",),
    78: ("Bundesliga",),
    61: ("Ligue 1",),
}


class ApiFootballCollectionSummary(BaseModel):
    catalog_date: date
    fixtures_seen: int = Field(ge=0)
    fixtures_matched: int = Field(ge=0)
    fixtures_unmatched: int = Field(ge=0)
    lineups_imported: int = Field(ge=0)
    injuries_imported: int = Field(ge=0)
    player_snapshots_imported: int = Field(ge=0)
    requests_remaining: int | None = Field(default=None, ge=0)
    notes: list[str]


def collect_api_football_intelligence(
    session: Session,
    *,
    client: ApiFootballClient,
    coverage: list[ApiFootballLeagueCoverage],
    on_date: date,
    now: datetime | None = None,
) -> ApiFootballCollectionSummary:
    current = _utc(now or datetime.now(UTC))
    catalog = client.fixture_catalog(on_date)
    supported = {item.league_id: item for item in coverage if item.current}
    local = _local_events(session, on_date)
    matched = 0
    lineups_imported = 0
    injuries_imported = 0
    player_snapshots_imported = 0
    notes: list[str] = []
    for fixture in catalog.fixtures:
        league = supported.get(fixture.league_id)
        if league is None:
            continue
        identity = _match_fixture(fixture, local)
        if identity is None:
            notes.append(
                f"fixture {fixture.fixture_id} did not exactly match one local event identity"
            )
            continue
        matched += 1
        event, home_team_id, away_team_id = identity
        team_ids = {
            fixture.home_team_id: home_team_id,
            fixture.away_team_id: away_team_id,
        }
        until_kickoff = _utc(event.kickoff_at) - current
        has_confirmed = session.scalar(
            select(LineupSnapshot.id).where(
                LineupSnapshot.event_id == event.id,
                LineupSnapshot.lineup_type == "confirmed",
            )
        )
        if (
            league.lineups
            and has_confirmed is None
            and timedelta(0) <= until_kickoff <= timedelta(minutes=50)
        ):
            lineup_snapshot = client.fixture_lineup_snapshot(fixture.fixture_id)
            if lineup_snapshot.teams:
                request = build_lineup_intelligence_request(
                    lineup_snapshot, event_id=event.id, local_team_ids=team_ids
                )
                import_intelligence_bundle(
                    session, request, now=max(current, lineup_snapshot.observed_at)
                )
                lineups_imported += len(lineup_snapshot.teams)
            else:
                notes.append(f"fixture {fixture.fixture_id} lineup is not published yet")
        if (
            league.injuries
            and timedelta(0) <= until_kickoff <= timedelta(minutes=50)
            and not _already_imported(session, fixture.fixture_id, "injuries")
        ):
            injury_snapshot = client.fixture_injury_snapshot(fixture.fixture_id)
            if injury_snapshot.injuries:
                try:
                    request = build_injury_intelligence_request(
                        injury_snapshot, event_id=event.id, local_team_ids=team_ids
                    )
                    result = import_intelligence_bundle(
                        session, request, now=max(current, injury_snapshot.observed_at)
                    )
                    injuries_imported += result.created.get("availability", 0)
                except (ApiFootballIntelligenceError, IntelligenceImportError):
                    notes.append(
                        f"fixture {fixture.fixture_id} injuries await mapped player identities"
                    )
        if (
            league.player_statistics
            and fixture.status in _FINISHED_STATUSES
            and not _already_imported(session, fixture.fixture_id, "players")
        ):
            player_snapshot = client.fixture_player_snapshot(fixture.fixture_id)
            if player_snapshot.performances:
                request = build_player_intelligence_request(
                    player_snapshot, event_id=event.id, local_team_ids=team_ids
                )
                import_intelligence_bundle(
                    session, request, now=max(current, player_snapshot.observed_at)
                )
                player_snapshots_imported += 1
    considered = sum(fixture.league_id in supported for fixture in catalog.fixtures)
    if not catalog.fixtures:
        notes.append("API-Football returned no fixtures for this date")
    elif considered == 0:
        notes.append("No catalog fixtures belong to a currently supported target league")
    return ApiFootballCollectionSummary(
        catalog_date=on_date,
        fixtures_seen=len(catalog.fixtures),
        fixtures_matched=matched,
        fixtures_unmatched=max(considered - matched, 0),
        lineups_imported=lineups_imported,
        injuries_imported=injuries_imported,
        player_snapshots_imported=player_snapshots_imported,
        requests_remaining=client.requests_remaining,
        notes=notes,
    )


def _local_events(session: Session, on_date: date) -> list[tuple[Event, str, str, str]]:
    home = aliased(Team)
    away = aliased(Team)
    start = datetime.combine(on_date, datetime.min.time(), tzinfo=UTC)
    end = start + timedelta(days=1)
    return list(
        session.execute(
            select(Event, Competition.name, home.name, away.name)
            .join(Competition, Competition.id == Event.competition_id)
            .join(home, home.id == Event.home_team_id)
            .join(away, away.id == Event.away_team_id)
            .where(
                Event.is_demo.is_(False),
                Event.kickoff_at >= start,
                Event.kickoff_at < end,
            )
        ).tuples()
    )


def _match_fixture(
    fixture: ApiFootballFixture,
    local: list[tuple[Event, str, str, str]],
) -> tuple[Event, int, int] | None:
    prefixes = _LEAGUE_COMPETITION_PREFIXES.get(fixture.league_id, ())
    matches = [
        event
        for event, competition, home_name, away_name in local
        if any(competition.startswith(prefix) for prefix in prefixes)
        and _utc(event.kickoff_at) == _utc(fixture.kickoff_at)
        and _exact_name(home_name) == _exact_name(fixture.home_team_name)
        and _exact_name(away_name) == _exact_name(fixture.away_team_name)
    ]
    if len(matches) != 1:
        return None
    event = matches[0]
    return event, event.home_team_id, event.away_team_id


def _already_imported(session: Session, fixture_id: int, endpoint: str) -> bool:
    prefix = f"api-football:fixture:{fixture_id}:{endpoint}:%"
    return (
        session.scalar(select(RawIngestion.id).where(RawIngestion.source_key.like(prefix)))
        is not None
    )


def _exact_name(value: str) -> str:
    return " ".join(value.casefold().split())


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
