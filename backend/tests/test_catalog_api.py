from __future__ import annotations

from collections.abc import Generator, Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db.models import Event, OddsSnapshot
from app.db.session import Base, get_db
from app.main import app
from app.services.demo_seed import build_demo_odds_csv, seed_demo_data


@pytest.fixture
def api(tmp_path: Path) -> Iterator[tuple[TestClient, Session, datetime]]:
    engine = create_engine(
        f"sqlite:///{tmp_path}/api.db", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    as_of = datetime.now(UTC).replace(second=0, microsecond=0)
    with Session(engine) as seed_session:
        seed_demo_data(seed_session, as_of=as_of)

    def database_override() -> Generator[Session, None, None]:
        with Session(engine) as request_session:
            yield request_session

    app.dependency_overrides[get_db] = database_override
    with TestClient(app) as client, Session(engine) as assertion_session:
        yield client, assertion_session, as_of
    app.dependency_overrides.clear()


def test_events_providers_and_detail_use_stored_data(
    api: tuple[TestClient, Session, datetime],
) -> None:
    client, _, _ = api

    events_response = client.get("/api/v1/events")
    providers_response = client.get("/api/v1/providers")

    assert events_response.status_code == 200
    events = events_response.json()
    assert len(events) == 4
    assert events[0]["is_demo"] is True
    assert events[0]["latest_odds_at"] is not None
    assert providers_response.status_code == 200
    assert providers_response.json()[0]["kind"] == "demo_seed"
    assert providers_response.json()[0]["snapshot_count"] == 8
    assert client.get("/api/v1/jobs").json() == []

    detail = client.get(f"/api/v1/events/{events[0]['id']}")
    assert detail.status_code == 200
    assert detail.json()["event"]["home_team"] == "Northbridge FC"
    assert len(detail.json()["markets"]) == 1


def test_odds_comparison_calculates_devig_and_best_prices(
    api: tuple[TestClient, Session, datetime],
) -> None:
    client, session, _ = api
    event_id = session.scalar(select(Event.id).order_by(Event.id))
    assert event_id is not None

    response = client.get("/api/v1/odds/comparison", params={"event_id": event_id})

    assert response.status_code == 200
    market = response.json()[0]
    assert market["market_type"] == "MATCH_RESULT"
    assert len(market["snapshots"]) == 2
    for snapshot in market["snapshots"]:
        assert snapshot["overround"] > 1
        assert snapshot["bookmaker_margin"] == pytest.approx(snapshot["overround"] - 1)
        assert sum(
            price["proportional_fair_probability"] for price in snapshot["prices"]
        ) == pytest.approx(1)
        assert sum(
            price["power_fair_probability"] for price in snapshot["prices"]
        ) == pytest.approx(1)
    best = {price["selection_code"]: price for price in market["best_prices"]}
    assert best["HOME"]["bookmaker"] == "Demo Beacon Bet"
    assert best["HOME"]["decimal_odds"] == 2.24
    assert best["DRAW"]["bookmaker"] == "Demo Atlas Sports"
    assert best["AWAY"]["bookmaker"] == "Demo Atlas Sports"


def test_csv_upload_and_import_job_are_connected(
    api: tuple[TestClient, Session, datetime],
) -> None:
    client, session, as_of = api

    user_csv = build_demo_odds_csv(as_of).replace(b"Demo Atlas Sports", b"User Atlas Sports")
    user_csv = user_csv.replace(b"Demo Beacon Bet", b"User Beacon Bet")
    response = client.post(
        "/api/v1/imports/odds",
        files={"file": ("user-odds.csv", user_csv, "text/csv")},
    )

    assert response.status_code == 201
    assert response.json()["rows_imported"] == 24
    jobs = client.get("/api/v1/imports")
    assert jobs.status_code == 200
    assert len(jobs.json()) == 2
    job = client.get(f"/api/v1/imports/{response.json()['job_id']}")
    assert job.status_code == 200
    assert job.json()["status"] == "completed"
    assert session.scalar(select(func.count()).select_from(Event)) == 8


def test_rejected_upload_is_atomic_and_returns_problem_details(
    api: tuple[TestClient, Session, datetime],
) -> None:
    client, session, as_of = api
    lines = build_demo_odds_csv(as_of).decode().splitlines()
    incomplete = ("\n".join(lines[:-1]) + "\n").encode()
    original_snapshots = session.scalar(select(func.count()).select_from(OddsSnapshot))

    response = client.post(
        "/api/v1/imports/odds",
        files={"file": ("incomplete.csv", incomplete, "text/csv")},
    )

    assert response.status_code == 422
    problem = response.json()["detail"]
    assert problem["title"] == "Odds import rejected"
    assert problem["import_job_id"] is not None
    session.expire_all()
    assert session.scalar(select(func.count()).select_from(OddsSnapshot)) == original_snapshots


def test_unknown_event_returns_not_found(api: tuple[TestClient, Session, datetime]) -> None:
    client, _, _ = api
    assert client.get("/api/v1/events/999999").status_code == 404
    assert client.get("/api/v1/odds/comparison", params={"event_id": 999999}).status_code == 404
