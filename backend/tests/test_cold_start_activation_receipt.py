import json
from pathlib import Path

import pytest

from app.services.cold_start_activation import (
    ACTIVATION_CONTRACT_VERSION,
    COLD_START_FEATURE_VERSION,
    COLD_START_MODEL_KIND,
    cold_start_activation_decision,
    frozen_activation_evidence,
)

CONFIG = Path(__file__).parents[1] / "config"


def test_live_activation_receipt_is_contract_bound_and_probability_only() -> None:
    receipt = json.loads(
        (CONFIG / "cold_start_activation_receipt_v1.json").read_text(encoding="utf-8")
    )
    activation = cold_start_activation_decision(frozen_activation_evidence())

    assert (
        receipt["activation_contract_version"]
        == activation["version"]
        == (ACTIVATION_CONTRACT_VERSION)
    )
    assert receipt["rejected_legacy_source"]["model_created"] is False
    assert receipt["strict_source"]["model_id"] == 11
    assert receipt["strict_source"]["probability_evaluation_status"] == "unvalidated"
    model = receipt["activated_model"]
    assert model["model_id"] == 12
    assert model["kind"] == activation["model_kind"] == COLD_START_MODEL_KIND
    assert model["feature_version"] == activation["feature_version"] == (COLD_START_FEATURE_VERSION)
    assert model["authorized_probability_markets"] == ["MATCH_RESULT"]
    assert model["evaluation_status"] == "insufficient_market_evidence"
    assert model["market_authorization"] is False
    assert model["automatic_signal_generation_authorized"] is False

    verification = receipt["live_prediction_verification"]
    assert verification["inputs_as_of"] == verification["predicted_at"]
    assert verification["predicted_at"] < verification["kickoff_at"]
    assert verification["away_venue_matches"] == 0
    assert verification["away_used_league_prior"] is True
    assert verification["reliability_weight"] == pytest.approx(0.5)
    assert verification["successful_refits"] == verification["requested_refits"] == 400
    assert verification["calibration_method"] == "identity"
    assert verification["prediction_market_types"] == ["MATCH_RESULT"]
    assert sum(verification["match_result_probabilities"].values()) == pytest.approx(1)

    gate_state = receipt["stored_gate_state"]
    assert gate_state["validation_model_probability_statuses"] == [
        "unvalidated",
        "unvalidated",
    ]
    assert gate_state["strict_run_probability_statuses"] == [
        "insufficient_evidence",
        "insufficient_evidence",
    ]
    assert gate_state["value_signals"] == 0
    assert gate_state["closing_snapshots"] == 0
    assert receipt["operations"]["healthy"] is True
    assert receipt["operations"]["alerts"] == []
