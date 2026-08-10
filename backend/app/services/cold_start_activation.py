from __future__ import annotations

from dataclasses import dataclass

ACTIVATION_CONTRACT_VERSION = "cold-start-v2-probability-activation-v1"
CONFIRMATION_POLICY_VERSION = "cross-league-cold-start-confirmation-v1"
CONFIRMATION_SELECTION_ID = "eredivisie-primeira-2024-25-cold-start-v2"
REQUIRED_CONFIRMATION_STATUS = "replicated_probability_candidate"
COLD_START_MODEL_KIND = "poisson_team_strength_cold_start_v2"
COLD_START_FEATURE_VERSION = "final-score-home-away-v4-cold-start-v2"
COLD_START_PREDICTION_POLICY_VERSION = "league-prior-uniform-widening-v2"
COLD_START_UNCERTAINTY_VERSION = "venue-history-uniform-mixture-v1"
COLD_START_CALIBRATION_VERSION = "identity-after-uncertainty-widening-v1"
EXPECTED_FAMILY_FINGERPRINTS = (
    "40d196d536580d5af7153af345aaf43d075760e817e16ddd41b4e24acc65e551",
    "353bc4310da6b91615e76265aefd25e290c9545fa1d6052aa99a2e6472565821",
)
EXPECTED_SOURCE_MODEL_IDS = (9, 10)


@dataclass(frozen=True)
class ColdStartActivationEvidence:
    policy_version: str
    selection_id: str
    confirmation_status: str
    family_fingerprints: tuple[str, ...]
    source_model_ids: tuple[int, ...]
    source_model_probability_statuses: tuple[str, ...]
    strict_run_probability_statuses: tuple[str, ...]
    value_signal_count: int
    closing_snapshot_count: int


def cold_start_activation_decision(
    evidence: ColdStartActivationEvidence,
) -> dict[str, object]:
    checks = {
        "confirmation_policy_matches": evidence.policy_version == CONFIRMATION_POLICY_VERSION,
        "selection_matches": evidence.selection_id == CONFIRMATION_SELECTION_ID,
        "replicated_candidate_confirmed": (
            evidence.confirmation_status == REQUIRED_CONFIRMATION_STATUS
        ),
        "family_fingerprints_match": (evidence.family_fingerprints == EXPECTED_FAMILY_FINGERPRINTS),
        "source_models_match": evidence.source_model_ids == EXPECTED_SOURCE_MODEL_IDS,
        "source_models_remain_unvalidated": (
            evidence.source_model_probability_statuses == ("unvalidated", "unvalidated")
        ),
        "strict_runs_remain_insufficient": (
            evidence.strict_run_probability_statuses
            == ("insufficient_evidence", "insufficient_evidence")
        ),
        "no_value_signals_created": evidence.value_signal_count == 0,
        "no_closing_snapshots_claimed": evidence.closing_snapshot_count == 0,
    }
    if not all(checks.values()):
        failed = sorted(name for name, passed in checks.items() if not passed)
        raise ValueError(f"cold-start activation evidence failed: {', '.join(failed)}")

    return {
        "version": ACTIVATION_CONTRACT_VERSION,
        "status": "approved_probability_only_model_path",
        "checks": checks,
        "model_kind": COLD_START_MODEL_KIND,
        "feature_version": COLD_START_FEATURE_VERSION,
        "prediction_policy_version": COLD_START_PREDICTION_POLICY_VERSION,
        "uncertainty_version": COLD_START_UNCERTAINTY_VERSION,
        "calibration_version": COLD_START_CALIBRATION_VERSION,
        "initial_probability_evaluation_status": "probability_validated",
        "initial_market_evaluation_status": "insufficient_market_evidence",
        "source_model_immutability_required": True,
        "new_model_row_required": True,
        "probability_prediction_authorized": True,
        "automatic_signal_generation_authorized": False,
        "market_authorization": False,
        "player_features_authorized": False,
        "staking_or_profitability_claims_authorized": False,
    }
