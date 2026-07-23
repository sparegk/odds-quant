from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.models import Provider
from app.db.session import Base
from app.providers.openfootball import (
    OPENFOOTBALL_LICENSE_URL,
    OpenFootballImportError,
    normalize_openfootball_results,
)
from app.services.results_import import import_results_csv, serialize_result_rows_csv

PUBLISHED_AT = datetime(2025, 6, 1, 5, 26, 17, tzinfo=UTC)
COMMIT = "6a225eabc8be1f7e354faa55befe790fea93332d"


@pytest.fixture
def session(tmp_path: Path) -> Iterator[Session]:
    engine = create_engine(f"sqlite:///{tmp_path}/openfootball.db")
    Base.metadata.create_all(engine)
    with Session(engine) as database_session:
        yield database_session


def test_normalizes_local_kickoffs_and_uses_pinned_publication_evidence() -> None:
    rows = normalize_openfootball_results(
        _dataset(),
        dataset_path="2024-25/en.1.json",
        competition="Premier League",
        country="England",
        season="2024/25",
        timezone="Europe/London",
        source_commit=COMMIT,
        source_updated_at=PUBLISHED_AT,
    )

    assert rows[0].kickoff_at == datetime(2024, 8, 16, 19, 0, tzinfo=UTC)
    assert rows[1].kickoff_at == datetime(2025, 1, 4, 20, 0, tzinfo=UTC)
    assert all(row.observed_at == PUBLISHED_AT for row in rows)
    assert all(row.settled_at == PUBLISHED_AT for row in rows)
    assert rows[0].provider_event_key != rows[1].provider_event_key


def test_rejects_a_fixture_after_the_pinned_publication_timestamp() -> None:
    with pytest.raises(OpenFootballImportError, match="not available"):
        normalize_openfootball_results(
            _dataset(),
            dataset_path="2024-25/en.1.json",
            competition="Premier League",
            country="England",
            season="2024/25",
            timezone="Europe/London",
            source_commit=COMMIT,
            source_updated_at=datetime(2024, 8, 1, tzinfo=UTC),
        )


def test_normalizes_direct_full_time_score_variant() -> None:
    payload = json.loads(_dataset())
    payload["matches"][0]["score"] = [1, 0]

    rows = normalize_openfootball_results(
        json.dumps(payload).encode(),
        dataset_path="2024-25/en.1.json",
        competition="Premier League",
        country="England",
        season="2024/25",
        timezone="Europe/London",
        source_commit=COMMIT,
        source_updated_at=PUBLISHED_AT,
    )

    assert rows[0].home_goals == 1
    assert rows[0].away_goals == 0


@pytest.mark.parametrize("score", [[1], [1, -1], [1, 0.5], "1-0"])
def test_rejects_invalid_direct_full_time_score_variant(score: object) -> None:
    payload = json.loads(_dataset())
    payload["matches"][0]["score"] = score

    with pytest.raises(OpenFootballImportError, match="score.ft"):
        normalize_openfootball_results(
            json.dumps(payload).encode(),
            dataset_path="2024-25/en.1.json",
            competition="Premier League",
            country="England",
            season="2024/25",
            timezone="Europe/London",
            source_commit=COMMIT,
            source_updated_at=PUBLISHED_AT,
        )


def test_import_persists_open_data_provenance(session: Session) -> None:
    rows = normalize_openfootball_results(
        _dataset(),
        dataset_path="2024-25/en.1.json",
        competition="Premier League",
        country="England",
        season="2024/25",
        timezone="Europe/London",
        source_commit=COMMIT,
        source_updated_at=PUBLISHED_AT,
    )
    imported = import_results_csv(
        session,
        filename=f"openfootball-2024-25-{COMMIT[:12]}.csv",
        content=serialize_result_rows_csv(rows),
        provider_slug="openfootball-cc0",
        provider_name="OpenFootball CC0 results",
        provider_kind="open_data",
        provider_terms_url=OPENFOOTBALL_LICENSE_URL,
        now=datetime(2026, 7, 22, tzinfo=UTC),
    )

    provider = session.scalar(select(Provider).where(Provider.slug == "openfootball-cc0"))
    assert imported.results_created == 2
    assert provider is not None
    assert provider.kind == "open_data"
    assert provider.terms_url == OPENFOOTBALL_LICENSE_URL
    assert provider.is_demo is False


def _dataset() -> bytes:
    return json.dumps(
        {
            "name": "English Premier League 2024/25",
            "matches": [
                {
                    "date": "2024-08-16",
                    "time": "20:00",
                    "team1": "Manchester United FC",
                    "team2": "Fulham FC",
                    "score": {"ft": [1, 0]},
                },
                {
                    "date": "2025-01-04",
                    "time": "20:00",
                    "team1": "North FC",
                    "team2": "South FC",
                    "score": {"ft": [2, 2]},
                },
            ],
        }
    ).encode()
