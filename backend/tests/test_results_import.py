from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db.models import Event, ImportJob, MatchResult, Provider, RawIngestion
from app.db.session import Base
from app.schemas.results import ResultImportRow
from app.services.demo_seed import build_demo_results_csv
from app.services.results_import import (
    ResultImportError,
    import_results_csv,
    parse_results_csv,
    serialize_result_rows_csv,
)

AS_OF = datetime(2026, 7, 19, 10, 0, tzinfo=UTC)


@pytest.fixture
def session(tmp_path: Path) -> Iterator[Session]:
    engine = create_engine(f"sqlite:///{tmp_path}/results.db")
    Base.metadata.create_all(engine)
    with Session(engine) as database_session:
        yield database_session


def test_demo_results_are_labelled_atomic_and_idempotent(session: Session) -> None:
    content = build_demo_results_csv(AS_OF)
    first = import_results_csv(
        session,
        filename="DEMO_results.csv",
        content=content,
        provider_slug="demo-results-v1",
        provider_name="Synthetic results",
        is_demo=True,
        now=AS_OF,
    )
    second = import_results_csv(
        session,
        filename="DEMO_results.csv",
        content=content,
        provider_slug="demo-results-v1",
        provider_name="Synthetic results",
        is_demo=True,
        now=AS_OF,
    )

    assert first.results_created == 32
    assert second.results_created == 0
    assert session.scalar(select(func.count()).select_from(Event)) == 32
    assert session.scalar(select(func.count()).select_from(MatchResult)) == 32
    assert session.scalar(select(func.count()).select_from(RawIngestion)) == 2
    provider = session.scalar(select(Provider).where(Provider.slug == "demo-results-v1"))
    assert provider is not None and provider.is_demo is True


def test_future_result_observation_rejects_entire_file(session: Session) -> None:
    with pytest.raises(ResultImportError) as caught:
        import_results_csv(
            session,
            filename="future.csv",
            content=build_demo_results_csv(AS_OF),
            now=AS_OF - timedelta(days=120),
        )

    assert any("future" in str(error["message"]) for error in caught.value.errors)
    assert session.scalar(select(func.count()).select_from(Event)) == 0
    job = session.scalar(select(ImportJob))
    assert job is not None and job.status == "rejected"


def test_later_correction_supersedes_previous_result(session: Session) -> None:
    original_row = parse_results_csv(build_demo_results_csv(AS_OF), now=AS_OF)[0]
    import_results_csv(
        session,
        filename="original.csv",
        content=serialize_result_rows_csv([original_row]),
        now=AS_OF,
    )
    correction = ResultImportRow(
        **{
            **original_row.model_dump(),
            "home_goals": original_row.home_goals + 1,
            "observed_at": AS_OF - timedelta(hours=1),
            "source_updated_at": AS_OF - timedelta(hours=1),
        }
    )
    imported = import_results_csv(
        session,
        filename="correction.csv",
        content=serialize_result_rows_csv([correction]),
        now=AS_OF,
    )

    results = session.scalars(select(MatchResult).order_by(MatchResult.observed_at)).all()
    assert imported.results_created == 1
    assert len(results) == 2
    assert results[1].supersedes_id == results[0].id
    assert results[1].home_goals == results[0].home_goals + 1


def test_out_of_order_correction_is_rejected(session: Session) -> None:
    original_row = parse_results_csv(build_demo_results_csv(AS_OF), now=AS_OF)[0]
    later = ResultImportRow(
        **{
            **original_row.model_dump(),
            "home_goals": original_row.home_goals + 1,
            "observed_at": AS_OF - timedelta(hours=1),
            "source_updated_at": AS_OF - timedelta(hours=1),
        }
    )
    import_results_csv(
        session,
        filename="later.csv",
        content=serialize_result_rows_csv([later]),
        now=AS_OF,
    )

    with pytest.raises(ResultImportError) as caught:
        import_results_csv(
            session,
            filename="older.csv",
            content=serialize_result_rows_csv([original_row]),
            now=AS_OF,
        )

    assert any("predates" in str(error["message"]) for error in caught.value.errors)
    assert session.scalar(select(func.count()).select_from(MatchResult)) == 1
