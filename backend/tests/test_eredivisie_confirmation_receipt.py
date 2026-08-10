import json
from pathlib import Path

from app.services.external_validation import receipt_for_evaluation

RECEIPT_PATH = Path(__file__).parents[1] / "config" / "eredivisie_confirmation_receipt_v1.json"


def test_eredivisie_confirmation_receipt_is_fingerprint_bound_and_fail_closed() -> None:
    stored = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))

    assert stored["sequence_position"] == 1
    assert stored["imports"] == {
        "job_ids": [193, 194, 195],
        "rows_received": 918,
        "rows_imported": 918,
        "results_created": 918,
        "competition_ids": [29, 30, 31],
    }
    assert stored["model"]["sample_size"] == 612
    assert stored["model"]["probability_evaluation_status"] == "unvalidated"
    evaluation = stored["evaluation"]
    assert evaluation["strict_primary"]["decision"] == "insufficient_evidence"
    candidate = evaluation["cold_start_candidate"]
    assert candidate["observations"] == candidate["candidate_events"] == 263
    assert candidate["expected_calibration_error"] <= 0.08
    assert candidate["uniform_brier_upper_difference"] < 0
    assert candidate["uniform_log_loss_upper_difference"] < 0
    assert candidate["decision"] == "probability_validated_candidate"

    receipt = receipt_for_evaluation(evaluation["fingerprint"])
    assert receipt is not None
    assert receipt.experiment_id == stored["experiment_id"]
    assert receipt.probability_decision == candidate["decision"]
    assert receipt.retuning_permitted is False
    assert receipt.market_validation_authorized is False
    assert stored["combined_confirmation"]["status"] == "pending_second_family"
