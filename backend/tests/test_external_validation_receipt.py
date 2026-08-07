from app.services.external_validation import receipt_for_evaluation


def test_bundesliga_external_validation_receipt_is_fingerprint_bound() -> None:
    fingerprint = "0784718941c4f2e22326902be89c76158f038b0d2a66e487f4b078708d2bf9cb"

    receipt = receipt_for_evaluation(fingerprint)

    assert receipt is not None
    assert receipt.experiment_id == "bundesliga-2024-25-v6-poisson-primary"
    assert receipt.evidence_role == "pre_registered_external_holdout"
    assert receipt.probability_decision == "insufficient_evidence"
    assert receipt.examined is True
    assert receipt.retuning_permitted is False
    assert receipt.market_validation_authorized is False
    assert receipt_for_evaluation("0" * 64) is None
