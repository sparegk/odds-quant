import json
from pathlib import Path

from app.services.cross_league_confirmation import (
    CROSS_LEAGUE_CONFIRMATION_POLICY_VERSION,
    REQUIRED_UNTOUCHED_FAMILIES,
)
from app.services.evaluation import (
    COLD_START_CALIBRATION_VERSION,
    COLD_START_UNCERTAINTY_VERSION,
    COLD_START_VALIDATION_BENCHMARK_VERSION,
    COLD_START_VALIDATION_METHOD_VERSION,
)

MANIFEST_PATH = Path(__file__).parents[1] / "config" / "cross_league_confirmation_selection_v1.json"


def test_cross_league_selection_freezes_both_complete_families_before_replay() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest["policy_version"] == CROSS_LEAGUE_CONFIRMATION_POLICY_VERSION
    assert manifest["policy_commit"] == "99102ed"
    assert manifest["candidate_implementation_commit"] == "f722ca1"
    assert manifest["candidate"] == {
        "benchmark_version": COLD_START_VALIDATION_BENCHMARK_VERSION,
        "evaluation_method_version": COLD_START_VALIDATION_METHOD_VERSION,
        "uncertainty_version": COLD_START_UNCERTAINTY_VERSION,
        "calibration_version": COLD_START_CALIBRATION_VERSION,
    }

    families = manifest["execution_order"]
    assert len(families) == REQUIRED_UNTOUCHED_FAMILIES
    assert [family["position"] for family in families] == [1, 2]
    assert [family["experiment_id"] for family in families] == [
        "eredivisie-2024-25-v8-cold-start-poisson",
        "primeira-liga-2024-25-v8-cold-start-poisson",
    ]
    assert [family["competition"]["name"] for family in families] == [
        "Eredivisie",
        "Primeira Liga",
    ]
    assert [family["evaluation"]["candidate_events_before_eligibility"] for family in families] == [
        263,
        261,
    ]
    for family in families:
        assert [dataset["final_rows"] for dataset in family["datasets"]] == [306, 306, 306]
        assert family["primary_model"]["expected_training_results"] == 612
        assert family["evaluation"]["candidate_events_before_eligibility"] >= 200
        assert family["evaluation"]["include_cold_start_validation"] is True
        assert family["datasets"][2]["role"] == "untouched_holdout"
    assert manifest["selection_checks"] == {
        "all_files_complete": True,
        "all_training_sources_published_before_boundary": True,
        "all_holdouts_exceed_200_candidates": True,
        "no_existing_competitions_models_or_runs": True,
        "both_families_frozen_before_first_replay": True,
        "raw_files_committed": False,
    }
