from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Competition,
    Event,
    FixtureObservation,
    MatchResult,
    ModelEventOutput,
    Provider,
    Sport,
    Team,
)
from app.schemas.fixtures import FixtureImportRow, FixtureImportSummary
from app.services.team_identity import get_or_create_team


class FixtureImportError(ValueError):
    pass


def import_provider_fixtures(
    session: Session,
    *,
    rows: list[FixtureImportRow],
    provider_slug: str,
    provider_name: str,
    provider_kind: str,
    terms_url: str | None,
    is_demo: bool,
    now: datetime | None = None,
) -> FixtureImportSummary:
    ingested_at = _utc(now or datetime.now(UTC))
    if not rows:
        return FixtureImportSummary(
            fixtures_received=0,
            events_created=0,
            observations_created=0,
        )
    identities: dict[str, tuple[object, ...]] = {}
    for row in rows:
        if _utc(row.observed_at) > ingested_at:
            raise FixtureImportError("fixture observation cannot be in the future")
        identity = (
            row.competition,
            row.country,
            row.season,
            _utc(row.kickoff_at),
            row.home_team,
            row.away_team,
        )
        previous = identities.setdefault(row.provider_event_key, identity)
        if previous != identity:
            raise FixtureImportError("fixture batch contains a conflicting event identity")

    provider = session.scalar(select(Provider).where(Provider.slug == provider_slug))
    if provider is None:
        provider = Provider(
            slug=provider_slug,
            name=provider_name,
            kind=provider_kind,
            is_demo=is_demo,
            terms_url=terms_url,
            capabilities={"fixtures": True, "odds": True, "football": True},
        )
        session.add(provider)
        session.flush()
    elif (
        provider.name != provider_name
        or provider.kind != provider_kind
        or provider.is_demo != is_demo
    ):
        raise FixtureImportError("provider metadata conflicts with stored identity")

    sport = session.scalar(select(Sport).where(Sport.slug == "football"))
    if sport is None:
        sport = Sport(slug="football", name="Football")
        session.add(sport)
        session.flush()

    events_created = 0
    observations_created = 0
    seen_observations: set[tuple[str, datetime]] = set()
    for row in rows:
        competition = session.scalar(
            select(Competition).where(
                Competition.sport_id == sport.id,
                Competition.name == row.competition,
                Competition.season == row.season,
            )
        )
        if competition is None:
            competition = Competition(
                sport_id=sport.id,
                name=row.competition,
                country=row.country,
                season=row.season,
            )
            session.add(competition)
            session.flush()
        elif competition.country != row.country:
            raise FixtureImportError("competition country conflicts with stored identity")

        home = get_or_create_team(session, sport_id=sport.id, name=row.home_team)
        away = get_or_create_team(session, sport_id=sport.id, name=row.away_team)
        event = session.scalar(
            select(Event).where(
                Event.provider_id == provider.id,
                Event.provider_event_key == row.provider_event_key,
            )
        )
        if event is None:
            event = Event(
                competition_id=competition.id,
                home_team_id=home.id,
                away_team_id=away.id,
                provider_id=provider.id,
                provider_event_key=row.provider_event_key,
                kickoff_at=row.kickoff_at,
                status=row.status,
                is_demo=is_demo,
            )
            session.add(event)
            session.flush()
            events_created += 1
        elif (
            event.competition_id,
            event.home_team_id,
            event.away_team_id,
            _utc(event.kickoff_at),
        ) != (competition.id, home.id, away.id, _utc(row.kickoff_at)):
            _apply_pre_kickoff_correction(
                session,
                event=event,
                competition=competition,
                home=home,
                away=away,
                row=row,
            )

        observation_key = (row.provider_event_key, _utc(row.observed_at))
        if observation_key in seen_observations:
            continue
        seen_observations.add(observation_key)
        existing = session.scalar(
            select(FixtureObservation).where(
                FixtureObservation.event_id == event.id,
                FixtureObservation.provider_id == provider.id,
                FixtureObservation.observed_at == row.observed_at,
            )
        )
        if existing is None:
            session.add(
                FixtureObservation(
                    event_id=event.id,
                    provider_id=provider.id,
                    competition_id=competition.id,
                    home_team_id=home.id,
                    away_team_id=away.id,
                    kickoff_at=row.kickoff_at,
                    source_updated_at=row.source_updated_at,
                    observed_at=row.observed_at,
                    ingested_at=ingested_at,
                    status=row.status,
                )
            )
            observations_created += 1
        elif (
            existing.competition_id,
            existing.home_team_id,
            existing.away_team_id,
            _utc(existing.kickoff_at),
        ) != (competition.id, home.id, away.id, _utc(row.kickoff_at)):
            raise FixtureImportError("fixture observation conflicts at the same timestamp")
        event.status = row.status
    session.flush()
    return FixtureImportSummary(
        fixtures_received=len(rows),
        events_created=events_created,
        observations_created=observations_created,
    )


def _apply_pre_kickoff_correction(
    session: Session,
    *,
    event: Event,
    competition: Competition,
    home: Team,
    away: Team,
    row: FixtureImportRow,
) -> None:
    if event.competition_id != competition.id:
        raise FixtureImportError("fixture correction cannot change competition identity")
    if event.status != "scheduled" or row.status != "scheduled":
        raise FixtureImportError("fixture correction requires a scheduled event")
    if _utc(row.observed_at) >= _utc(event.kickoff_at):
        raise FixtureImportError("fixture correction was observed after the stored kickoff")
    has_model_output = session.scalar(
        select(ModelEventOutput.id).where(ModelEventOutput.event_id == event.id).limit(1)
    )
    has_result = session.scalar(
        select(MatchResult.id).where(MatchResult.event_id == event.id).limit(1)
    )
    if has_model_output is not None or has_result is not None:
        raise FixtureImportError("fixture correction conflicts with downstream event evidence")
    event.home_team_id = home.id
    event.away_team_id = away.id
    event.kickoff_at = row.kickoff_at


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
