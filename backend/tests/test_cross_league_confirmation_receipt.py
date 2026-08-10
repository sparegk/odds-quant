import json
from pathlib import Path

from app.services.cross_league_confirmation import (
    FamilyConfirmationReceipt,
    cross_league_confirmation_decision,
)
from app.services.external_validation import receipt_for_evaluation

CONFIG = Path(__file__).parents[1] / "config"


def test_two_family_receipts_reproduce_frozen_combined_decision() -> None:
    primeira = json.loads(
        (CONFIG / "primeira_liga_confirmation_receipt_v1.json").read_text(encoding="utf-8")
    )
    combined = json.loads(
        (CONFIG / "cross_league_confirmation_receipt_v1.json").read_text(encoding="utf-8")
    )

    assert primeira["sequence_position"] == 2
    assert primeira["imports"] == {
        "job_ids": [197, 198, 200],
        "rows_received": 918,
        "rows_imported": 918,
        "results_created": 918,
        "competition_ids": [32, 33, 34],
    }
    assert primeira["model"]["sample_size"] == 612
    candidate = primeira["evaluation"]["cold_start_candidate"]
    assert candidate["observations"] == candidate["candidate_events"] == 261
    assert candidate["expected_calibration_error"] <= 0.08
    assert candidate["uniform_brier_upper_difference"] < 0
    assert candidate["uniform_log_loss_upper_difference"] < 0
    assert candidate["decision"] == "probability_validated_candidate"

    family_receipts = tuple(
        FamilyConfirmationReceipt(
            experiment_id=family["experiment_id"],
            evaluation_fingerprint=family["evaluation_fingerprint"],
            probability_decision=family["probability_decision"],
            examined=family["examined"],
        )
        for family in combined["family_receipts"]
    )
    reproduced = cross_league_confirmation_decision(family_receipts)

    assert reproduced["status"] == combined["decision"]["status"]
    assert reproduced["all_families_passed"] is True
    assert reproduced["metric_pooling_permitted"] is False
    assert reproduced["automatic_model_promotion"] is False
    assert reproduced["market_authorization"] is False
    assert combined["stored_state"]["model_probability_statuses"] == [
        "unvalidated",
        "unvalidated",
    ]
    assert combined["stored_state"]["value_signals"] == 0
    assert combined["stored_state"]["closing_snapshots"] == 0

    external = receipt_for_evaluation(primeira["evaluation"]["fingerprint"])
    assert external is not None
    assert external.experiment_id == primeira["experiment_id"]
    assert external.probability_decision == candidate["decision"]
    assert external.market_validation_authorized is False
