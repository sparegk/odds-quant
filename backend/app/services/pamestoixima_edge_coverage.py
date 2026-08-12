from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import cast

from sqlalchemy.orm import Session

from app.schemas.api import PamestoiximaEdgeCoverageView
from app.services.market_edge_coverage import market_edge_coverage

CONFIG_PATH = Path(__file__).parents[2] / "config" / "pamestoixima_edge_validation_v1.json"
BOOKMAKER_NAME = "Allwyn / Pamestoixima"


def pamestoixima_edge_coverage(
    session: Session, *, now: datetime | None = None
) -> PamestoiximaEdgeCoverageView:
    manifest = cast(dict[str, object], json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    cohort = _object(manifest, "prospective_cohort")
    benchmark = _object(manifest, "single_book_probability_benchmark_gate")
    edge = _object(manifest, "edge_gate")
    activation = _object(manifest, "activation_evidence")
    scope = _object(manifest, "bookmaker_scope")
    authorization = _object(manifest, "authorization")
    if _string(scope, "bookmaker_name") != BOOKMAKER_NAME:
        raise ValueError("Pamestoixima contract bookmaker identity drifted")

    base = market_edge_coverage(session, now=now)
    bookmaker = next(
        (item for item in base.bookmakers if item.bookmaker == BOOKMAKER_NAME),
        None,
    )
    permitted_snapshots = bookmaker.permitted_snapshots if bookmaker is not None else 0
    permitted_events = bookmaker.permitted_snapshot_events if bookmaker is not None else 0
    decision_events = bookmaker.decision_window_events if bookmaker is not None else 0
    closing_events = bookmaker.explicit_closing_events if bookmaker is not None else 0
    cost_events = bookmaker.cost_profile_events if bookmaker is not None else 0
    expected = _integer(cohort, "expected_complete_candidate_events")
    minimum_observations = _integer(benchmark, "minimum_observations")
    minimum_coverage = _number(benchmark, "minimum_candidate_coverage")
    minimum_closing = _number(edge, "minimum_closing_price_coverage")
    decision_coverage = decision_events / expected
    closing_coverage = closing_events / expected
    cost_coverage = cost_events / decision_events if decision_events else 0.0

    blockers: list[str] = []
    if "activated_model_missing_or_drifted" in base.blockers:
        blockers.append("activated_model_missing_or_drifted")
    if base.stored_events != expected:
        blockers.append("incomplete_candidate_universe")
    if decision_events < minimum_observations:
        blockers.append("insufficient_decision_window_market_observations")
    if decision_coverage < minimum_coverage:
        blockers.append("insufficient_decision_window_market_coverage")
    if closing_coverage < minimum_closing:
        blockers.append("insufficient_explicit_closing_coverage")
    if base.final_result_events != expected:
        blockers.append("incomplete_final_results")
    if not decision_events or cost_events != decision_events:
        blockers.append("incomplete_cost_profiles")
    ready = not blockers
    return PamestoiximaEdgeCoverageView(
        contract_version=_string(manifest, "contract_version"),
        cohort_selection_id=_string(cohort, "selection_id"),
        observed_at=base.observed_at,
        activated_model_id=_integer(activation, "activated_model_id"),
        activated_model_version=_string(activation, "activated_model_version"),
        expected_events=expected,
        stored_events=base.stored_events,
        final_result_events=base.final_result_events,
        prediction_events=base.prediction_events,
        permitted_snapshots=permitted_snapshots,
        permitted_snapshot_events=permitted_events,
        decision_window_events=decision_events,
        explicit_closing_events=closing_events,
        cost_profile_events=cost_events,
        decision_window_coverage=decision_coverage,
        closing_coverage=closing_coverage,
        cost_profile_coverage=cost_coverage,
        minimum_observations=minimum_observations,
        minimum_candidate_coverage=minimum_coverage,
        minimum_closing_coverage=minimum_closing,
        market_consensus_authorized=_boolean(
            authorization, "market_consensus_validation_authorized"
        ),
        acquisition_ready=ready,
        replay_authorized=ready,
        blockers=blockers,
    )


def _object(values: dict[str, object], key: str) -> dict[str, object]:
    value = values.get(key)
    if not isinstance(value, dict) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"Pamestoixima contract field {key} is invalid")
    return cast(dict[str, object], value)


def _string(values: dict[str, object], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Pamestoixima contract field {key} is invalid")
    return value


def _integer(values: dict[str, object], key: str) -> int:
    value = values.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"Pamestoixima contract field {key} is invalid")
    return value


def _number(values: dict[str, object], key: str) -> float:
    value = values.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Pamestoixima contract field {key} is invalid")
    number = float(value)
    if not 0 < number <= 1:
        raise ValueError(f"Pamestoixima contract field {key} is invalid")
    return number


def _boolean(values: dict[str, object], key: str) -> bool:
    value = values.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"Pamestoixima contract field {key} is invalid")
    return value
