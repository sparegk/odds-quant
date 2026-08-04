from __future__ import annotations

import pytest

from app.quant.feature_activation import blocked_feature_activation


def test_player_tactical_feature_activation_is_explicitly_fail_closed() -> None:
    evidence = blocked_feature_activation(
        requested_contexts=["confirmed_lineups", "tactical_matchup", "confirmed_lineups"]
    )

    assert evidence == {
        "version": "player-tactical-feature-gate-v1",
        "status": "blocked",
        "probabilities_adjusted": False,
        "requested_contexts": ["confirmed_lineups", "tactical_matchup"],
        "applied_features": [],
        "blockers": [
            "no_validated_player_feature_version",
            "missing_licensed_timestamped_player_history",
            "missing_chronological_ablation_evidence",
            "double_counting_not_independently_excluded",
        ],
    }


def test_feature_activation_rejects_empty_context_labels() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        blocked_feature_activation(requested_contexts=[""])
