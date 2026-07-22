from __future__ import annotations

import csv
import hashlib
import io
from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Competition,
    Event,
    ImportJob,
    MatchResult,
    Provider,
    RawIngestion,
    Sport,
    Team,
)
from app.schemas.results import ResultImportRow, ResultImportSummary

MAX_RESULTS_CSV_BYTES = 5 * 1024 * 1024
MAX_RESULTS_CSV_ROWS = 20_000
MAX_REPORTED_ERRORS = 100
CSV_COLUMNS = frozenset(ResultImportRow.model_fields)
REQUIRED_COLUMNS = frozenset(CSV_COLUMNS - {"source_updated_at"})


class ResultImportError(ValueError):
    def __init__(self, errors: list[dict[str, object]], job_id: int | None = None) -> None:
        super().__init__("result import rejected")
        if len(errors) > MAX_REPORTED_ERRORS:
            omitted = len(errors) - MAX_REPORTED_ERRORS
            errors = errors[:MAX_REPORTED_ERRORS] + [
                _error(None, "file", f"{omitted} additional errors omitted")
            ]
        self.errors = errors
        self.job_id = job_id


def _error(row: int | None, field: str, message: str) -> dict[str, object]:
    result: dict[str, object] = {"field": field, "message": message}
    if row is not None:
        result["row"] = row
    return result


def parse_results_csv(content: bytes, *, now: datetime | None = None) -> list[ResultImportRow]:
    if not content:
        raise ResultImportError([_error(None, "file", "CSV file is empty")])
    if len(content) > MAX_RESULTS_CSV_BYTES:
        raise ResultImportError([_error(None, "file", "CSV file exceeds the 5 MiB limit")])
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ResultImportError([_error(None, "file", "CSV must be UTF-8 encoded")]) from exc

    reader = csv.DictReader(io.StringIO(text, newline=""))
    if reader.fieldnames is None:
        raise ResultImportError([_error(None, "header", "CSV header is missing")])
    if len(reader.fieldnames) != len(set(reader.fieldnames)):
        raise ResultImportError([_error(None, "header", "CSV header contains duplicate columns")])
    header = frozenset(reader.fieldnames)
    errors: list[dict[str, object]] = []
    missing = sorted(REQUIRED_COLUMNS - header)
    unknown = sorted(header - CSV_COLUMNS)
    if missing:
        errors.append(_error(None, "header", f"missing columns: {', '.join(missing)}"))
    if unknown:
        errors.append(_error(None, "header", f"unknown columns: {', '.join(unknown)}"))
    if errors:
        raise ResultImportError(errors)

    rows: list[ResultImportRow] = []
    identities: dict[str, tuple[object, ...]] = {}
    cutoff = _utc(now or datetime.now(UTC))
    for row_number, raw_row in enumerate(reader, start=2):
        if row_number > MAX_RESULTS_CSV_ROWS + 1:
            errors.append(_error(None, "file", f"CSV exceeds {MAX_RESULTS_CSV_ROWS} data rows"))
            break
        try:
            row = ResultImportRow.model_validate(raw_row)
            if row.observed_at > cutoff:
                errors.append(
                    _error(row_number, "observed_at", "timestamp cannot be in the future")
                )
            identity = (
                row.competition,
                row.country,
                row.season,
                row.kickoff_at,
                row.home_team,
                row.away_team,
            )
            previous = identities.setdefault(row.provider_event_key, identity)
            if previous != identity:
                errors.append(
                    _error(
                        row_number,
                        "provider_event_key",
                        "provider event key has conflicting event identity",
                    )
                )
            rows.append(row)
        except ValidationError as exc:
            for detail in exc.errors(include_url=False, include_context=False):
                location = ".".join(str(part) for part in detail["loc"]) or "row"
                errors.append(_error(row_number, location, str(detail["msg"])))
    if not rows and not errors:
        errors.append(_error(None, "file", "CSV contains no data rows"))
    if errors:
        raise ResultImportError(errors)
    return rows


def serialize_result_rows_csv(rows: list[ResultImportRow]) -> bytes:
    if not rows:
        raise ValueError("cannot serialize an empty result batch")
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream,
        fieldnames=list(ResultImportRow.model_fields),
        lineterminator="\n",
    )
    writer.writeheader()
    for row in rows:
        writer.writerow(row.model_dump(mode="json"))
    return stream.getvalue().encode("utf-8")


def import_results_csv(
    session: Session,
    *,
    filename: str,
    content: bytes,
    provider_slug: str = "user-results-csv",
    provider_name: str = "User results CSV import",
    provider_kind: str = "csv_upload",
    provider_terms_url: str | None = None,
    is_demo: bool = False,
    now: datetime | None = None,
) -> ResultImportSummary:
    ingested_at = _utc(now or datetime.now(UTC))
    try:
        rows = parse_results_csv(content, now=ingested_at)
    except ResultImportError as exc:
        exc.job_id = _record_rejected_job(session, filename, 0, exc.errors)
        raise

    try:
        job = ImportJob(
            filename=filename,
            status="running",
            rows_received=len(rows),
            rows_imported=0,
            errors=[],
        )
        session.add(job)
        session.flush()
        provider = _provider(
            session,
            provider_slug,
            provider_name,
            provider_kind,
            provider_terms_url,
            is_demo,
        )
        session.add(
            RawIngestion(
                provider_id=provider.id,
                import_job_id=job.id,
                source_key=f"results-csv:{filename}:job:{job.id}",
                source_updated_at=max(
                    (row.source_updated_at for row in rows if row.source_updated_at is not None),
                    default=None,
                ),
                observed_at=max(row.observed_at for row in rows),
                ingested_at=ingested_at,
                content_sha256=hashlib.sha256(content).hexdigest(),
                payload=[row.model_dump(mode="json") for row in rows],
                schema_version="football-results-csv-v1",
                status="accepted",
                is_demo=is_demo,
            )
        )
        sport = _one_or_create(session, Sport, {"name": "Football"}, slug="football")
        created = sum(
            _persist_result(
                session,
                row=row,
                provider=provider,
                sport=sport,
                is_demo=is_demo,
            )
            for row in sorted(rows, key=lambda value: value.observed_at)
        )
        job.status = "completed"
        job.rows_imported = created
        session.commit()
        return ResultImportSummary(
            job_id=job.id,
            status=job.status,
            rows_received=job.rows_received,
            rows_imported=job.rows_imported,
            results_created=created,
        )
    except ResultImportError as exc:
        session.rollback()
        exc.job_id = _record_rejected_job(session, filename, len(rows), exc.errors)
        raise
    except Exception:
        session.rollback()
        raise


def _persist_result(
    session: Session,
    *,
    row: ResultImportRow,
    provider: Provider,
    sport: Sport,
    is_demo: bool,
) -> int:
    competition = _one_or_create(
        session,
        Competition,
        {"country": row.country},
        sport_id=sport.id,
        name=row.competition,
        season=row.season,
    )
    if competition.country != row.country:
        raise ResultImportError(
            [_error(None, "country", "competition country conflicts with stored identity")]
        )
    home = _one_or_create(session, Team, {}, sport_id=sport.id, name=row.home_team)
    away = _one_or_create(session, Team, {}, sport_id=sport.id, name=row.away_team)
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
            status="final",
            is_demo=is_demo,
        )
        session.add(event)
        session.flush()
    elif (
        event.competition_id,
        event.home_team_id,
        event.away_team_id,
        _utc(event.kickoff_at),
    ) != (competition.id, home.id, away.id, _utc(row.kickoff_at)):
        raise ResultImportError(
            [_error(None, "provider_event_key", "event conflicts with stored identity")]
        )

    same_observation = session.scalar(
        select(MatchResult).where(
            MatchResult.event_id == event.id,
            MatchResult.provider_id == provider.id,
            MatchResult.observed_at == row.observed_at,
        )
    )
    if same_observation is not None:
        if (same_observation.home_goals, same_observation.away_goals) != (
            row.home_goals,
            row.away_goals,
        ):
            raise ResultImportError(
                [_error(None, "result", "same result observation has different score")]
            )
        return 0

    latest = session.scalar(
        select(MatchResult)
        .where(
            MatchResult.event_id == event.id,
            MatchResult.provider_id == provider.id,
        )
        .order_by(MatchResult.observed_at.desc())
        .limit(1)
    )
    if latest is not None and _utc(latest.observed_at) > _utc(row.observed_at):
        raise ResultImportError(
            [_error(None, "observed_at", "result observation predates the latest stored result")]
        )
    if latest is not None and (latest.home_goals, latest.away_goals) == (
        row.home_goals,
        row.away_goals,
    ):
        return 0

    session.add(
        MatchResult(
            event_id=event.id,
            provider_id=provider.id,
            home_goals=row.home_goals,
            away_goals=row.away_goals,
            status="final",
            is_final=True,
            source_updated_at=row.source_updated_at,
            observed_at=row.observed_at,
            settled_at=row.settled_at,
            supersedes_id=latest.id if latest is not None else None,
        )
    )
    event.status = "final"
    return 1


def _record_rejected_job(
    session: Session,
    filename: str,
    rows_received: int,
    errors: list[dict[str, object]],
) -> int:
    job = ImportJob(
        filename=filename,
        status="rejected",
        rows_received=rows_received,
        rows_imported=0,
        errors=errors,
    )
    session.add(job)
    session.commit()
    return job.id


def _provider(
    session: Session,
    slug: str,
    name: str,
    kind: str,
    terms_url: str | None,
    is_demo: bool,
) -> Provider:
    provider = _one_or_create(
        session,
        Provider,
        {
            "name": name,
            "kind": "demo_seed" if is_demo else kind,
            "is_demo": is_demo,
            "terms_url": terms_url,
            "capabilities": {"football_results": True},
        },
        slug=slug,
    )
    if provider.is_demo != is_demo:
        raise ResultImportError(
            [_error(None, "provider", "provider demo classification conflicts")]
        )
    expected_kind = "demo_seed" if is_demo else kind
    if provider.kind != expected_kind or provider.terms_url != terms_url:
        raise ResultImportError(
            [_error(None, "provider", "provider provenance conflicts with stored metadata")]
        )
    return provider


def _one_or_create[ModelT](
    session: Session,
    model: type[ModelT],
    defaults: dict[str, object],
    **identity: object,
) -> ModelT:
    instance = session.scalar(select(model).filter_by(**identity))
    if instance is None:
        instance = model(**identity, **defaults)
        session.add(instance)
        session.flush()
    return instance


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
