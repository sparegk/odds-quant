import json
from dataclasses import replace
from pathlib import Path

import pytest

from app.services.cold_start_activation import (
    ACTIVATION_CONTRACT_VERSION,
    COLD_START_CALIBRATION_VERSION,
    COLD_START_FEATURE_VERSION,
    COLD_START_MODEL_KIND,
    COLD_START_PREDICTION_POLICY_VERSION,
    COLD_START_UNCERTAINTY_VERSION,
    CONFIRMATION_POLICY_VERSION,
    CONFIRMATION_SELECTION_ID,
    EXPECTED_FAMILY_FINGERPRINTS,
    EXPECTED_SOURCE_MODEL_IDS,
    ColdStartActivationEvidence,
    cold_start_activation_decision,
)

CONFIG = Path(__file__).parents[1] / "config"


def _evidence() -> ColdStartActivationEvidence:
    receipt = json.loads(
        (CONFIG / "cross_league_confirmation_receipt_v1.json").read_text(encoding="utf-8")
    )
    return ColdStartActivationEvidence(
        policy_version=receipt["policy_version"],
        selection_id=receipt["selection_id"],
        confirmation_status=receipt["decision"]["status"],
        family_fingerprints=tuple(
            family["evaluation_fingerprint"] for family in receipt["family_receipts"]
        ),
        source_model_ids=tuple(receipt["stored_state"]["model_ids"]),
        source_model_probability_statuses=tuple(
            receipt["stored_state"]["model_probability_statuses"]
        ),
        strict_run_probability_statuses=tuple(
            receipt["stored_state"]["strict_run_probability_statuses"]
        ),
        value_signal_count=receipt["stored_state"]["value_signals"],
        closing_snapshot_count=receipt["stored_state"]["closing_snapshots"],
    )


def test_activation_contract_pins_evidence_and_probability_only_path() -> None:
    manifest = json.loads(
        (CONFIG / "cold_start_activation_contract_v1.json").read_text(encoding="utf-8")
    )
    decision = cold_start_activation_decision(_evidence())

    assert manifest["contract_version"] == decision["version"] == ACTIVATION_CONTRACT_VERSION
    assert manifest["evidence"]["confirmation_policy_version"] == CONFIRMATION_POLICY_VERSION
    assert manifest["evidence"]["confirmation_selection_id"] == CONFIRMATION_SELECTION_ID
    assert tuple(manifest["evidence"]["family_evaluation_fingerprints"]) == (
        EXPECTED_FAMILY_FINGERPRINTS
    )
    assert tuple(manifest["evidence"]["source_model_ids"]) == EXPECTED_SOURCE_MODEL_IDS
    path = manifest["activated_model_path"]
    assert path["kind"] == decision["model_kind"] == COLD_START_MODEL_KIND
    assert path["feature_version"] == decision["feature_version"] == COLD_START_FEATURE_VERSION
    assert (
        path["prediction_policy_version"]
        == (decision["prediction_policy_version"])
        == COLD_START_PREDICTION_POLICY_VERSION
    )
    assert path["uncertainty_version"] == COLD_START_UNCERTAINTY_VERSION
    assert path["calibration_version"] == COLD_START_CALIBRATION_VERSION
    assert path["venue_history_target"] == 3
    assert decision["status"] == "approved_probability_only_model_path"
    assert decision["probability_prediction_authorized"] is True
    assert decision["automatic_signal_generation_authorized"] is False
    assert decision["market_authorization"] is False


def test_activation_contract_fails_closed_on_evidence_drift() -> None:
    evidence = _evidence()
    invalid_variants = (
        (
            replace(evidence, confirmation_status="replication_failed"),
            "replicated_candidate_confirmed",
        ),
        (
            replace(evidence, family_fingerprints=("0" * 64, "1" * 64)),
            "family_fingerprints_match",
        ),
        (
            replace(
                evidence,
                source_model_probability_statuses=("probability_validated", "unvalidated"),
            ),
            "source_models_remain_unvalidated",
        ),
        (
            replace(
                evidence,
                strict_run_probability_statuses=(
                    "probability_validated",
                    "insufficient_evidence",
                ),
            ),
            "strict_runs_remain_insufficient",
        ),
        (replace(evidence, value_signal_count=1), "no_value_signals_created"),
    )

    for invalid, failed_check in invalid_variants:
        with pytest.raises(ValueError, match=failed_check):
            cold_start_activation_decision(invalid)
