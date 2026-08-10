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
    ExternalValidationReceiptView(
        experiment_id="ligue1-2024-25-v8-cold-start-poisson",
        display_name="Ligue 1 2024/25 cold-start",
        evidence_role="pre_registered_external_holdout",
        specification_frozen_at=datetime(2026, 8, 10, 18, 4, 24, tzinfo=UTC),
        executed_at=datetime(2026, 8, 10, 18, 33, 19, 69057, tzinfo=UTC),
        evaluation_fingerprint=("28a2324ff783d412afbfe030d21f690892a5e2ac3f301e62b1896cea37b77471"),
        probability_decision="insufficient_evidence",
        examined=True,
        retuning_permitted=False,
        market_validation_authorized=False,
    ),
    ExternalValidationReceiptView(
        experiment_id="eredivisie-2024-25-v8-cold-start-poisson",
        display_name="Eredivisie 2024/25 cold-start",
        evidence_role="pre_registered_cross_league_family_one",
        specification_frozen_at=datetime(2026, 8, 10, 18, 57, 49, tzinfo=UTC),
        executed_at=datetime(2026, 8, 10, 19, 17, 36, 71786, tzinfo=UTC),
        evaluation_fingerprint=("40d196d536580d5af7153af345aaf43d075760e817e16ddd41b4e24acc65e551"),
        probability_decision="probability_validated_candidate",
        examined=True,
        retuning_permitted=False,
        market_validation_authorized=False,
    ),
    ExternalValidationReceiptView(
        experiment_id="primeira-liga-2024-25-v8-cold-start-poisson",
        display_name="Primeira Liga 2024/25 cold-start",
        evidence_role="pre_registered_cross_league_family_two",
        specification_frozen_at=datetime(2026, 8, 10, 18, 57, 49, tzinfo=UTC),
        executed_at=datetime(2026, 8, 10, 19, 35, 43, 235167, tzinfo=UTC),
        evaluation_fingerprint=("353bc4310da6b91615e76265aefd25e290c9545fa1d6052aa99a2e6472565821"),
        probability_decision="probability_validated_candidate",
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
