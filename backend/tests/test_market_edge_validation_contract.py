import hashlib
import json
from pathlib import Path
from typing import cast

from app.services.evaluation import (
    BOOTSTRAP_CONFIDENCE_LEVEL,
    BOOTSTRAP_RESAMPLES,
    MARKET_BENCHMARK_MAX_AGE,
    MINIMUM_MARKET_BOOKMAKERS,
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


def _manifest() -> dict[str, object]:
    return cast(
        dict[str, object],
        json.loads((CONFIG / "market_edge_validation_v1.json").read_text(encoding="utf-8")),
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_contract_is_bound_to_activation_evidence() -> None:
    manifest = _manifest()
    evidence = manifest["activation_evidence"]
    assert isinstance(evidence, dict)

    assert manifest["contract_version"] == "cold-start-v2-market-edge-validation-v1"
    assert evidence["activation_contract_sha256"] == _sha256(
        CONFIG / "cold_start_activation_contract_v1.json"
    )
    assert evidence["activation_receipt_sha256"] == _sha256(
        CONFIG / "cold_start_activation_receipt_v1.json"
    )
    assert evidence["activated_model_version"] == "pqc2-c5-202606020000-7917411c"
    assert evidence["required_probability_status"] == "probability_validated"
    assert evidence["required_initial_market_status"] == "insufficient_market_evidence"


def test_contract_pins_existing_market_and_signal_policy() -> None:
    manifest = _manifest()
    market = manifest["market_probability_gate"]
    signals = manifest["value_policy_replay"]
    eligible = manifest["eligible_market_evidence"]
    assert isinstance(market, dict)
    assert isinstance(signals, dict)
    assert isinstance(eligible, dict)

    assert market["minimum_bookmakers_per_event"] == MINIMUM_MARKET_BOOKMAKERS
    assert market["minimum_observations"] == MINIMUM_MARKET_PROMOTION_OBSERVATIONS
    assert market["minimum_candidate_coverage"] == MINIMUM_MARKET_PROMOTION_COVERAGE
    assert market["bootstrap_confidence_level"] == BOOTSTRAP_CONFIDENCE_LEVEL
    assert market["bootstrap_resamples"] == BOOTSTRAP_RESAMPLES
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


def test_contract_keeps_execution_fail_closed() -> None:
    manifest = _manifest()
    cohort = manifest["prospective_cohort"]
    evidence = manifest["eligible_market_evidence"]
    edge = manifest["edge_gate"]
    authorization = manifest["authorization"]
    assert isinstance(cohort, dict)
    assert isinstance(evidence, dict)
    assert isinstance(edge, dict)
    assert isinstance(authorization, dict)

    assert cohort["interim_return_or_clv_decisions_allowed"] is False
    assert cohort["replace_or_pool_competitions_after_price_inspection"] is False
    assert evidence["closing_status_must_not_be_inferred"] is True
    assert evidence["atomic_import_required"] is True
    assert edge["point_estimate_alone_never_passes"] is True
    assert authorization["automatic_value_signals_before_market_probability_gate"] is False
    assert authorization["staking_before_edge_gate"] is False
    assert authorization["profitability_claim_before_all_gates"] is False
