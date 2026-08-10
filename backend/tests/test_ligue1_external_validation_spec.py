import json
from pathlib import Path

from app.services.evaluation import (
    BOOTSTRAP_CONFIDENCE_LEVEL,
    BOOTSTRAP_RESAMPLES,
    COLD_START_CALIBRATION_VERSION,
    COLD_START_UNCERTAINTY_VERSION,
    COLD_START_VALIDATION_BENCHMARK_VERSION,
    COLD_START_VALIDATION_METHOD_VERSION,
    COLD_START_VENUE_HISTORY_TARGET,
    MAXIMUM_PROMOTION_ECE,
    MINIMUM_PROMOTION_COVERAGE,
    MINIMUM_PROMOTION_OBSERVATIONS,
)
from app.services.modeling import FEATURE_VERSION

MANIFEST_PATH = Path(__file__).parents[1] / "config" / "ligue1_external_validation_v1.json"


def test_ligue1_external_validation_manifest_locks_cold_start_specification() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest["implementation_commit"] == "f722ca1"
    assert manifest["competition"] == {
        "sport": "football",
        "name": "Ligue 1",
        "country": "France",
        "timezone": "Europe/Paris",
        "family_scope": "same_sport_name_country_all_seasons",
    }
    datasets = manifest["datasets"]
    assert [dataset["final_rows"] for dataset in datasets] == [380, 306, 306]
    assert sum(dataset["final_rows"] for dataset in datasets[:2]) == 686
    assert [dataset["git_blob"] for dataset in datasets] == [
        "66703493e83dbd16b18f0a891a78a3b3a91b71a1",
        "9e42eb9982de8d3652242edf198b4197cdbbaef0",
        "8bc6ec90c62fa423386ec60473cfa6236419a636",
    ]

    primary = manifest["primary_model"]
    assert primary["minimum_matches"] == 200
    assert primary["minimum_team_matches"] == COLD_START_VENUE_HISTORY_TARGET
    assert primary["shrinkage_matches"] == 5.0
    assert primary["feature_version"] == FEATURE_VERSION

    evaluation = manifest["evaluation"]
    assert evaluation["method_version"] == COLD_START_VALIDATION_METHOD_VERSION
    assert evaluation["candidate_events_before_eligibility"] == 270
    assert evaluation["prediction_lead_minutes"] == 60
    assert evaluation["minimum_training_matches"] == 200
    assert evaluation["calibration_bins"] == 10
    assert evaluation["include_cold_start_validation"] is True

    cold_start = manifest["cold_start"]
    assert cold_start["benchmark_version"] == COLD_START_VALIDATION_BENCHMARK_VERSION
    assert cold_start["uncertainty_version"] == COLD_START_UNCERTAINTY_VERSION
    assert cold_start["venue_history_target"] == COLD_START_VENUE_HISTORY_TARGET
    assert cold_start["calibration_version"] == COLD_START_CALIBRATION_VERSION
    assert cold_start["calibration_method"] == "identity_only_no_outcome_fitted_parameters"
    assert cold_start["outcome_fitted_parameters"] is False

    policy = manifest["probability_policy"]
    assert policy["minimum_observations"] == MINIMUM_PROMOTION_OBSERVATIONS
    assert policy["minimum_coverage"] == MINIMUM_PROMOTION_COVERAGE
    assert policy["maximum_expected_calibration_error"] == MAXIMUM_PROMOTION_ECE
    assert manifest["bootstrap"]["confidence_level"] == BOOTSTRAP_CONFIDENCE_LEVEL
    assert manifest["bootstrap"]["resamples"] == BOOTSTRAP_RESAMPLES
    assert manifest["decision_rules"]["automatic_model_promotion"] is False
    assert manifest["decision_rules"]["market_authorization"] is False
