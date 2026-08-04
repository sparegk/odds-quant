import json
from pathlib import Path

from app.quant.calibration import PROMOTION_POLICY_VERSION, RECALIBRATION_VERSION
from app.quant.ensemble import (
    ENSEMBLE_MODELS,
    ENSEMBLE_VERSION,
    ENSEMBLE_WEIGHT_GRID,
    ENSEMBLE_WEIGHT_STEP,
)
from app.quant.model_selection import NESTED_SELECTION_VERSION
from app.services.evaluation import (
    BOOTSTRAP_CONFIDENCE_LEVEL,
    BOOTSTRAP_RESAMPLES,
    CALIBRATION_SELECTION_MINIMUM_IMPROVEMENT,
    ENSEMBLE_MINIMUM_HISTORY,
    EVALUATION_METHOD_VERSION,
    MAXIMUM_PROMOTION_ECE,
    MINIMUM_PROMOTION_COVERAGE,
    MINIMUM_PROMOTION_OBSERVATIONS,
    MINIMUM_RECALIBRATION_EVALUATION_OBSERVATIONS,
    MINIMUM_RECALIBRATION_HISTORY,
    MINIMUM_RECALIBRATION_VALIDATION_OBSERVATIONS,
    NESTED_ELO_K_FACTORS,
    NESTED_POISSON_SHRINKAGES,
    NESTED_SELECTION_MINIMUM_HISTORY,
)
from app.services.modeling import FEATURE_VERSION

MANIFEST_PATH = Path(__file__).parents[1] / "config" / "bundesliga_external_validation_v1.json"


def test_bundesliga_external_validation_manifest_locks_current_specification() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest["implementation_commit"] == ("28ce95ebc2a5c51ef89a2ea6dfef6ef37382e658")
    assert manifest["primary_model"] == {
        "kind": "poisson_scoreline",
        "training_start": "2022-08-01T00:00:00Z",
        "training_end": "2024-09-20T00:00:00Z",
        "minimum_matches": 200,
        "minimum_team_matches": 8,
        "shrinkage_matches": 5.0,
        "feature_version": FEATURE_VERSION,
    }
    evaluation = manifest["evaluation"]
    assert evaluation["method_version"] == EVALUATION_METHOD_VERSION
    assert evaluation["minimum_training_matches"] == 200
    assert evaluation["prediction_lead_minutes"] == 60
    assert evaluation["calibration_bins"] == 10
    assert evaluation["candidate_events_before_eligibility"] == 279

    policy = manifest["probability_policy"]
    assert policy["version"] == PROMOTION_POLICY_VERSION
    assert policy["minimum_observations"] == MINIMUM_PROMOTION_OBSERVATIONS
    assert policy["minimum_coverage"] == MINIMUM_PROMOTION_COVERAGE
    assert policy["maximum_expected_calibration_error"] == MAXIMUM_PROMOTION_ECE
    assert manifest["bootstrap"]["confidence_level"] == BOOTSTRAP_CONFIDENCE_LEVEL
    assert manifest["bootstrap"]["resamples"] == BOOTSTRAP_RESAMPLES

    recalibration = manifest["recalibration"]
    assert recalibration["version"] == RECALIBRATION_VERSION
    assert recalibration["minimum_history"] == MINIMUM_RECALIBRATION_HISTORY
    assert (
        recalibration["minimum_evaluation_observations"]
        == MINIMUM_RECALIBRATION_EVALUATION_OBSERVATIONS
    )
    assert (
        recalibration["minimum_validation_observations"]
        == MINIMUM_RECALIBRATION_VALIDATION_OBSERVATIONS
    )
    assert (
        recalibration["selection_minimum_improvement"] == CALIBRATION_SELECTION_MINIMUM_IMPROVEMENT
    )

    nested = manifest["nested_selection"]
    assert nested["version"] == NESTED_SELECTION_VERSION
    assert nested["minimum_history"] == NESTED_SELECTION_MINIMUM_HISTORY
    assert nested["poisson_shrinkage_matches"] == list(NESTED_POISSON_SHRINKAGES)
    assert nested["elo_k_factors"] == list(NESTED_ELO_K_FACTORS)

    ensemble = manifest["ensemble"]
    assert ensemble["version"] == ENSEMBLE_VERSION
    assert ensemble["models"] == list(ENSEMBLE_MODELS)
    assert ensemble["minimum_history"] == ENSEMBLE_MINIMUM_HISTORY
    assert ensemble["weight_step"] == ENSEMBLE_WEIGHT_STEP
    assert ensemble["weight_grid"] == [list(weights) for weights in ENSEMBLE_WEIGHT_GRID]
