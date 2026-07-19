from __future__ import annotations

import csv
import hashlib
import io
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Bookmaker,
    Competition,
    Event,
    ImportJob,
    Market,
    OddsPrice,
    OddsSnapshot,
    Provider,
    RawIngestion,
    Selection,
    Sport,
    Team,
)
from app.db.session import Base
from app.schemas.odds import EXPECTED_SELECTIONS, ImportSummary, OddsImportRow

MAX_CSV_BYTES = 5 * 1024 * 1024
MAX_CSV_ROWS = 20_000
MAX_REPORTED_ERRORS = 100
CSV_COLUMNS = frozenset(OddsImportRow.model_fields)
REQUIRED_CSV_COLUMNS = frozenset(
    {
        "provider_event_key",
        "competition",
        "country",
        "season",
        "kickoff_at",
        "home_team",
        "away_team",
        "bookmaker",
        "market_type",
        "selection_code",
        "selection_name",
        "decimal_odds",
        "observed_at",
    }
)


class OddsImportError(ValueError):
    def __init__(self, errors: list[dict[str, object]], job_id: int | None = None) -> None:
        super().__init__("odds import rejected")
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


def parse_odds_csv(content: bytes, *, now: datetime | None = None) -> list[OddsImportRow]:
    if not content:
        raise OddsImportError([_error(None, "file", "CSV file is empty")])
    if len(content) > MAX_CSV_BYTES:
        raise OddsImportError([_error(None, "file", "CSV file exceeds the 5 MiB limit")])
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise OddsImportError([_error(None, "file", "CSV must be UTF-8 encoded")]) from exc

    reader = csv.DictReader(io.StringIO(text, newline=""))
    if reader.fieldnames is None:
        raise OddsImportError([_error(None, "header", "CSV header is missing")])
    if len(reader.fieldnames) != len(set(reader.fieldnames)):
        raise OddsImportError([_error(None, "header", "CSV header contains duplicate columns")])
    header = frozenset(reader.fieldnames)
    errors: list[dict[str, object]] = []
    missing = sorted(REQUIRED_CSV_COLUMNS - header)
    unknown = sorted(header - CSV_COLUMNS)
    if missing:
        errors.append(_error(None, "header", f"missing columns: {', '.join(missing)}"))
    if unknown:
        errors.append(_error(None, "header", f"unknown columns: {', '.join(unknown)}"))
    if errors:
        raise OddsImportError(errors)

    rows: list[OddsImportRow] = []
    cutoff = now or datetime.now(UTC)
    for row_number, raw_row in enumerate(reader, start=2):
        if row_number > MAX_CSV_ROWS + 1:
            errors.append(_error(None, "file", f"CSV exceeds {MAX_CSV_ROWS} data rows"))
            break
        try:
            row = OddsImportRow.model_validate(raw_row)
            if row.observed_at > cutoff:
                errors.append(
                    _error(row_number, "observed_at", "timestamp cannot be in the future")
                )
            rows.append(row)
        except ValidationError as exc:
            for detail in exc.errors(include_url=False, include_context=False):
                location = ".".join(str(part) for part in detail["loc"]) or "row"
                errors.append(_error(row_number, location, str(detail["msg"])))
    if not rows and not errors:
        errors.append(_error(None, "file", "CSV contains no data rows"))
    errors.extend(_validate_coherent_snapshots(rows))
    if errors:
        raise OddsImportError(errors)
    return rows


def _validate_coherent_snapshots(rows: list[OddsImportRow]) -> list[dict[str, object]]:
    errors: list[dict[str, object]] = []
    event_identity: dict[str, tuple[object, ...]] = {}
    groups: dict[tuple[object, ...], list[OddsImportRow]] = defaultdict(list)
    for row in rows:
        identity = (
            row.competition,
            row.country,
            row.season,
            row.kickoff_at,
            row.home_team,
            row.away_team,
        )
        previous = event_identity.setdefault(row.provider_event_key, identity)
        if previous != identity:
            errors.append(
                _error(
                    None,
                    "provider_event_key",
                    f"conflicting event identity for {row.provider_event_key!r}",
                )
            )
        key = (
            row.provider_event_key,
            row.bookmaker.casefold(),
            row.market_type,
            row.line_key,
            row.period,
            row.currency,
            row.settlement_rule_key,
            row.observed_at,
        )
        groups[key].append(row)

    for group_rows in groups.values():
        first = group_rows[0]
        codes = [row.selection_code for row in group_rows]
        if len({row.is_closing for row in group_rows}) != 1:
            errors.append(
                _error(None, "is_closing", "a snapshot mixes closing and non-closing prices")
            )
        if len(codes) != len(set(codes)):
            errors.append(
                _error(None, "selection_code", "a snapshot contains duplicate selection codes")
            )
            continue
        expected = EXPECTED_SELECTIONS[first.market_type]
        if frozenset(codes) != expected:
            missing = sorted(expected - frozenset(codes))
            extra = sorted(frozenset(codes) - expected)
            details = []
            if missing:
                details.append(f"missing {', '.join(missing)}")
            if extra:
                details.append(f"unexpected {', '.join(extra)}")
            errors.append(
                _error(
                    None,
                    "snapshot",
                    f"incomplete {first.market_type} snapshot for {first.bookmaker}: "
                    + "; ".join(details),
                )
            )
    return errors


def import_odds_csv(
    session: Session,
    *,
    filename: str,
    content: bytes,
    provider_slug: str = "user-csv",
    provider_name: str = "User CSV import",
    is_demo: bool = False,
    now: datetime | None = None,
) -> ImportSummary:
    ingested_at = now or datetime.now(UTC)
    try:
        rows = parse_odds_csv(content, now=ingested_at)
    except OddsImportError as exc:
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
        provider = _provider(session, provider_slug, provider_name, is_demo)
        raw = RawIngestion(
            provider_id=provider.id,
            import_job_id=job.id,
            source_key=f"csv:{filename}:job:{job.id}",
            source_updated_at=max(
                (row.source_updated_at for row in rows if row.source_updated_at is not None),
                default=None,
            ),
            observed_at=max(row.observed_at for row in rows),
            ingested_at=ingested_at,
            content_sha256=hashlib.sha256(content).hexdigest(),
            payload=[row.model_dump(mode="json") for row in rows],
            schema_version="odds-csv-v1",
            status="accepted",
            is_demo=is_demo,
        )
        session.add(raw)

        sport = _one_or_create(session, Sport, slug="football", defaults={"name": "Football"})
        snapshots_created = 0
        rows_imported = 0
        for grouped_rows in _group_rows(rows).values():
            created, imported = _persist_snapshot(
                session,
                provider=provider,
                sport=sport,
                job=job,
                rows=grouped_rows,
                ingested_at=ingested_at,
                is_demo=is_demo,
            )
            snapshots_created += int(created)
            rows_imported += imported

        job.status = "completed"
        job.rows_imported = rows_imported
        session.commit()
        return ImportSummary(
            job_id=job.id,
            status=job.status,
            rows_received=job.rows_received,
            rows_imported=job.rows_imported,
            snapshots_created=snapshots_created,
        )
    except OddsImportError as exc:
        session.rollback()
        exc.job_id = _record_rejected_job(session, filename, len(rows), exc.errors)
        raise
    except Exception:
        session.rollback()
        raise


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


def _group_rows(rows: list[OddsImportRow]) -> dict[tuple[object, ...], list[OddsImportRow]]:
    groups: dict[tuple[object, ...], list[OddsImportRow]] = defaultdict(list)
    for row in rows:
        groups[
            (
                row.provider_event_key,
                row.bookmaker.casefold(),
                row.market_type,
                row.line_key,
                row.period,
                row.currency,
                row.settlement_rule_key,
                row.observed_at,
            )
        ].append(row)
    return groups


def _persist_snapshot(
    session: Session,
    *,
    provider: Provider,
    sport: Sport,
    job: ImportJob,
    rows: list[OddsImportRow],
    ingested_at: datetime,
    is_demo: bool,
) -> tuple[bool, int]:
    first = rows[0]
    competition = _one_or_create(
        session,
        Competition,
        sport_id=sport.id,
        name=first.competition,
        season=first.season,
        defaults={"country": first.country},
    )
    if competition.country != first.country:
        raise OddsImportError(
            [_error(None, "country", "competition country conflicts with stored identity")]
        )
    home = _team(session, sport.id, first.home_team)
    away = _team(session, sport.id, first.away_team)
    event = session.scalar(
        select(Event).where(
            Event.provider_id == provider.id,
            Event.provider_event_key == first.provider_event_key,
        )
    )
    if event is None:
        event = Event(
            competition_id=competition.id,
            home_team_id=home.id,
            away_team_id=away.id,
            provider_id=provider.id,
            provider_event_key=first.provider_event_key,
            kickoff_at=first.kickoff_at,
            status="scheduled",
            is_demo=is_demo,
        )
        session.add(event)
        session.flush()
    elif (
        event.competition_id,
        event.home_team_id,
        event.away_team_id,
        _aware_utc(event.kickoff_at),
    ) != (competition.id, home.id, away.id, first.kickoff_at):
        raise OddsImportError(
            [_error(None, "provider_event_key", "event conflicts with stored identity")]
        )

    bookmaker_slug = _slug(first.bookmaker)
    bookmaker = _one_or_create(
        session,
        Bookmaker,
        slug=bookmaker_slug,
        defaults={"name": first.bookmaker, "is_demo": is_demo},
    )
    market = _one_or_create(
        session,
        Market,
        event_id=event.id,
        market_type=str(first.market_type),
        line_key=first.line_key,
        period=first.period,
        currency=first.currency,
        settlement_rule_key=first.settlement_rule_key,
        defaults={"line": first.line},
    )
    snapshot = session.scalar(
        select(OddsSnapshot).where(
            OddsSnapshot.market_id == market.id,
            OddsSnapshot.bookmaker_id == bookmaker.id,
            OddsSnapshot.provider_id == provider.id,
            OddsSnapshot.observed_at == first.observed_at,
        )
    )
    if snapshot is not None:
        _verify_existing_prices(session, snapshot, market, rows)
        return False, 0

    snapshot = OddsSnapshot(
        market_id=market.id,
        bookmaker_id=bookmaker.id,
        provider_id=provider.id,
        import_job_id=job.id,
        source_updated_at=max(
            (row.source_updated_at for row in rows if row.source_updated_at is not None),
            default=None,
        ),
        observed_at=first.observed_at,
        ingested_at=ingested_at,
        is_closing=all(row.is_closing for row in rows),
        is_complete=True,
        source_label="DEMO DATA" if is_demo else "USER CSV",
    )
    session.add(snapshot)
    session.flush()
    for row in rows:
        selection = _one_or_create(
            session,
            Selection,
            market_id=market.id,
            code=row.selection_code,
            defaults={"name": row.selection_name},
        )
        session.add(
            OddsPrice(
                snapshot_id=snapshot.id,
                selection_id=selection.id,
                decimal_odds=row.decimal_odds,
            )
        )
    return True, len(rows)


def _verify_existing_prices(
    session: Session,
    snapshot: OddsSnapshot,
    market: Market,
    rows: list[OddsImportRow],
) -> None:
    stored = {
        code: Decimal(price)
        for code, price in session.execute(
            select(Selection.code, OddsPrice.decimal_odds)
            .join(OddsPrice, OddsPrice.selection_id == Selection.id)
            .where(
                Selection.market_id == market.id,
                OddsPrice.snapshot_id == snapshot.id,
            )
        ).all()
    }
    incoming = {row.selection_code: row.decimal_odds for row in rows}
    if stored != incoming:
        raise OddsImportError(
            [_error(None, "snapshot", "same snapshot identity already has different prices")]
        )


def _provider(session: Session, slug: str, name: str, is_demo: bool) -> Provider:
    provider = _one_or_create(
        session,
        Provider,
        slug=slug,
        defaults={
            "name": name,
            "kind": "demo_seed" if is_demo else "csv_upload",
            "is_demo": is_demo,
            "terms_url": None,
            "capabilities": {"odds": True, "football": True},
        },
    )
    if provider.is_demo != is_demo:
        raise OddsImportError([_error(None, "provider", "provider demo classification conflicts")])
    return provider


def _team(session: Session, sport_id: int, name: str) -> Team:
    return _one_or_create(session, Team, sport_id=sport_id, name=name, defaults={})


def _one_or_create[ModelT: Base](
    session: Session,
    model: type[ModelT],
    /,
    defaults: dict[str, object],
    **identity: object,
) -> ModelT:
    instance = session.scalar(select(model).filter_by(**identity))
    if instance is None:
        instance = model(**identity, **defaults)
        session.add(instance)
        session.flush()
    return instance


def _aware_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _slug(value: str) -> str:
    slug = "-".join(
        "".join(character.lower() if character.isalnum() else " " for character in value).split()
    )
    if not slug:
        raise OddsImportError([_error(None, "bookmaker", "bookmaker cannot produce an empty slug")])
    return slug[:60]
