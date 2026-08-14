from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from sqlalchemy.orm import Session

from app.db.models import BacktestResult, BacktestRun
from app.quant.calibration import PROMOTION_POLICY_VERSION
from app.schemas.models import ModelOutputView
from app.services.calibration_reliability import calibration_reliability

NOW = datetime(2026, 8, 14, 10, tzinfo=UTC)


def _prediction(*, applied: bool = True) -> ModelOutputView:
    return ModelOutputView.model_validate(
        {
            "id": 1,
            "event_id": 2,
            "model_version_id": 3,
            "model_version": "poisson-v1",
            "predicted_at": NOW,
            "inputs_as_of": NOW,
            "evidence_class": "team_baseline",
            "lineup_snapshot_ids": [],
            "home_lambda": 1.4,
            "away_lambda": 1.1,
            "sample_size": 100,
            "probability_uncertainty": {
                "method": "bootstrap",
                "version": "v1",
                "confidence_level": 0.95,
                "requested_refits": 10,
                "successful_refits": 10,
                "attempted_refits": 10,
                "block_length": 2,
                "seed_fingerprint": "a" * 64,
                "training_fingerprint": "b" * 64,
            },
            "probability_calibration": {
                "method": "scalar_temperature_scaling" if applied else "none",
                "version": "calibration-v2" if applied else "raw-probability-v1",
                "applied": applied,
                "temperature": 1.1 if applied else None,
                "sample_size": 250 if applied else 0,
                "input_fingerprint": "c" * 64 if applied else None,
                "fit_through": NOW - timedelta(days=2) if applied else None,
                "evaluation_run_id": 7 if applied else None,
            },
            "feature_activation": {
                "version": "v1",
                "status": "blocked",
                "probabilities_adjusted": False,
                "requested_contexts": [],
                "applied_features": [],
                "blockers": [],
            },
            "score_matrix": [],
            "derived_probabilities": {},
            "predictions": [],
        }
    )


def _run(*, test_end: datetime) -> BacktestRun:
    run = BacktestRun(
        id=7,
        model_version_id=3,
        status="completed",
        train_end=NOW - timedelta(days=10),
        validation_end=NOW - timedelta(days=5),
        test_end=test_end,
        fingerprint="d" * 64,
        config={},
        policy={
            "version": PROMOTION_POLICY_VERSION,
            "probability_decision": "probability_validated",
            "probability_checks": {"chronological_recalibration_accepted": True},
        },
        probability_evaluation_status="probability_validated",
        evaluation_status="unvalidated",
        is_demo=False,
    )
    return run


def _result() -> BacktestResult:
    return BacktestResult(
        run_id=7,
        benchmark="temperature_scaled",
        dimension="overall",
        dimension_value="all",
        metrics={
            "expected_calibration_error": 0.04,
            "brier_score": 0.55,
            "log_loss": 0.9,
        },
    )


def test_exposes_only_referenced_chronological_probability_evidence() -> None:
    session = MagicMock(spec=Session)
    session.get.return_value = _run(test_end=NOW - timedelta(days=1))
    session.scalar.return_value = _result()

    view = calibration_reliability(session, _prediction())

    assert view.status == "available"
    assert view.chronological_out_of_sample is True
    assert view.expected_calibration_error == 0.04
    assert view.brier_score == 0.55
    assert view.log_loss == 0.9
    assert view.market_edge_evidence_included is False
    assert view.return_evidence_included is False


def test_blocks_calibration_evidence_whose_test_window_is_in_the_future() -> None:
    session = MagicMock(spec=Session)
    session.get.return_value = _run(test_end=NOW + timedelta(seconds=1))
    session.scalar.return_value = _result()

    view = calibration_reliability(session, _prediction())

    assert view.status == "blocked"
    assert view.chronological_out_of_sample is False
    assert "test window ends after" in view.blockers[0]


def test_raw_probabilities_report_reliability_as_blocked() -> None:
    session = MagicMock(spec=Session)

    view = calibration_reliability(session, _prediction(applied=False))

    assert view.status == "blocked"
    assert view.expected_calibration_error is None
    assert "raw, uncalibrated" in view.blockers[0]
    session.get.assert_not_called()
