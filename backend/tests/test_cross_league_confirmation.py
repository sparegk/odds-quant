import json
from pathlib import Path

import pytest

from app.services.cross_league_confirmation import (
    CROSS_LEAGUE_CONFIRMATION_POLICY_VERSION,
    REQUIRED_UNTOUCHED_FAMILIES,
    FamilyConfirmationReceipt,
    cross_league_confirmation_decision,
)
from app.services.evaluation import (
    COLD_START_CALIBRATION_VERSION,
    COLD_START_UNCERTAINTY_VERSION,
    COLD_START_VALIDATION_BENCHMARK_VERSION,
    COLD_START_VALIDATION_METHOD_VERSION,
    MAXIMUM_PROMOTION_ECE,
    MINIMUM_PROMOTION_COVERAGE,
    MINIMUM_PROMOTION_OBSERVATIONS,
)

MANIFEST_PATH = Path(__file__).parents[1] / "config" / "cross_league_confirmation_policy_v1.json"


def _receipt(experiment_id: str, fingerprint: str, decision: str) -> FamilyConfirmationReceipt:
    return FamilyConfirmationReceipt(
        experiment_id=experiment_id,
        evaluation_fingerprint=fingerprint,
        probability_decision=decision,
        examined=True,
    )


def test_cross_league_policy_manifest_locks_existing_cold_start_candidate() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest["policy_version"] == CROSS_LEAGUE_CONFIRMATION_POLICY_VERSION
    assert manifest["sequence"]["required_untouched_families"] == REQUIRED_UNTOUCHED_FAMILIES
    assert manifest["candidate"] == {
        "benchmark_version": COLD_START_VALIDATION_BENCHMARK_VERSION,
        "evaluation_method_version": COLD_START_VALIDATION_METHOD_VERSION,
        "implementation_commit": "f722ca1",
        "uncertainty_version": COLD_START_UNCERTAINTY_VERSION,
        "calibration_version": COLD_START_CALIBRATION_VERSION,
        "calibration_method": "identity_only_no_outcome_fitted_parameters",
    }
    gate = manifest["family_gate"]
    assert gate["minimum_observations"] == MINIMUM_PROMOTION_OBSERVATIONS
    assert gate["minimum_coverage"] == MINIMUM_PROMOTION_COVERAGE
    assert gate["maximum_expected_calibration_error"] == MAXIMUM_PROMOTION_ECE
    assert manifest["combined_decision"]["metric_pooling_permitted"] is False
    assert manifest["authorization"]["automatic_model_promotion"] is False
    assert manifest["authorization"]["market_authorization"] is False


def test_cross_league_confirmation_requires_both_independent_passes() -> None:
    passed = cross_league_confirmation_decision(
        (
            _receipt("family-one", "1" * 64, "probability_validated_candidate"),
            _receipt("family-two", "2" * 64, "probability_validated_candidate"),
        )
    )
    failed = cross_league_confirmation_decision(
        (
            _receipt("family-one", "1" * 64, "probability_validated_candidate"),
            _receipt("family-two", "2" * 64, "insufficient_evidence"),
        )
    )

    assert passed["status"] == "replicated_probability_candidate"
    assert passed["all_families_passed"] is True
    assert passed["automatic_model_promotion"] is False
    assert failed["status"] == "replication_failed"
    assert failed["all_families_passed"] is False
    assert failed["metric_pooling_permitted"] is False


def test_cross_league_confirmation_rejects_replacement_or_unfinalized_evidence() -> None:
    with pytest.raises(ValueError, match="exactly two"):
        cross_league_confirmation_decision(
            (_receipt("family-one", "1" * 64, "probability_validated_candidate"),)
        )
    with pytest.raises(ValueError, match="distinct"):
        cross_league_confirmation_decision(
            (
                _receipt("family-one", "1" * 64, "probability_validated_candidate"),
                _receipt("family-one", "2" * 64, "probability_validated_candidate"),
            )
        )
    with pytest.raises(ValueError, match="finalized examined"):
        cross_league_confirmation_decision(
            (
                _receipt("family-one", "1" * 64, "probability_validated_candidate"),
                FamilyConfirmationReceipt(
                    experiment_id="family-two",
                    evaluation_fingerprint="2" * 64,
                    probability_decision="probability_validated_candidate",
                    examined=False,
                ),
            )
        )
