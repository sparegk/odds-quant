from __future__ import annotations

from collections.abc import Generator, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.session import Base, get_db
from app.main import app


@pytest.fixture
def api(tmp_path: Path) -> Iterator[TestClient]:
    engine = create_engine(
        f"sqlite:///{tmp_path}/workspaces.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)

    def database_override() -> Generator[Session, None, None]:
        with Session(engine) as request_session:
            yield request_session

    app.dependency_overrides[get_db] = database_override
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_named_workspace_round_trip_and_delete(api: TestClient) -> None:
    payload = {
        "name": "Tuesday review",
        "items": [
            {
                "id": "match:7",
                "eventId": 7,
                "title": "Northbridge vs Harbour",
                "subtitle": "Premier Test · match",
                "kind": "match",
                "offeredOdds": None,
                "modelProbability": None,
                "marketProbability": None,
                "edge": None,
                "evidenceId": "event:7",
                "note": "Verify timestamped prices.",
                "savedAt": "2026-08-04T00:00:00Z",
            }
        ],
    }

    created = api.put("/api/v1/workspaces", json=payload)
    assert created.status_code == 200
    workspace_id = created.json()["id"]
    assert created.json()["items"][0]["evidenceId"] == "event:7"

    payload["items"][0]["note"] = "Updated note."
    updated = api.put("/api/v1/workspaces", json=payload)
    assert updated.status_code == 200
    assert updated.json()["id"] == workspace_id
    assert api.get("/api/v1/workspaces").json()[0]["items"][0]["note"] == "Updated note."
    assert api.get("/api/v1/workspaces?limit=1&offset=1").json() == []

    assert api.delete(f"/api/v1/workspaces/{workspace_id}").status_code == 204
    assert api.get("/api/v1/workspaces").json() == []


def test_workspace_import_contract_rejects_unknown_and_invalid_evidence(api: TestClient) -> None:
    response = api.put(
        "/api/v1/workspaces",
        json={
            "name": "Invalid",
            "items": [
                {
                    "id": "match:0",
                    "eventId": 0,
                    "title": "Invalid",
                    "subtitle": "",
                    "kind": "match",
                    "evidenceId": "event:0",
                    "note": "",
                    "savedAt": "2026-08-04T00:00:00Z",
                    "unexpected": True,
                }
            ],
        },
    )
    assert response.status_code == 422
