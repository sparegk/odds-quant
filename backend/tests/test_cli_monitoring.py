from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app import cli
from app.schemas.api import CollectionMonitoringView, MarketEdgeCoverageView


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


def test_market_edge_coverage_cli_serializes_only_audit_fields(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    observed_at = datetime(2026, 8, 12, 9, 30, tzinfo=UTC)
    result = MarketEdgeCoverageView(
        contract_version="cold-start-v2-market-edge-validation-v1",
        cohort_selection_id="premier-league-2026-27-post-activation-full-season",
        observed_at=observed_at,
        activated_model_id=12,
        activated_model_version="pqc2-c5-202606020000-7917411c",
        expected_events=380,
        stored_events=30,
        final_result_events=0,
        prediction_events=1,
        permitted_snapshots=1660,
        decision_window_events=0,
        two_bookmaker_events=0,
        explicit_closing_events=0,
        qualifying_bookmaker_event_pairs=0,
        cost_profile_bookmaker_event_pairs=0,
        decision_window_coverage=0,
        two_bookmaker_coverage=0,
        closing_coverage=0,
        cost_profile_coverage=0,
        minimum_market_observations=160,
        minimum_market_coverage=0.8,
        minimum_closing_coverage=0.8,
        bookmakers=[
            {
                "bookmaker_id": 4,
                "bookmaker": "Allwyn / Pamestoixima",
                "permitted_snapshots": 1750,
                "permitted_snapshot_events": 30,
                "decision_window_events": 0,
                "explicit_closing_events": 0,
                "cost_profile_events": 0,
            }
        ],
        acquisition_ready=False,
        replay_authorized=False,
        blockers=["incomplete_candidate_universe"],
    )
    monkeypatch.setattr(sys, "argv", ["odds-quant", "audit-market-edge-coverage"])
    monkeypatch.setattr(cli, "SessionLocal", _SessionContext)
    monkeypatch.setattr(cli, "market_edge_coverage", lambda *args, **kwargs: result)

    assert cli.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["stored_events"] == 30
    assert payload["blockers"] == ["incomplete_candidate_universe"]
    assert "roi" not in payload
    assert "clv" not in payload

    monkeypatch.setattr(
        sys,
        "argv",
        ["odds-quant", "audit-market-edge-coverage", "--fail-on-blockers"],
    )
    assert cli.main() == 4
    blocked_payload = json.loads(capsys.readouterr().out)
    assert blocked_payload["replay_authorized"] is False
    assert blocked_payload["blockers"] == ["incomplete_candidate_universe"]

    ready = result.model_copy(
        update={"acquisition_ready": True, "replay_authorized": True, "blockers": []}
    )
    monkeypatch.setattr(cli, "market_edge_coverage", lambda *args, **kwargs: ready)
    assert cli.main() == 0
    ready_payload = json.loads(capsys.readouterr().out)
    assert ready_payload["replay_authorized"] is True
    assert ready_payload["blockers"] == []
