from __future__ import annotations

from typing import TypedDict

FEATURE_ACTIVATION_VERSION = "player-tactical-feature-gate-v1"


class FeatureActivationEvidence(TypedDict):
    version: str
    status: str
    probabilities_adjusted: bool
    requested_contexts: list[str]
    applied_features: list[str]
    blockers: list[str]


def blocked_feature_activation(
    *,
    requested_contexts: list[str],
) -> FeatureActivationEvidence:
    contexts = sorted(set(requested_contexts))
    if any(not context for context in contexts):
        raise ValueError("feature activation contexts must be non-empty strings")
    return {
        "version": FEATURE_ACTIVATION_VERSION,
        "status": "blocked",
        "probabilities_adjusted": False,
        "requested_contexts": contexts,
        "applied_features": [],
        "blockers": [
            "no_validated_player_feature_version",
            "missing_licensed_timestamped_player_history",
            "missing_chronological_ablation_evidence",
            "double_counting_not_independently_excluded",
        ],
    }
