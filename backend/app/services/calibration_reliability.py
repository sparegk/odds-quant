from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import BacktestResult, BacktestRun
from app.quant.calibration import PROMOTION_POLICY_VERSION
from app.schemas.matchday import CalibrationReliabilityView
from app.schemas.models import ModelOutputView


def calibration_reliability(
    session: Session, prediction: ModelOutputView | None
) -> CalibrationReliabilityView:
    if prediction is None:
        return _blocked(None, "No timestamp-valid model output is stored at this cutoff.")
    calibration = prediction.probability_calibration
    base = {
        "calibration_method": calibration.method,
        "calibration_version": calibration.version,
        "calibration_applied": calibration.applied,
        "temperature": calibration.temperature,
        "sample_size": calibration.sample_size,
        "fit_through": calibration.fit_through,
        "evaluation_run_id": calibration.evaluation_run_id,
        "prediction_inputs_as_of": prediction.inputs_as_of,
    }
    if not calibration.applied:
        return _blocked(base, "The stored prediction uses raw, uncalibrated probabilities.")
    if calibration.evaluation_run_id is None or calibration.fit_through is None:
        return _blocked(base, "Applied calibration is missing its evaluation run or fit cutoff.")
    run = session.get(BacktestRun, calibration.evaluation_run_id)
    blockers: list[str] = []
    if run is None:
        blockers.append("The referenced calibration evaluation run is missing.")
    else:
        if run.model_version_id != prediction.model_version_id:
            blockers.append("The calibration run belongs to a different model version.")
        if (
            run.status != "completed"
            or run.probability_evaluation_status != "probability_validated"
        ):
            blockers.append("The calibration run is not completed and probability-validated.")
        if run.is_demo:
            blockers.append("Demo calibration evidence cannot establish reliability.")
        probability_checks = run.policy.get("probability_checks")
        if (
            run.policy.get("version") != PROMOTION_POLICY_VERSION
            or run.policy.get("probability_decision") != "probability_validated"
            or not isinstance(probability_checks, dict)
            or probability_checks.get("chronological_recalibration_accepted") is not True
        ):
            blockers.append("The calibration run lacks accepted chronological policy evidence.")
        if _utc(run.test_end) > _utc(prediction.inputs_as_of):
            blockers.append("The calibration test window ends after the prediction input cutoff.")
    if _utc(calibration.fit_through) > _utc(prediction.inputs_as_of):
        blockers.append("The calibrator fit includes outcomes after the prediction input cutoff.")

    result = None
    if run is not None:
        result = session.scalar(
            select(BacktestResult).where(
                BacktestResult.run_id == run.id,
                BacktestResult.benchmark == "temperature_scaled",
                BacktestResult.dimension == "overall",
                BacktestResult.dimension_value == "all",
            )
        )
        if result is None:
            blockers.append("The calibration run has no overall temperature-scaled metrics.")
    metrics = result.metrics if result is not None else {}
    expected_calibration_error = _metric(metrics, "expected_calibration_error")
    brier_score = _metric(metrics, "brier_score")
    log_loss = _metric(metrics, "log_loss")
    if result is not None and expected_calibration_error is None:
        blockers.append("Expected calibration error is missing or invalid.")
    if result is not None and brier_score is None:
        blockers.append("Brier score is missing or invalid.")
    if result is not None and log_loss is None:
        blockers.append("Log loss is missing or invalid.")

    return CalibrationReliabilityView(
        status="blocked" if blockers else "available",
        **base,
        evaluation_test_end=_utc(run.test_end) if run is not None else None,
        evaluation_fingerprint=run.fingerprint if run is not None else None,
        probability_evaluation_status=(
            run.probability_evaluation_status if run is not None else None
        ),
        expected_calibration_error=expected_calibration_error,
        brier_score=brier_score,
        log_loss=log_loss,
        chronological_out_of_sample=not blockers,
        blockers=blockers,
    )


def _blocked(base: dict[str, object] | None, blocker: str) -> CalibrationReliabilityView:
    defaults: dict[str, object] = {
        "calibration_method": "none",
        "calibration_version": "raw-probability-v1",
        "calibration_applied": False,
        "temperature": None,
        "sample_size": 0,
        "fit_through": None,
        "evaluation_run_id": None,
        "prediction_inputs_as_of": None,
    }
    defaults.update(base or {})
    return CalibrationReliabilityView(
        status="blocked",
        **defaults,
        evaluation_test_end=None,
        evaluation_fingerprint=None,
        probability_evaluation_status=None,
        expected_calibration_error=None,
        brier_score=None,
        log_loss=None,
        chronological_out_of_sample=False,
        blockers=[blocker],
    )


def _metric(metrics: dict[str, object], key: str) -> float | None:
    value = metrics.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        return None
    return float(value)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
