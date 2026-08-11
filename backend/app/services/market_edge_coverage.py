from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Bookmaker,
    BookmakerConstraint,
    BookmakerTaxProfile,
    Competition,
    Event,
    Market,
    MatchResult,
    ModelEventOutput,
    ModelVersion,
    OddsPrice,
    OddsSnapshot,
    Provider,
    Selection,
    Sport,
    TaxProfile,
)
from app.schemas.api import MarketEdgeBookmakerCoverage, MarketEdgeCoverageView

CONFIG_PATH = Path(__file__).parents[2] / "config" / "market_edge_validation_v1.json"
TRACKED_BOOKMAKER_SLUGS = ("allwyn-pamestoixima", "novibet")


@dataclass(frozen=True)
class _Contract:
    version: str
    selection_id: str
    sport: str
    competition: str
    country: str
    season: str
    kickoff_start: datetime
    kickoff_end: datetime
    expected_events: int
    decision_lead: timedelta
    market_max_age: timedelta
    minimum_market_observations: int
    minimum_market_coverage: float
    minimum_closing_coverage: float
    model_id: int
    model_version: str


@dataclass(frozen=True)
class _Snapshot:
    event_id: int
    kickoff_at: datetime
    bookmaker_id: int
    bookmaker: str
    currency: str
    observed_at: datetime
    source_updated_at: datetime | None
    is_closing: bool
    selection_codes: frozenset[str]


@dataclass
class _SnapshotAccumulator:
    event: Event
    market: Market
    snapshot: OddsSnapshot
    bookmaker: Bookmaker
    selection_codes: set[str]


def _contract() -> _Contract:
    manifest = cast(dict[str, object], json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    cohort = _object(manifest, "prospective_cohort")
    evidence = _object(manifest, "eligible_market_evidence")
    market = _object(manifest, "market_probability_gate")
    edge = _object(manifest, "edge_gate")
    activation = _object(manifest, "activation_evidence")
    return _Contract(
        version=_string(manifest, "contract_version"),
        selection_id=_string(cohort, "selection_id"),
        sport=_string(cohort, "sport"),
        competition=_string(cohort, "competition_name"),
        country=_string(cohort, "country"),
        season=_string(cohort, "season"),
        kickoff_start=datetime.fromisoformat(_string(cohort, "kickoff_start_inclusive")),
        kickoff_end=datetime.fromisoformat(_string(cohort, "kickoff_end_exclusive")),
        expected_events=_integer(cohort, "expected_complete_candidate_events"),
        decision_lead=timedelta(minutes=_integer(cohort, "decision_lead_minutes")),
        market_max_age=timedelta(
            seconds=_integer(evidence, "maximum_market_benchmark_age_seconds")
        ),
        minimum_market_observations=_integer(market, "minimum_observations"),
        minimum_market_coverage=_number(market, "minimum_candidate_coverage"),
        minimum_closing_coverage=_number(edge, "minimum_closing_price_coverage"),
        model_id=_integer(activation, "activated_model_id"),
        model_version=_string(activation, "activated_model_version"),
    )


def market_edge_coverage(
    session: Session, *, now: datetime | None = None
) -> MarketEdgeCoverageView:
    contract = _contract()
    reference = _utc(now or datetime.now(UTC))
    events = session.scalars(
        select(Event)
        .join(Competition, Competition.id == Event.competition_id)
        .join(Sport, Sport.id == Competition.sport_id)
        .join(Provider, Provider.id == Event.provider_id)
        .where(
            Sport.slug == contract.sport,
            Competition.name == contract.competition,
            Competition.country == contract.country,
            Competition.season == contract.season,
            Event.kickoff_at >= contract.kickoff_start,
            Event.kickoff_at < contract.kickoff_end,
            Event.is_demo.is_(False),
            Provider.is_demo.is_(False),
        )
        .order_by(Event.kickoff_at, Event.id)
    ).all()
    event_ids = [event.id for event in events]
    snapshots = _snapshots(session, event_ids)
    required_codes = frozenset({"HOME", "DRAW", "AWAY"})
    complete = [snapshot for snapshot in snapshots if snapshot.selection_codes == required_codes]
    permitted_snapshots = len(complete)
    raw_event_books: dict[int, set[int]] = {}
    for snapshot in complete:
        raw_event_books.setdefault(snapshot.event_id, set()).add(snapshot.bookmaker_id)
    decision_pairs: dict[tuple[int, int], _Snapshot] = {}
    closing_pairs: dict[tuple[int, int], _Snapshot] = {}
    for snapshot in complete:
        cutoff = _utc(snapshot.kickoff_at) - contract.decision_lead
        source_time = (
            _utc(snapshot.source_updated_at) if snapshot.source_updated_at is not None else None
        )
        if (
            cutoff - contract.market_max_age <= _utc(snapshot.observed_at) <= cutoff
            and _utc(snapshot.observed_at) <= reference
            and (source_time is None or source_time <= cutoff)
            and (source_time is None or source_time <= reference)
        ):
            _retain_latest(decision_pairs, snapshot)
        if (
            snapshot.is_closing
            and _utc(snapshot.observed_at) < _utc(snapshot.kickoff_at)
            and _utc(snapshot.observed_at) <= reference
            and (source_time is None or source_time < _utc(snapshot.kickoff_at))
            and (source_time is None or source_time <= reference)
        ):
            _retain_latest(closing_pairs, snapshot)

    decision_event_books = _event_bookmakers(decision_pairs)
    closing_event_books = _event_bookmakers(closing_pairs)
    decision_window_events = len(decision_event_books)
    two_bookmaker_events = sum(len(bookmakers) >= 2 for bookmakers in decision_event_books.values())
    explicit_closing_events = len(closing_event_books)
    final_result_events = _final_result_events(session, event_ids, reference)
    model = session.get(ModelVersion, contract.model_id)
    model_matches = model is not None and model.version == contract.model_version
    prediction_events = (
        _prediction_events(
            session,
            events,
            contract.model_id,
            contract.decision_lead,
            reference,
        )
        if model_matches
        else 0
    )
    tax_rows = list(
        session.execute(
            select(BookmakerTaxProfile, TaxProfile).join(
                TaxProfile, TaxProfile.id == BookmakerTaxProfile.tax_profile_id
            )
        )
        .tuples()
        .all()
    )
    constraints = session.scalars(select(BookmakerConstraint)).all()
    cost_pairs = {
        key
        for key, snapshot in decision_pairs.items()
        if _has_cost_profile(
            snapshot,
            decision_cutoff=_utc(snapshot.kickoff_at) - contract.decision_lead,
            tax_rows=tax_rows,
            constraints=constraints,
        )
    }
    bookmaker_names = {
        snapshot.bookmaker_id: snapshot.bookmaker
        for snapshot in [*decision_pairs.values(), *closing_pairs.values()]
    }
    bookmaker_names.update(
        {
            bookmaker.id: bookmaker.name
            for bookmaker in session.scalars(
                select(Bookmaker).where(Bookmaker.slug.in_(TRACKED_BOOKMAKER_SLUGS))
            ).all()
        }
    )
    bookmaker_names.update({snapshot.bookmaker_id: snapshot.bookmaker for snapshot in complete})
    bookmakers = [
        MarketEdgeBookmakerCoverage(
            bookmaker_id=bookmaker_id,
            bookmaker=bookmaker_names[bookmaker_id],
            permitted_snapshots=sum(snapshot.bookmaker_id == bookmaker_id for snapshot in complete),
            permitted_snapshot_events=sum(
                bookmaker_id in values for values in raw_event_books.values()
            ),
            decision_window_events=sum(
                bookmaker_id in values for values in decision_event_books.values()
            ),
            explicit_closing_events=sum(
                bookmaker_id in values for values in closing_event_books.values()
            ),
            cost_profile_events=sum(key[1] == bookmaker_id for key in cost_pairs),
        )
        for bookmaker_id in sorted(bookmaker_names, key=lambda item: bookmaker_names[item])
    ]
    expected = contract.expected_events
    decision_coverage = decision_window_events / expected
    two_bookmaker_coverage = two_bookmaker_events / expected
    closing_coverage = explicit_closing_events / expected
    cost_coverage = len(cost_pairs) / len(decision_pairs) if decision_pairs else 0.0
    blockers: list[str] = []
    if not model_matches:
        blockers.append("activated_model_missing_or_drifted")
    if len(events) != expected:
        blockers.append("incomplete_candidate_universe")
    if decision_window_events < contract.minimum_market_observations:
        blockers.append("insufficient_decision_window_market_observations")
    if decision_coverage < contract.minimum_market_coverage:
        blockers.append("insufficient_decision_window_market_coverage")
    if (
        two_bookmaker_events < contract.minimum_market_observations
        or two_bookmaker_coverage < contract.minimum_market_coverage
    ):
        blockers.append("insufficient_two_bookmaker_market_coverage")
    if closing_coverage < contract.minimum_closing_coverage:
        blockers.append("insufficient_explicit_closing_coverage")
    if final_result_events != expected:
        blockers.append("incomplete_final_results")
    if not decision_pairs or len(cost_pairs) != len(decision_pairs):
        blockers.append("incomplete_cost_profiles")
    ready = not blockers
    return MarketEdgeCoverageView(
        contract_version=contract.version,
        cohort_selection_id=contract.selection_id,
        observed_at=reference,
        activated_model_id=contract.model_id,
        activated_model_version=contract.model_version,
        expected_events=expected,
        stored_events=len(events),
        final_result_events=final_result_events,
        prediction_events=prediction_events,
        permitted_snapshots=permitted_snapshots,
        decision_window_events=decision_window_events,
        two_bookmaker_events=two_bookmaker_events,
        explicit_closing_events=explicit_closing_events,
        qualifying_bookmaker_event_pairs=len(decision_pairs),
        cost_profile_bookmaker_event_pairs=len(cost_pairs),
        decision_window_coverage=decision_coverage,
        two_bookmaker_coverage=two_bookmaker_coverage,
        closing_coverage=closing_coverage,
        cost_profile_coverage=cost_coverage,
        minimum_market_observations=contract.minimum_market_observations,
        minimum_market_coverage=contract.minimum_market_coverage,
        minimum_closing_coverage=contract.minimum_closing_coverage,
        bookmakers=bookmakers,
        acquisition_ready=ready,
        replay_authorized=ready,
        blockers=blockers,
    )


def _snapshots(session: Session, event_ids: list[int]) -> list[_Snapshot]:
    if not event_ids:
        return []
    rows = session.execute(
        select(Event, Market, OddsSnapshot, Bookmaker, Selection)
        .join(Market, Market.event_id == Event.id)
        .join(OddsSnapshot, OddsSnapshot.market_id == Market.id)
        .join(Bookmaker, Bookmaker.id == OddsSnapshot.bookmaker_id)
        .join(Provider, Provider.id == OddsSnapshot.provider_id)
        .join(OddsPrice, OddsPrice.snapshot_id == OddsSnapshot.id)
        .join(Selection, Selection.id == OddsPrice.selection_id)
        .where(
            Event.id.in_(event_ids),
            Market.market_type == "MATCH_RESULT",
            Market.period == "FULL_TIME",
            Market.line.is_(None),
            OddsSnapshot.is_complete.is_(True),
            Bookmaker.is_demo.is_(False),
            Provider.is_demo.is_(False),
        )
        .order_by(OddsSnapshot.id, Selection.id)
    ).all()
    grouped: dict[int, _SnapshotAccumulator] = {}
    for event, market, snapshot, bookmaker, selection in rows:
        accumulator = grouped.setdefault(
            snapshot.id,
            _SnapshotAccumulator(
                event=event,
                market=market,
                snapshot=snapshot,
                bookmaker=bookmaker,
                selection_codes=set(),
            ),
        )
        accumulator.selection_codes.add(selection.code)
    return [
        _Snapshot(
            event_id=row.event.id,
            kickoff_at=_utc(row.event.kickoff_at),
            bookmaker_id=row.bookmaker.id,
            bookmaker=row.bookmaker.name,
            currency=row.market.currency,
            observed_at=_utc(row.snapshot.observed_at),
            source_updated_at=(
                _utc(row.snapshot.source_updated_at)
                if row.snapshot.source_updated_at is not None
                else None
            ),
            is_closing=row.snapshot.is_closing,
            selection_codes=frozenset(row.selection_codes),
        )
        for row in grouped.values()
    ]


def _final_result_events(session: Session, event_ids: list[int], reference: datetime) -> int:
    if not event_ids:
        return 0
    value = session.scalar(
        select(func.count(func.distinct(MatchResult.event_id)))
        .join(Provider, Provider.id == MatchResult.provider_id)
        .where(
            MatchResult.event_id.in_(event_ids),
            MatchResult.is_final.is_(True),
            MatchResult.observed_at <= reference,
            MatchResult.settled_at <= reference,
            Provider.is_demo.is_(False),
        )
    )
    return int(value or 0)


def _prediction_events(
    session: Session,
    events: Sequence[Event],
    model_id: int,
    decision_lead: timedelta,
    reference: datetime,
) -> int:
    if not events:
        return 0
    by_id = {event.id: event for event in events}
    rows = session.scalars(
        select(ModelEventOutput).where(
            ModelEventOutput.model_version_id == model_id,
            ModelEventOutput.event_id.in_(by_id),
        )
    ).all()
    return len(
        {
            row.event_id
            for row in rows
            if _utc(row.inputs_as_of) <= _utc(row.predicted_at)
            and _utc(row.predicted_at) <= reference
            and _utc(row.predicted_at) <= _utc(by_id[row.event_id].kickoff_at) - decision_lead
        }
    )


def _retain_latest(
    values: dict[tuple[int, int], _Snapshot],
    snapshot: _Snapshot,
) -> None:
    key = (snapshot.event_id, snapshot.bookmaker_id)
    existing = values.get(key)
    if existing is None or snapshot.observed_at > existing.observed_at:
        values[key] = snapshot


def _event_bookmakers(
    values: dict[tuple[int, int], _Snapshot],
) -> dict[int, set[int]]:
    result: dict[int, set[int]] = {}
    for event_id, bookmaker_id in values:
        result.setdefault(event_id, set()).add(bookmaker_id)
    return result


def _has_cost_profile(
    snapshot: _Snapshot,
    *,
    decision_cutoff: datetime,
    tax_rows: Sequence[tuple[BookmakerTaxProfile, TaxProfile]],
    constraints: Sequence[BookmakerConstraint],
) -> bool:
    tax_ready = any(
        mapping.bookmaker_id == snapshot.bookmaker_id
        and _utc(mapping.valid_from) <= decision_cutoff
        and (mapping.valid_to is None or _utc(mapping.valid_to) > decision_cutoff)
        and profile.currency == snapshot.currency
        and profile.status == "verified"
        and _utc(profile.effective_from) <= decision_cutoff
        and (profile.effective_to is None or _utc(profile.effective_to) > decision_cutoff)
        and _utc(profile.verified_at) <= decision_cutoff
        and bool(profile.source_label.strip())
        for mapping, profile in tax_rows
    )
    constraint_ready = any(
        constraint.bookmaker_id == snapshot.bookmaker_id
        and constraint.currency == snapshot.currency
        and _utc(constraint.observed_at) <= decision_cutoff
        and constraint.maximum_stake is not None
        and bool(constraint.source_label.strip())
        for constraint in constraints
    )
    return tax_ready and constraint_ready


def _object(values: dict[str, object], key: str) -> dict[str, object]:
    value = values.get(key)
    if not isinstance(value, dict) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"market edge contract field {key} is invalid")
    return cast(dict[str, object], value)


def _string(values: dict[str, object], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"market edge contract field {key} is invalid")
    return value


def _integer(values: dict[str, object], key: str) -> int:
    value = values.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"market edge contract field {key} is invalid")
    return value


def _number(values: dict[str, object], key: str) -> float:
    value = values.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"market edge contract field {key} is invalid")
    number = float(value)
    if not 0 < number <= 1:
        raise ValueError(f"market edge contract field {key} is invalid")
    return number


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
