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
    OPENFOOTBALL_CHAMPIONS_LICENSE_URL,
    OPENFOOTBALL_LICENSE_URL,
    OpenFootballImportError,
    normalize_openfootball_results,
    normalize_openfootball_text_results,
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


def test_normalizes_unambiguous_football_text_with_explicit_aliases() -> None:
    rows = normalize_openfootball_text_results(
        _text_dataset(),
        dataset_path="2025-26/clq.txt",
        competition="UEFA Champions League Qualification",
        country="International",
        season="2025/26",
        timezone="Europe/Berlin",
        source_commit=COMMIT,
        source_updated_at=PUBLISHED_AT,
        team_aliases={"Kuopion PS": "Kuopion Palloseura"},
    )

    assert len(rows) == 2
    assert rows[0].home_team == "Kuopion Palloseura"
    assert rows[0].away_team == "FC Milsami"
    assert rows[0].kickoff_at == datetime(2024, 7, 8, 14, 0, tzinfo=UTC)
    assert rows[0].home_goals == 1
    assert rows[0].away_goals == 0
    assert rows[1].kickoff_at == datetime(2024, 7, 15, 16, 0, tzinfo=UTC)
    assert all(row.observed_at == PUBLISHED_AT for row in rows)
    assert all(row.provider_event_key.startswith("openfootball-champions:") for row in rows)


def test_football_text_rejects_ambiguous_timed_result() -> None:
    content = b"  Tue Jul 8 2024\n    25:00 Broken v Row 1-0\n"

    with pytest.raises(OpenFootballImportError, match="invalid kickoff time"):
        normalize_openfootball_text_results(
            content,
            dataset_path="2025-26/clq.txt",
            competition="UEFA Champions League Qualification",
            country="International",
            season="2025/26",
            timezone="Europe/Berlin",
            source_commit=COMMIT,
            source_updated_at=PUBLISHED_AT,
        )


def test_normalizes_domestic_football_text_without_country_codes() -> None:
    rows = normalize_openfootball_text_results(
        (
            b"= Challenge League 2024/25\n"
            b"  Fri Jul 19 2024\n"
            b"    20:15  FC Aarau v FC Thun Berner Oberland  1-3 (0-2)\n"
            b"    21:00  Awarded FC v Other FC 3-0 [awarded]\n"
        ),
        dataset_path="switzerland/2024-25_ch2.txt",
        competition="Swiss Challenge League",
        country="Switzerland",
        season="2024/25",
        timezone="Europe/Zurich",
        source_commit=COMMIT,
        source_updated_at=PUBLISHED_AT,
        team_aliases={"FC Thun Berner Oberland": "FC Thun"},
    )

    assert rows[0].home_team == "FC Aarau"
    assert rows[0].away_team == "FC Thun"
    assert rows[0].home_goals == 1
    assert rows[0].away_goals == 3
    assert len(rows) == 1


def test_import_persists_champions_repository_provenance(session: Session) -> None:
    rows = normalize_openfootball_text_results(
        _text_dataset(),
        dataset_path="2025-26/clq.txt",
        competition="UEFA Champions League Qualification",
        country="International",
        season="2025/26",
        timezone="Europe/Berlin",
        source_commit=COMMIT,
        source_updated_at=PUBLISHED_AT,
    )
    imported = import_results_csv(
        session,
        filename="openfootball-champions-clq.csv",
        content=serialize_result_rows_csv(rows),
        provider_slug="openfootball-champions-cc0",
        provider_name="OpenFootball Champions League CC0 results",
        provider_kind="open_data",
        provider_terms_url=OPENFOOTBALL_CHAMPIONS_LICENSE_URL,
        now=datetime(2026, 7, 22, tzinfo=UTC),
    )

    provider = session.scalar(select(Provider).where(Provider.slug == "openfootball-champions-cc0"))
    assert imported.results_created == 2
    assert provider is not None
    assert provider.terms_url == OPENFOOTBALL_CHAMPIONS_LICENSE_URL


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


def _text_dataset() -> bytes:
    return (
        b"= UEFA Champions League - Quali 2024/25\n"
        b"  Tue Jul 8 2024\n"
        b"    16:00  Kuopion PS (FIN) v FC Milsami (MDA)  1-0 (0-0)\n"
        b"           Unknown Time (AAA) v Other Team (BBB) 2-0 (1-0)\n"
        b"  Tue Jul 15\n"
        b"    18:00  FC Milsami (MDA) v Kuopion PS (FIN) 0-0\n"
        b"    19:00  Extra Team (AAA) v Pen Team (BBB) 4-3 pen. 1-1 a.e.t. (0-0)\n"
    )
