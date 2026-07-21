from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AvailabilityReport,
    Coach,
    CoachTenure,
    Competition,
    Event,
    ImportJob,
    LineupMember,
    LineupSnapshot,
    Player,
    PlayerAppearance,
    PlayerRegistration,
    PlayerStatistic,
    Provider,
    RawIngestion,
    Sport,
    TacticalSnapshot,
    Team,
)
from app.schemas.intelligence import (
    AvailabilityInput,
    IntelligenceImportRequest,
    IntelligenceImportSummary,
    PublishedEvidence,
)

MAX_INTELLIGENCE_CSV_BYTES = 5 * 1024 * 1024
MAX_INTELLIGENCE_CSV_ROWS = 20_000
_AVAILABILITY_COLUMNS = frozenset(AvailabilityInput.model_fields)


class IntelligenceImportError(ValueError):
    def __init__(self, errors: list[dict[str, object]], job_id: int | None = None) -> None:
        super().__init__("football intelligence import rejected")
        self.errors = errors[:100]
        self.job_id = job_id


def _error(field: str, message: str, row: int | None = None) -> dict[str, object]:
    value: dict[str, object] = {"field": field, "message": message}
    if row is not None:
        value["row"] = row
    return value


def parse_availability_csv(content: bytes) -> list[AvailabilityInput]:
    if not content:
        raise IntelligenceImportError([_error("file", "CSV file is empty")])
    if len(content) > MAX_INTELLIGENCE_CSV_BYTES:
        raise IntelligenceImportError([_error("file", "CSV file exceeds the 5 MiB limit")])
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise IntelligenceImportError([_error("file", "CSV must be UTF-8 encoded")]) from exc
    reader = csv.DictReader(io.StringIO(text, newline=""))
    if reader.fieldnames is None:
        raise IntelligenceImportError([_error("header", "CSV header is missing")])
    header = frozenset(reader.fieldnames)
    missing = sorted(_AVAILABILITY_COLUMNS - header)
    unknown = sorted(header - _AVAILABILITY_COLUMNS)
    errors: list[dict[str, object]] = []
    if missing:
        errors.append(_error("header", f"missing columns: {', '.join(missing)}"))
    if unknown:
        errors.append(_error("header", f"unknown columns: {', '.join(unknown)}"))
    rows: list[AvailabilityInput] = []
    if not errors:
        for number, raw in enumerate(reader, start=2):
            if number > MAX_INTELLIGENCE_CSV_ROWS + 1:
                errors.append(_error("file", "CSV row limit exceeded"))
                break
            normalized = {key: (None if value == "" else value) for key, value in raw.items()}
            try:
                rows.append(AvailabilityInput.model_validate(normalized))
            except ValidationError as exc:
                for detail in exc.errors(include_url=False, include_context=False):
                    field = ".".join(str(part) for part in detail["loc"])
                    errors.append(_error(field or "row", str(detail["msg"]), number))
    if not rows and not errors:
        errors.append(_error("file", "CSV contains no data rows"))
    if errors:
        raise IntelligenceImportError(errors)
    return rows


def import_availability_csv(
    session: Session,
    *,
    filename: str,
    content: bytes,
    source_key: str,
    provider_slug: str,
    provider_name: str,
    now: datetime | None = None,
) -> IntelligenceImportSummary:
    try:
        availability = parse_availability_csv(content)
    except IntelligenceImportError as exc:
        exc.job_id = _rejected_job(session, filename, 0, exc.errors)
        raise
    player_keys = sorted({row.provider_player_key for row in availability})
    provider = session.scalar(select(Provider).where(Provider.slug == provider_slug))
    if provider is None:
        error = [_error("provider_slug", "provider must exist before availability CSV import")]
        raise IntelligenceImportError(
            error, _rejected_job(session, filename, len(availability), error)
        )
    stored = {
        player.provider_player_key: player
        for player in session.scalars(
            select(Player).where(
                Player.provider_id == provider.id,
                Player.provider_player_key.in_(player_keys),
            )
        ).all()
    }
    missing = sorted(set(player_keys) - set(stored))
    if missing:
        error = [_error("provider_player_key", f"unknown player identities: {', '.join(missing)}")]
        raise IntelligenceImportError(
            error, _rejected_job(session, filename, len(availability), error)
        )
    request = IntelligenceImportRequest(
        source_key=source_key,
        provider_slug=provider_slug,
        provider_name=provider_name,
        is_demo=provider.is_demo,
        availability=availability,
    )
    return import_intelligence_bundle(session, request, filename=filename, now=now)


def import_intelligence_bundle(
    session: Session,
    request: IntelligenceImportRequest,
    *,
    filename: str = "intelligence.json",
    now: datetime | None = None,
) -> IntelligenceImportSummary:
    ingested_at = _utc(now or datetime.now(UTC))
    payload = request.model_dump(mode="json")
    content_sha256 = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    rows_received = _row_count(request)
    try:
        provider = _provider(session, request)
        existing = session.scalar(
            select(RawIngestion).where(
                RawIngestion.provider_id == provider.id,
                RawIngestion.source_key == request.source_key,
                RawIngestion.content_sha256 == content_sha256,
            )
        )
        if existing is not None and existing.import_job_id is not None:
            job = session.get_one(ImportJob, existing.import_job_id)
            return IntelligenceImportSummary(
                job_id=job.id,
                status=job.status,
                rows_received=job.rows_received,
                rows_imported=job.rows_imported,
                created={},
                content_sha256=content_sha256,
            )
        evidence = _evidence(request)
        future = [item for item in evidence if _utc(item.observed_at) > ingested_at]
        if future:
            raise IntelligenceImportError(
                [_error("observed_at", "evidence timestamp cannot be in the future")]
            )
        job = ImportJob(
            filename=filename,
            status="running",
            rows_received=rows_received,
            rows_imported=0,
            errors=[],
        )
        session.add(job)
        session.flush()
        sport = session.scalar(select(Sport).where(Sport.slug == "football"))
        if sport is None:
            sport = Sport(slug="football", name="Football")
            session.add(sport)
            session.flush()
        created: dict[str, int] = {}
        players = _persist_players(session, request, provider, sport, created)
        coaches = _persist_coaches(session, request, provider, sport, created)
        _persist_relational(session, request, provider, players, coaches, created)
        rows_imported = sum(created.values())
        observed_at = max((_utc(item.observed_at) for item in evidence), default=ingested_at)
        published_at = max((_utc(item.published_at) for item in evidence), default=None)
        session.add(
            RawIngestion(
                provider_id=provider.id,
                import_job_id=job.id,
                source_key=request.source_key,
                source_updated_at=published_at,
                observed_at=observed_at,
                ingested_at=ingested_at,
                content_sha256=content_sha256,
                payload=payload,
                schema_version="football-intelligence-bundle-v1",
                status="accepted",
                is_demo=request.is_demo,
            )
        )
        job.status = "completed"
        job.rows_imported = rows_imported
        session.commit()
        return IntelligenceImportSummary(
            job_id=job.id,
            status=job.status,
            rows_received=rows_received,
            rows_imported=rows_imported,
            created=created,
            content_sha256=content_sha256,
        )
    except IntelligenceImportError as exc:
        session.rollback()
        exc.job_id = _rejected_job(session, filename, rows_received, exc.errors)
        raise
    except Exception:
        session.rollback()
        raise


def _persist_players(
    session: Session,
    request: IntelligenceImportRequest,
    provider: Provider,
    sport: Sport,
    created: dict[str, int],
) -> dict[str, Player]:
    players = {
        player.provider_player_key: player
        for player in session.scalars(select(Player).where(Player.provider_id == provider.id)).all()
    }
    for value in request.players:
        stored = players.get(value.provider_player_key)
        identity = (value.name, value.position, value.preferred_side, value.birth_year)
        if (
            stored is not None
            and (
                stored.name,
                stored.position,
                stored.preferred_side,
                stored.birth_year,
            )
            != identity
        ):
            raise IntelligenceImportError(
                [
                    _error(
                        "provider_player_key",
                        f"conflicting player identity: {value.provider_player_key}",
                    )
                ]
            )
        if stored is None:
            stored = Player(
                sport_id=sport.id,
                provider_id=provider.id,
                provider_player_key=value.provider_player_key,
                name=value.name,
                position=value.position,
                preferred_side=value.preferred_side,
                birth_year=value.birth_year,
                is_demo=request.is_demo,
            )
            session.add(stored)
            session.flush()
            players[value.provider_player_key] = stored
            created["players"] = created.get("players", 0) + 1
    return players


def _persist_coaches(
    session: Session,
    request: IntelligenceImportRequest,
    provider: Provider,
    sport: Sport,
    created: dict[str, int],
) -> dict[str, Coach]:
    coaches = {
        coach.provider_coach_key: coach
        for coach in session.scalars(select(Coach).where(Coach.provider_id == provider.id)).all()
    }
    for value in request.coaches:
        stored = coaches.get(value.provider_coach_key)
        if stored is not None and stored.name != value.name:
            raise IntelligenceImportError(
                [
                    _error(
                        "provider_coach_key",
                        f"conflicting coach identity: {value.provider_coach_key}",
                    )
                ]
            )
        if stored is None:
            stored = Coach(
                sport_id=sport.id,
                provider_id=provider.id,
                provider_coach_key=value.provider_coach_key,
                name=value.name,
                is_demo=request.is_demo,
            )
            session.add(stored)
            session.flush()
            coaches[value.provider_coach_key] = stored
            created["coaches"] = created.get("coaches", 0) + 1
    return coaches


def _persist_relational(
    session: Session,
    request: IntelligenceImportRequest,
    provider: Provider,
    players: dict[str, Player],
    coaches: dict[str, Coach],
    created: dict[str, int],
) -> None:
    def player(key: str) -> Player:
        if key not in players:
            raise IntelligenceImportError([_error("provider_player_key", f"unknown player: {key}")])
        return players[key]

    def coach(key: str | None) -> Coach | None:
        if key is None:
            return None
        if key not in coaches:
            raise IntelligenceImportError([_error("provider_coach_key", f"unknown coach: {key}")])
        return coaches[key]

    for registration in request.registrations:
        _team(session, registration.team_id)
        if (
            registration.competition_id is not None
            and session.get(Competition, registration.competition_id) is None
        ):
            raise IntelligenceImportError([_error("competition_id", "competition not found")])
        session.add(
            PlayerRegistration(
                player_id=player(registration.provider_player_key).id,
                team_id=registration.team_id,
                competition_id=registration.competition_id,
                valid_from=registration.valid_from,
                valid_to=registration.valid_to,
                squad_number=registration.squad_number,
                source_updated_at=registration.published_at,
                observed_at=registration.observed_at,
            )
        )
        _inc(created, "registrations")
    for tenure in request.coach_tenures:
        _team(session, tenure.team_id)
        stored_coach = coach(tenure.provider_coach_key)
        assert stored_coach is not None
        session.add(
            CoachTenure(
                coach_id=stored_coach.id,
                team_id=tenure.team_id,
                valid_from=tenure.valid_from,
                valid_to=tenure.valid_to,
                source_updated_at=tenure.published_at,
                observed_at=tenure.observed_at,
            )
        )
        _inc(created, "coach_tenures")
    for appearance in request.appearances:
        _event_team(session, appearance.event_id, appearance.team_id)
        session.add(
            PlayerAppearance(
                event_id=appearance.event_id,
                player_id=player(appearance.provider_player_key).id,
                team_id=appearance.team_id,
                provider_id=provider.id,
                starter=appearance.starter,
                minutes=appearance.minutes,
                position=appearance.position,
                role=appearance.role,
                source_updated_at=appearance.published_at,
                observed_at=appearance.observed_at,
            )
        )
        _inc(created, "appearances")
    for statistic in request.player_statistics:
        _event_team(session, statistic.event_id, statistic.team_id)
        session.add(
            PlayerStatistic(
                event_id=statistic.event_id,
                player_id=player(statistic.provider_player_key).id,
                team_id=statistic.team_id,
                provider_id=provider.id,
                metric_schema_version=statistic.metric_schema_version,
                minutes=statistic.minutes,
                metrics=statistic.metrics,
                source_updated_at=statistic.published_at,
                observed_at=statistic.observed_at,
            )
        )
        _inc(created, "player_statistics")
    for availability in sorted(request.availability, key=lambda item: item.observed_at):
        _team(session, availability.team_id)
        if availability.event_id is not None:
            _event_team(session, availability.event_id, availability.team_id)
        stored_player = player(availability.provider_player_key)
        latest = session.scalar(
            select(AvailabilityReport)
            .where(
                AvailabilityReport.player_id == stored_player.id,
                AvailabilityReport.team_id == availability.team_id,
                AvailabilityReport.event_id == availability.event_id,
                AvailabilityReport.provider_id == provider.id,
            )
            .order_by(AvailabilityReport.observed_at.desc())
            .limit(1)
        )
        session.add(
            AvailabilityReport(
                player_id=stored_player.id,
                team_id=availability.team_id,
                event_id=availability.event_id,
                provider_id=provider.id,
                status=availability.status,
                reason=availability.reason,
                evidence_class=availability.evidence_class,
                confidence=availability.confidence,
                source_updated_at=availability.published_at,
                observed_at=availability.observed_at,
                effective_from=availability.effective_from,
                effective_to=availability.effective_to,
                supersedes_id=latest.id if latest else None,
            )
        )
        _inc(created, "availability")
    for lineup_value in request.lineups:
        _event_team(session, lineup_value.event_id, lineup_value.team_id)
        stored_coach = coach(lineup_value.provider_coach_key)
        lineup = LineupSnapshot(
            event_id=lineup_value.event_id,
            team_id=lineup_value.team_id,
            coach_id=stored_coach.id if stored_coach else None,
            provider_id=provider.id,
            lineup_type=lineup_value.lineup_type,
            formation=lineup_value.formation,
            source_updated_at=lineup_value.published_at,
            observed_at=lineup_value.observed_at,
            confidence=lineup_value.confidence,
        )
        session.add(lineup)
        session.flush()
        for member in lineup_value.members:
            session.add(
                LineupMember(
                    lineup_snapshot_id=lineup.id,
                    player_id=player(member.provider_player_key).id,
                    starter=member.starter,
                    position=member.position,
                    role=member.role,
                    expected_probability=member.expected_probability,
                )
            )
        _inc(created, "lineups")
        created["lineup_members"] = created.get("lineup_members", 0) + len(lineup_value.members)
    for tactic in request.tactics:
        _team(session, tactic.team_id)
        if tactic.event_id is not None:
            _event_team(session, tactic.event_id, tactic.team_id)
        stored_coach = coach(tactic.provider_coach_key)
        session.add(
            TacticalSnapshot(
                event_id=tactic.event_id,
                team_id=tactic.team_id,
                coach_id=stored_coach.id if stored_coach else None,
                provider_id=provider.id,
                formation=tactic.formation,
                metrics=tactic.metrics,
                labels=tactic.labels,
                source_updated_at=tactic.published_at,
                observed_at=tactic.observed_at,
                as_of=tactic.as_of,
            )
        )
        _inc(created, "tactics")


def _provider(session: Session, request: IntelligenceImportRequest) -> Provider:
    provider = session.scalar(select(Provider).where(Provider.slug == request.provider_slug))
    if provider is None:
        provider = Provider(
            slug=request.provider_slug,
            name=request.provider_name,
            kind="user_intelligence",
            is_demo=request.is_demo,
            terms_url=None,
            capabilities={"football_intelligence": True},
        )
        session.add(provider)
        session.flush()
    elif provider.name != request.provider_name or provider.is_demo != request.is_demo:
        raise IntelligenceImportError(
            [_error("provider_slug", "provider identity conflicts with stored provider")]
        )
    return provider


def _team(session: Session, team_id: int) -> Team:
    team = session.get(Team, team_id)
    if team is None:
        raise IntelligenceImportError([_error("team_id", f"team not found: {team_id}")])
    return team


def _event_team(session: Session, event_id: int, team_id: int) -> Event:
    event = session.get(Event, event_id)
    if event is None:
        raise IntelligenceImportError([_error("event_id", f"event not found: {event_id}")])
    if team_id not in (event.home_team_id, event.away_team_id):
        raise IntelligenceImportError([_error("team_id", "team does not participate in event")])
    return event


def _evidence(request: IntelligenceImportRequest) -> list[PublishedEvidence]:
    return [
        *request.registrations,
        *request.coach_tenures,
        *request.appearances,
        *request.player_statistics,
        *request.availability,
        *request.lineups,
        *request.tactics,
    ]


def _row_count(request: IntelligenceImportRequest) -> int:
    return (
        len(request.players)
        + len(request.coaches)
        + len(_evidence(request))
        + sum(len(lineup.members) for lineup in request.lineups)
    )


def _inc(created: dict[str, int], key: str) -> None:
    created[key] = created.get(key, 0) + 1


def _rejected_job(
    session: Session, filename: str, rows: int, errors: list[dict[str, object]]
) -> int:
    job = ImportJob(
        filename=filename,
        status="rejected",
        rows_received=rows,
        rows_imported=0,
        errors=errors[:100],
    )
    session.add(job)
    session.commit()
    return job.id


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
