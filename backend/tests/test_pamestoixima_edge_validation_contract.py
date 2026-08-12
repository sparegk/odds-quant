import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import cast

from app.services.evaluation import (
    BOOTSTRAP_CONFIDENCE_LEVEL,
    BOOTSTRAP_RESAMPLES,
    MARKET_BENCHMARK_MAX_AGE,
    MINIMUM_MARKET_PROMOTION_COVERAGE,
    MINIMUM_MARKET_PROMOTION_OBSERVATIONS,
)
from app.signals.policy import (
    MAXIMUM_CALIBRATION_ERROR,
    MAXIMUM_IMPLIED_MOVE_POINTS,
    MAXIMUM_ODDS_AGE_MINUTES,
    MAXIMUM_ODDS_MOVE_RATIO,
    MINIMUM_BOOKMAKER_COUNT,
    MINIMUM_SAMPLE_SIZE_PER_TEAM,
    MINIMUM_VALUE_CONFIDENCE,
    MINIMUM_VALUE_EDGE,
    MINIMUM_VALUE_EXPECTED_VALUE,
    SIGNAL_POLICY_VERSION,
)

CONFIG = Path(__file__).parents[1] / "config"


def _manifest(name: str = "pamestoixima_edge_validation_v1.json") -> dict[str, object]:
    return cast(
        dict[str, object],
        json.loads((CONFIG / name).read_text(encoding="utf-8")),
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_pamestoixima_contract_is_prospective_and_activation_bound() -> None:
    manifest = _manifest()
    cohort = manifest["prospective_cohort"]
    evidence = manifest["activation_evidence"]
    scope = manifest["bookmaker_scope"]
    assert isinstance(cohort, dict)
    assert isinstance(evidence, dict)
    assert isinstance(scope, dict)

    frozen_at = datetime.fromisoformat(str(manifest["frozen_at"]))
    kickoff_start = datetime.fromisoformat(str(cohort["kickoff_start_inclusive"]))
    assert frozen_at == kickoff_start
    assert cohort["expected_complete_candidate_events"] == 380
    assert scope == {
        "bookmaker_slug": "allwyn-pamestoixima",
        "bookmaker_name": "Allwyn / Pamestoixima",
        "minimum_bookmakers_per_event": 1,
        "additional_bookmakers_must_not_enter_this_replay": True,
    }
    assert evidence["activation_contract_sha256"] == _sha256(
        CONFIG / "cold_start_activation_contract_v1.json"
    )
    assert evidence["activation_receipt_sha256"] == _sha256(
        CONFIG / "cold_start_activation_receipt_v1.json"
    )
    assert evidence["activated_model_id"] == 12
    assert evidence["activated_model_version"] == "pqc2-c5-202606020000-7917411c"


def test_pamestoixima_contract_pins_benchmark_and_signal_policy() -> None:
    manifest = _manifest()
    benchmark = manifest["single_book_probability_benchmark_gate"]
    signals = manifest["value_policy_replay"]
    eligible = manifest["eligible_market_evidence"]
    assert isinstance(benchmark, dict)
    assert isinstance(signals, dict)
    assert isinstance(eligible, dict)

    assert benchmark["minimum_observations"] == MINIMUM_MARKET_PROMOTION_OBSERVATIONS
    assert benchmark["minimum_candidate_coverage"] == MINIMUM_MARKET_PROMOTION_COVERAGE
    assert benchmark["bootstrap_confidence_level"] == BOOTSTRAP_CONFIDENCE_LEVEL
    assert benchmark["bootstrap_resamples"] == BOOTSTRAP_RESAMPLES
    assert benchmark["market_consensus_claim_authorized"] is False
    assert eligible["maximum_market_benchmark_age_seconds"] == int(
        MARKET_BENCHMARK_MAX_AGE.total_seconds()
    )
    assert signals["signal_policy_version"] == SIGNAL_POLICY_VERSION
    assert signals["minimum_sample_size_per_team"] == MINIMUM_SAMPLE_SIZE_PER_TEAM
    assert signals["maximum_calibration_error"] == MAXIMUM_CALIBRATION_ERROR
    assert signals["maximum_price_age_minutes"] == MAXIMUM_ODDS_AGE_MINUTES
    assert signals["minimum_bookmaker_count"] == MINIMUM_BOOKMAKER_COUNT
    assert signals["maximum_odds_move_ratio_exclusive"] == MAXIMUM_ODDS_MOVE_RATIO
    assert signals["maximum_implied_move_points_exclusive"] == MAXIMUM_IMPLIED_MOVE_POINTS
    assert signals["minimum_expected_value"] == MINIMUM_VALUE_EXPECTED_VALUE
    assert signals["minimum_probability_edge"] == MINIMUM_VALUE_EDGE
    assert signals["minimum_confidence"] == MINIMUM_VALUE_CONFIDENCE


def test_single_book_contract_cannot_relax_market_consensus_or_execution_gates() -> None:
    manifest = _manifest()
    original = _manifest("market_edge_validation_v1.json")
    relationship = manifest["relationship_to_market_consensus_contract"]
    cohort = manifest["prospective_cohort"]
    evidence = manifest["eligible_market_evidence"]
    edge = manifest["edge_gate"]
    authorization = manifest["authorization"]
    original_market = original["market_probability_gate"]
    assert isinstance(relationship, dict)
    assert isinstance(cohort, dict)
    assert isinstance(evidence, dict)
    assert isinstance(edge, dict)
    assert isinstance(authorization, dict)
    assert isinstance(original_market, dict)

    assert original_market["minimum_bookmakers_per_event"] == 2
    assert relationship["remains_unchanged"] is True
    assert relationship["single_book_result_can_satisfy_market_consensus_gate"] is False
    assert relationship["single_book_result_can_replace_two_book_evidence"] is False
    assert cohort["interim_return_or_clv_decisions_allowed"] is False
    assert cohort["replace_or_pool_bookmakers_after_price_inspection"] is False
    assert evidence["closing_designation_must_be_explicit"] is True
    assert evidence["closing_status_must_not_be_inferred"] is True
    assert edge["point_estimate_alone_never_passes"] is True
    assert authorization["run_replay_only_after_fixed_cohort_is_final"] is True
    assert authorization["market_consensus_validation_authorized"] is False
    assert authorization["staking_before_edge_gate"] is False
    assert authorization["profitability_claim_before_all_gates"] is False
