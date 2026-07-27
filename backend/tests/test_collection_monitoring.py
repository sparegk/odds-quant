from __future__ import annotations

from datetime import UTC, datetime

from app.db.models import Provider, ProviderJob
from app.services.collection_monitoring import _prediction_refresh_view


def _completed_job(skip_reasons: dict[str, int]) -> ProviderJob:
    finished_at = datetime(2026, 7, 26, 21, 22, 57, tzinfo=UTC)
    return ProviderJob(
        id=64,
        provider_id=4,
        job_type="collect_odds",
        status="completed",
        message="Imported sanitized prices",
        created_at=datetime(2026, 7, 26, 21, 22, 54, tzinfo=UTC),
        finished_at=finished_at,
        metrics={
            "prediction_refresh": {
                "eligible_events": 42,
                "predictions_created": 3,
                "predictions_reused": 0,
                "events_skipped": 39,
                "research_candidates_available": 5,
                "skip_reasons": skip_reasons,
            }
        },
    )


def test_prediction_refresh_view_accepts_only_bounded_consistent_metrics() -> None:
    provider = Provider(
        id=4,
        slug="odds-api-io",
        name="Odds-API.io",
        kind="bookmaker_aggregator",
        is_demo=False,
        capabilities={"odds": True},
    )
    valid = _prediction_refresh_view(
        _completed_job(
            {
                "insufficient_away_team_away_history": 6,
                "insufficient_home_team_home_history": 33,
            }
        ),
        provider,
    )

    assert valid is not None
    assert valid.provider_job_id == 64
    assert valid.events_skipped == 39
    assert valid.skip_reasons == {
        "insufficient_away_team_away_history": 6,
        "insufficient_home_team_home_history": 33,
    }
    assert (
        _prediction_refresh_view(
            _completed_job({"raw_model_error_with_variable_match_count": 39}), provider
        )
        is None
    )
    assert (
        _prediction_refresh_view(
            _completed_job({"insufficient_home_team_home_history": 38}), provider
        )
        is None
    )
