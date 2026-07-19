from __future__ import annotations

import csv
import io
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db.models import Event, ImportJob, OddsPrice, OddsSnapshot, Provider, RawIngestion
from app.db.session import Base
from app.services.demo_seed import build_demo_odds_csv, seed_demo_data
from app.services.odds_import import OddsImportError, import_odds_csv, parse_odds_csv

AS_OF = datetime(2026, 7, 19, 10, 0, tzinfo=UTC)


@pytest.fixture
def session(tmp_path: Path) -> Iterator[Session]:
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    with Session(engine) as database_session:
        yield database_session


def _without_last_data_row(content: bytes) -> bytes:
    lines = content.decode("utf-8").splitlines()
    return ("\n".join(lines[:-1]) + "\n").encode()


def _change_first_price(content: bytes) -> bytes:
    source = io.StringIO(content.decode("utf-8"), newline="")
    reader = csv.DictReader(source)
    rows = list(reader)
    assert reader.fieldnames is not None
    rows[0]["decimal_odds"] = "9.99"
    target = io.StringIO(newline="")
    writer = csv.DictWriter(target, fieldnames=reader.fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return target.getvalue().encode()


def test_demo_seed_is_labelled_complete_and_idempotent(session: Session) -> None:
    first = seed_demo_data(session, as_of=AS_OF)
    second = seed_demo_data(session, as_of=AS_OF)

    assert first.rows_received == 24
    assert first.rows_imported == 24
    assert first.snapshots_created == 8
    assert second.rows_received == 24
    assert second.rows_imported == 0
    assert second.snapshots_created == 0
    assert session.scalar(select(func.count()).select_from(Event)) == 4
    assert session.scalar(select(func.count()).select_from(OddsSnapshot)) == 8
    assert session.scalar(select(func.count()).select_from(OddsPrice)) == 24
    assert session.scalar(select(func.count()).select_from(RawIngestion)) == 2
    provider = session.scalar(select(Provider).where(Provider.slug == "demo-seed-v1"))
    assert provider is not None
    assert provider.is_demo is True
    assert provider.kind == "demo_seed"
    assert session.scalars(select(OddsSnapshot)).all()[0].source_label == "DEMO DATA"


def test_incomplete_snapshot_rejects_entire_import(session: Session) -> None:
    invalid = _without_last_data_row(build_demo_odds_csv(AS_OF))

    with pytest.raises(OddsImportError) as caught:
        import_odds_csv(
            session,
            filename="incomplete.csv",
            content=invalid,
            now=AS_OF,
        )

    assert any("incomplete" in str(error["message"]) for error in caught.value.errors)
    assert session.scalar(select(func.count()).select_from(Event)) == 0
    assert session.scalar(select(func.count()).select_from(OddsSnapshot)) == 0
    job = session.scalar(select(ImportJob))
    assert job is not None
    assert job.status == "rejected"
    assert job.rows_imported == 0


def test_conflicting_reimport_preserves_original_snapshot(session: Session) -> None:
    original = build_demo_odds_csv(AS_OF)
    import_odds_csv(session, filename="original.csv", content=original, now=AS_OF)

    with pytest.raises(OddsImportError) as caught:
        import_odds_csv(
            session,
            filename="changed.csv",
            content=_change_first_price(original),
            now=AS_OF,
        )

    assert any("different prices" in str(error["message"]) for error in caught.value.errors)
    assert session.scalar(select(func.count()).select_from(OddsSnapshot)) == 8
    assert session.scalar(select(func.count()).select_from(OddsPrice)) == 24
    assert session.scalar(select(func.count()).select_from(ImportJob)) == 2
    rejected = session.scalar(select(ImportJob).where(ImportJob.status == "rejected"))
    assert rejected is not None


def test_live_import_cannot_reuse_demo_bookmaker_identity(session: Session) -> None:
    original = build_demo_odds_csv(AS_OF)
    seed_demo_data(session, as_of=AS_OF)

    with pytest.raises(OddsImportError) as caught:
        import_odds_csv(session, filename="mislabelled.csv", content=original, now=AS_OF)

    assert any("demo classification" in str(error["message"]) for error in caught.value.errors)
    assert session.scalar(select(func.count()).select_from(OddsSnapshot)) == 8


def test_parser_rejects_naive_timestamps() -> None:
    content = build_demo_odds_csv(AS_OF).replace(
        b"2026-07-20T10:00:00+00:00", b"2026-07-20T10:00:00", 1
    )

    with pytest.raises(OddsImportError) as caught:
        parse_odds_csv(content, now=AS_OF)

    assert any("UTC offset" in str(error["message"]) for error in caught.value.errors)


def test_parser_rejects_observations_after_kickoff() -> None:
    content = build_demo_odds_csv(AS_OF).replace(
        b"2026-07-19T10:00:00+00:00", b"2026-07-21T20:00:00+00:00"
    )

    with pytest.raises(OddsImportError) as caught:
        parse_odds_csv(content, now=datetime(2026, 7, 22, tzinfo=UTC))

    assert any("after kickoff" in str(error["message"]) for error in caught.value.errors)


def test_parser_rejects_future_observation() -> None:
    with pytest.raises(OddsImportError) as caught:
        parse_odds_csv(build_demo_odds_csv(AS_OF), now=datetime(2026, 7, 18, tzinfo=UTC))

    assert any("future" in str(error["message"]) for error in caught.value.errors)


def test_parser_rejects_mixed_closing_flags() -> None:
    content = build_demo_odds_csv(AS_OF).replace(b",false\n", b",true\n", 1)

    with pytest.raises(OddsImportError) as caught:
        parse_odds_csv(content, now=AS_OF)

    assert any("mixes closing" in str(error["message"]) for error in caught.value.errors)
