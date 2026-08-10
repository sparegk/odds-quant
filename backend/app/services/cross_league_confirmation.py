from __future__ import annotations

from dataclasses import dataclass

CROSS_LEAGUE_CONFIRMATION_POLICY_VERSION = "cross-league-cold-start-confirmation-v1"
REQUIRED_UNTOUCHED_FAMILIES = 2
PASSING_FAMILY_DECISION = "probability_validated_candidate"
FINAL_FAMILY_DECISIONS = frozenset({PASSING_FAMILY_DECISION, "insufficient_evidence", "demo_only"})


@dataclass(frozen=True)
class FamilyConfirmationReceipt:
    experiment_id: str
    evaluation_fingerprint: str
    probability_decision: str
    examined: bool


def cross_league_confirmation_decision(
    receipts: tuple[FamilyConfirmationReceipt, ...],
) -> dict[str, object]:
    if len(receipts) != REQUIRED_UNTOUCHED_FAMILIES:
        raise ValueError("cross-league confirmation requires exactly two family receipts")
    if len({receipt.experiment_id for receipt in receipts}) != len(receipts):
        raise ValueError("cross-league confirmation families must be distinct")
    if len({receipt.evaluation_fingerprint for receipt in receipts}) != len(receipts):
        raise ValueError("cross-league confirmation fingerprints must be distinct")
    if not all(receipt.examined for receipt in receipts):
        raise ValueError("cross-league confirmation requires finalized examined receipts")
    if any(receipt.probability_decision not in FINAL_FAMILY_DECISIONS for receipt in receipts):
        raise ValueError("cross-league confirmation contains a non-final family decision")

    family_checks = {
        receipt.experiment_id: receipt.probability_decision == PASSING_FAMILY_DECISION
        for receipt in receipts
    }
    replicated = all(family_checks.values())
    return {
        "version": CROSS_LEAGUE_CONFIRMATION_POLICY_VERSION,
        "status": ("replicated_probability_candidate" if replicated else "replication_failed"),
        "required_untouched_families": REQUIRED_UNTOUCHED_FAMILIES,
        "family_checks": family_checks,
        "all_families_passed": replicated,
        "metric_pooling_permitted": False,
        "replacement_family_permitted_after_first_replay": False,
        "automatic_model_promotion": False,
        "market_authorization": False,
    }
