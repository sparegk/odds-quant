from __future__ import annotations

from datetime import UTC, datetime

from app.schemas.models import ExternalValidationReceiptView

_RECEIPTS = (
    ExternalValidationReceiptView(
        experiment_id="bundesliga-2024-25-v6-poisson-primary",
        display_name="Bundesliga 2024/25",
        evidence_role="pre_registered_external_holdout",
        specification_frozen_at=datetime(2026, 8, 4, tzinfo=UTC),
        executed_at=datetime(2026, 8, 7, 12, 0, 35, 466472, tzinfo=UTC),
        evaluation_fingerprint=("0784718941c4f2e22326902be89c76158f038b0d2a66e487f4b078708d2bf9cb"),
        probability_decision="insufficient_evidence",
        examined=True,
        retuning_permitted=False,
        market_validation_authorized=False,
    ),
)


def receipt_for_evaluation(fingerprint: str) -> ExternalValidationReceiptView | None:
    matches = [receipt for receipt in _RECEIPTS if receipt.evaluation_fingerprint == fingerprint]
    if len(matches) > 1:
        raise ValueError("external validation fingerprint is registered more than once")
    return matches[0] if matches else None
