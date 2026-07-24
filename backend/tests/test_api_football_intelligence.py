from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db.models import Event, PlayerAppearance, PlayerStatistic, RawIngestion
from app.db.session import Base
from app.providers.api_football import ApiFootballPlayerPerformance, ApiFootballPlayerSnapshot
from app.services.api_football_intelligence import (
    ApiFootballIntelligenceError,
    build_player_intelligence_request,
)
from app.services.demo_seed import seed_demo_data
from app.services.intelligence_import import import_intelligence_bundle

NOW = datetime(2026, 7, 25, 12, 0, tzinfo=UTC)


@pytest.fixture
def session(tmp_path: Path) -> Generator[Session, None, None]:
    engine = create_engine(
        f"sqlite:///{tmp_path}/api-football.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    with Session(engine) as database:
        seed_demo_data(database, as_of=NOW, ingested_at=NOW)
        yield database


def _snapshot(provider_team_id: int) -> ApiFootballPlayerSnapshot:
    return ApiFootballPlayerSnapshot(
        fixture_id=9001,
        published_at=NOW - timedelta(seconds=5),
        observed_at=NOW,
        performances=[
            ApiFootballPlayerPerformance(
                player_id=701,
                player_name="Research Keeper",
                team_id=provider_team_id,
                team_name="Northbridge",
                position="GK",
                starter=True,
                minutes=90,
                metrics={"goals.saves": 4.0},
            )
        ],
    )


def test_player_snapshot_import_is_timestamped_and_idempotent(session: Session) -> None:
    event = session.scalar(select(Event).order_by(Event.id))
    assert event is not None
    request = build_player_intelligence_request(
        _snapshot(51),
        event_id=event.id,
        local_team_ids={51: event.home_team_id},
    )

    first = import_intelligence_bundle(session, request, now=NOW)
    repeated = import_intelligence_bundle(session, request, now=NOW)

    assert first.job_id == repeated.job_id
    assert first.created == {"players": 1, "appearances": 1, "player_statistics": 1}
    assert session.scalar(select(func.count()).select_from(PlayerAppearance)) == 1
    assert session.scalar(select(func.count()).select_from(PlayerStatistic)) == 1
    raw = session.scalar(
        select(RawIngestion).where(RawIngestion.source_key.like("api-football:fixture:%"))
    )
    assert raw is not None
    assert raw.source_updated_at == (NOW - timedelta(seconds=5)).replace(tzinfo=None)
    assert raw.observed_at == NOW.replace(tzinfo=None)


def test_player_snapshot_requires_explicit_team_identity_mapping(session: Session) -> None:
    event = session.scalar(select(Event).order_by(Event.id))
    assert event is not None

    with pytest.raises(ApiFootballIntelligenceError, match="team ids: 51"):
        build_player_intelligence_request(
            _snapshot(51),
            event_id=event.id,
            local_team_ids={},
        )
