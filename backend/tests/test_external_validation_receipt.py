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


def test_ligue1_cold_start_external_validation_receipt_is_fingerprint_bound() -> None:
    fingerprint = "28a2324ff783d412afbfe030d21f690892a5e2ac3f301e62b1896cea37b77471"

    receipt = receipt_for_evaluation(fingerprint)

    assert receipt is not None
    assert receipt.experiment_id == "ligue1-2024-25-v8-cold-start-poisson"
    assert receipt.display_name == "Ligue 1 2024/25 cold-start"
    assert receipt.probability_decision == "insufficient_evidence"
    assert receipt.examined is True
    assert receipt.retuning_permitted is False
    assert receipt.market_validation_authorized is False


def test_eredivisie_confirmation_receipt_is_fingerprint_bound() -> None:
    fingerprint = "40d196d536580d5af7153af345aaf43d075760e817e16ddd41b4e24acc65e551"

    receipt = receipt_for_evaluation(fingerprint)

    assert receipt is not None
    assert receipt.experiment_id == "eredivisie-2024-25-v8-cold-start-poisson"
    assert receipt.evidence_role == "pre_registered_cross_league_family_one"
    assert receipt.probability_decision == "probability_validated_candidate"
    assert receipt.examined is True
    assert receipt.retuning_permitted is False
    assert receipt.market_validation_authorized is False
