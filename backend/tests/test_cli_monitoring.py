from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app import cli
from app.schemas.api import CollectionMonitoringView


class _SessionContext:
    def __enter__(self) -> object:
        return object()

    def __exit__(self, *args: object) -> None:
        return None


def test_monitor_collection_cli_serializes_latest_prediction_refresh(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    observed_at = datetime(2026, 7, 27, 9, 30, tzinfo=UTC)
    result = CollectionMonitoringView.model_validate(
        {
            "observed_at": observed_at,
            "expected_poll_seconds": 900,
            "recent_job_limit": 10,
            "healthy": True,
            "providers": [],
            "alerts": [],
            "latest_prediction_refresh": {
                "provider_job_id": 64,
                "provider_slug": "odds-api-io",
                "job_created_at": observed_at,
                "job_finished_at": observed_at,
                "eligible_events": 42,
                "predictions_created": 3,
                "predictions_reused": 0,
                "events_skipped": 39,
                "research_candidates_available": 5,
                "skip_reasons": {
                    "insufficient_away_team_away_history": 6,
                    "insufficient_home_team_home_history": 33,
                },
            },
            "coverage": {
                "minimum_evaluation_results": 200,
                "required_bookmakers": ["Allwyn / Pamestoixima", "Novibet"],
                "total_events": 0,
                "permitted_events": 0,
                "permitted_final_results": 0,
                "permitted_odds_snapshots": 0,
                "permitted_closing_snapshots": 0,
                "competitions": [],
            },
        }
    )
    monkeypatch.setattr(sys, "argv", ["odds-quant", "monitor-collection"])
    monkeypatch.setattr(cli, "SessionLocal", _SessionContext)
    monkeypatch.setattr(cli, "get_settings", lambda: SimpleNamespace(provider_poll_seconds=900))
    monkeypatch.setattr(cli, "collection_monitoring", lambda *args, **kwargs: result)

    assert cli.main() == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["latest_prediction_refresh"]["provider_job_id"] == 64
    assert payload["latest_prediction_refresh"]["skip_reasons"] == {
        "insufficient_away_team_away_history": 6,
        "insufficient_home_team_home_history": 33,
    }
