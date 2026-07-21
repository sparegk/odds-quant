from __future__ import annotations

import csv
import io
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db.models import (
    AvailabilityReport,
    Event,
    ImportJob,
    LineupMember,
    LineupSnapshot,
    Player,
    RawIngestion,
)
from app.db.session import Base, get_db
from app.main import app
from app.schemas.intelligence import AvailabilityInput, IntelligenceImportRequest
from app.services.demo_seed import seed_demo_data
from app.services.intelligence_import import (
    IntelligenceImportError,
    import_intelligence_bundle,
    parse_availability_csv,
)

NOW = datetime(2026, 7, 21, 12, 0, tzinfo=UTC)


@pytest.fixture
def session(tmp_path: Path) -> Generator[Session, None, None]:
    engine = create_engine(
        f"sqlite:///{tmp_path}/intelligence.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    with Session(engine) as database:
        seed_demo_data(database, as_of=NOW, ingested_at=NOW)
        yield database


def _request(session: Session) -> IntelligenceImportRequest:
    event = session.scalar(select(Event).order_by(Event.id))
    assert event is not None
    return IntelligenceImportRequest.model_validate(
        {
            "source_key": "official:event-lineup:1",
            "provider_slug": "licensed-detail",
            "provider_name": "Licensed Detail Feed",
            "players": [
                {
                    "provider_player_key": "player-1",
                    "name": "Research Player",
                    "position": "FW",
                }
            ],
            "availability": [
                {
                    "provider_player_key": "player-1",
                    "team_id": event.home_team_id,
                    "event_id": event.id,
                    "status": "doubtful",
                    "reason": "ankle assessment",
                    "evidence_class": "licensed_provider",
                    "confidence": 0.7,
                    "effective_from": NOW,
                    "published_at": NOW - timedelta(minutes=2),
                    "observed_at": NOW - timedelta(minutes=1),
                }
            ],
            "lineups": [
                {
                    "event_id": event.id,
                    "team_id": event.home_team_id,
                    "lineup_type": "expected",
                    "formation": "4-3-3",
                    "confidence": 0.65,
                    "published_at": NOW - timedelta(minutes=2),
                    "observed_at": NOW - timedelta(minutes=1),
                    "members": [
                        {
                            "provider_player_key": "player-1",
                            "starter": True,
                            "position": "FW",
                            "expected_probability": 0.65,
                        }
                    ],
                }
            ],
        }
    )


def test_bundle_import_is_atomic_timestamped_and_idempotent(session: Session) -> None:
    request = _request(session)

    result = import_intelligence_bundle(session, request, now=NOW)
    repeated = import_intelligence_bundle(session, request, now=NOW)

    assert result.status == "completed"
    assert result.created == {
        "players": 1,
        "availability": 1,
        "lineups": 1,
        "lineup_members": 1,
    }
    assert repeated.job_id == result.job_id
    assert repeated.content_sha256 == result.content_sha256
    assert session.scalar(select(func.count()).select_from(Player)) == 1
    assert session.scalar(select(func.count()).select_from(AvailabilityReport)) == 1
    assert session.scalar(select(func.count()).select_from(LineupSnapshot)) == 1
    assert session.scalar(select(func.count()).select_from(LineupMember)) == 1
    raw = session.scalar(
        select(RawIngestion).where(RawIngestion.schema_version == "football-intelligence-bundle-v1")
    )
    assert raw is not None
    assert raw.schema_version == "football-intelligence-bundle-v1"
    assert raw.source_updated_at is not None
    assert raw.source_updated_at.replace(tzinfo=UTC) == NOW - timedelta(minutes=2)


def test_bundle_import_rolls_back_every_domain_row_on_identity_error(session: Session) -> None:
    request = _request(session)
    request.availability[0].team_id = 999_999

    with pytest.raises(IntelligenceImportError, match="rejected") as caught:
        import_intelligence_bundle(session, request, now=NOW)

    assert caught.value.job_id is not None
    assert session.scalar(select(func.count()).select_from(Player)) == 0
    assert session.scalar(select(func.count()).select_from(AvailabilityReport)) == 0
    assert (
        session.scalar(
            select(func.count())
            .select_from(RawIngestion)
            .where(RawIngestion.schema_version == "football-intelligence-bundle-v1")
        )
        == 0
    )
    rejected = session.get_one(ImportJob, caught.value.job_id)
    assert rejected.status == "rejected"


def test_availability_csv_is_strict() -> None:
    row = AvailabilityInput(
        provider_player_key="player-1",
        team_id=1,
        status="out",
        evidence_class="official",
        confidence=1,
        effective_from=NOW,
        published_at=NOW - timedelta(minutes=1),
        observed_at=NOW,
    )
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(AvailabilityInput.model_fields))
    writer.writeheader()
    writer.writerow(row.model_dump(mode="json"))

    parsed = parse_availability_csv(stream.getvalue().encode())

    assert parsed == [row]


def test_intelligence_api_persists_typed_bundle(session: Session) -> None:
    engine = session.get_bind()

    def database_override():  # type: ignore[no-untyped-def]
        with Session(engine) as request_session:
            yield request_session

    app.dependency_overrides[get_db] = database_override
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/imports/intelligence",
                json=_request(session).model_dump(mode="json"),
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["created"]["availability"] == 1
