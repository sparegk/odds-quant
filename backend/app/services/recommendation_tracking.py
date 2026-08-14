from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Bookmaker,
    Event,
    Market,
    MatchResult,
    ModelEventOutput,
    ModelPrediction,
    ModelVersion,
    OddsPrice,
    OddsSnapshot,
    RecommendationSnapshot,
    RecommendationTrackingState,
    Selection,
    ValueSignal,
)
from app.quant.match_suggestions import bookmaker_code
from app.quant.odds import closing_line_value
from app.quant.settlement import profit_units, settle
from app.schemas.matchday import RecommendationQualityView
from app.schemas.recommendations import (
    RecommendationSnapshotView,
    RecommendationTrackingView,
)
from app.services.betting_costs import resolve_quote_cost_evidence
from app.services.matchday import get_matchday_event_detail


class RecommendationTrackingError(ValueError):
    pass


def capture_recommendation(
    session: Session,
    *,
    signal_id: int,
    captured_at: datetime | None = None,
) -> RecommendationSnapshotView:
    existing = session.scalar(
        select(RecommendationSnapshot).where(RecommendationSnapshot.signal_id == signal_id)
    )
    if existing is not None:
        return _snapshot_view(session, existing)

    reference = _utc(captured_at or datetime.now(UTC))
    signal = session.get(ValueSignal, signal_id)
    if signal is None:
        raise RecommendationTrackingError("value signal was not found")
    event = session.get(Event, signal.event_id)
    selection = session.get(Selection, signal.selection_id)
    bookmaker = session.get(Bookmaker, signal.bookmaker_id)
    taken_snapshot = session.get(OddsSnapshot, signal.odds_snapshot_id)
    prediction = session.get(ModelPrediction, signal.prediction_id)
    if None in (event, selection, bookmaker, taken_snapshot, prediction):
        raise RecommendationTrackingError("recommendation provenance is incomplete")
    assert event is not None
    assert selection is not None
    assert bookmaker is not None
    assert taken_snapshot is not None
    assert prediction is not None
    market = session.get(Market, selection.market_id)
    output = session.get(ModelEventOutput, prediction.output_id)
    if market is None or output is None:
        raise RecommendationTrackingError("market or model-output provenance is missing")
    model = session.get(ModelVersion, output.model_version_id)
    if model is None or signal.evaluation_run_id is None:
        raise RecommendationTrackingError("validated model provenance is missing")
    kickoff = _utc(event.kickoff_at)
    if reference >= kickoff:
        raise RecommendationTrackingError("recommendations must be captured before kickoff")

    code = bookmaker_code(bookmaker.name)
    if code is None:
        raise RecommendationTrackingError("bookmaker is not supported for recommendations")
    detail = get_matchday_event_detail(
        session,
        event_id=event.id,
        as_of=reference,
        selected_bookmakers={code},
    )
    suggestion = (
        next(
            (
                item
                for item in detail.suggestions
                if detail is not None
                and item.source_kind == "single"
                and item.source_id == signal.id
            ),
            None,
        )
        if detail is not None
        else None
    )
    if suggestion is None:
        raise RecommendationTrackingError(
            "signal is not an executable recommendation at the requested capture time"
        )

    cost_evidence = resolve_quote_cost_evidence(
        session,
        bookmaker_id=bookmaker.id,
        bookmaker_name=bookmaker.name,
        currency=market.currency,
        reference=reference,
    )
    if (
        cost_evidence.blockers
        or cost_evidence.tax_profile_id is None
        or cost_evidence.tax_verified_at is None
        or cost_evidence.constraint_observed_at is None
    ):
        raise RecommendationTrackingError("exact cost provenance is incomplete")

    quality = suggestion.recommendation_quality.model_dump()
    payload = {
        "signal_id": signal.id,
        "captured_at": reference.isoformat(),
        "kickoff_at": kickoff.isoformat(),
        "odds_snapshot_id": signal.odds_snapshot_id,
        "price_observed_at": _utc(suggestion.price_observed_at).isoformat(),
        "prediction_id": signal.prediction_id,
        "model_version_id": model.id,
        "evaluation_run_id": signal.evaluation_run_id,
        "model_input_fingerprint": model.data_fingerprint,
        "feature_version": model.feature_version,
        "tax_profile_id": cost_evidence.tax_profile_id,
        "tax_profile_verified_at": cost_evidence.tax_verified_at.isoformat(),
        "constraint_observed_at": cost_evidence.constraint_observed_at.isoformat(),
        "offered_odds": suggestion.offered_odds,
        "lower_net_expected_value": suggestion.lower_net_expected_value,
        "recommendation_quality": quality,
    }
    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    stored = RecommendationSnapshot(
        signal_id=signal.id,
        event_id=event.id,
        selection_id=selection.id,
        bookmaker_id=bookmaker.id,
        odds_snapshot_id=taken_snapshot.id,
        prediction_id=prediction.id,
        model_version_id=model.id,
        evaluation_run_id=signal.evaluation_run_id,
        tax_profile_id=cost_evidence.tax_profile_id,
        captured_at=reference,
        kickoff_at=kickoff,
        price_observed_at=_utc(suggestion.price_observed_at),
        tax_profile_verified_at=cost_evidence.tax_verified_at,
        constraint_observed_at=cost_evidence.constraint_observed_at,
        market_type=market.market_type,
        line=float(market.line) if market.line is not None else None,
        selection_code=selection.code,
        settlement_rule_key=market.settlement_rule_key,
        currency=market.currency,
        offered_odds=suggestion.offered_odds,
        model_probability=suggestion.model_probability,
        lower_probability=suggestion.lower_probability,
        lower_expected_value=suggestion.lower_expected_value,
        net_expected_value=suggestion.net_expected_value,
        lower_net_expected_value=suggestion.lower_net_expected_value,
        stake=suggestion.cost_calculation_stake,
        cash_outlay=suggestion.cost_calculation_cash_outlay,
        minimum_acceptable_odds=suggestion.minimum_odds_for_positive_lower_net_ev,
        recommendation_quality=quality,
        model_input_fingerprint=model.data_fingerprint,
        feature_version=model.feature_version,
        fingerprint=fingerprint,
    )
    session.add(stored)
    session.flush()
    session.add(
        RecommendationTrackingState(
            recommendation_id=stored.id,
            closing_line_status="PENDING",
            settlement_status="PENDING",
            updated_at=reference,
        )
    )
    session.commit()
    return _snapshot_view(session, stored)


def list_recommendation_snapshots(
    session: Session, *, limit: int = 200
) -> list[RecommendationSnapshotView]:
    rows = session.scalars(
        select(RecommendationSnapshot)
        .order_by(RecommendationSnapshot.captured_at.desc(), RecommendationSnapshot.id.desc())
        .limit(limit)
    ).all()
    return [_snapshot_view(session, row) for row in rows]


def refresh_recommendation(
    session: Session,
    *,
    recommendation_id: int,
    as_of: datetime | None = None,
) -> RecommendationSnapshotView:
    reference = _utc(as_of or datetime.now(UTC))
    snapshot = session.get(RecommendationSnapshot, recommendation_id)
    if snapshot is None:
        raise RecommendationTrackingError("recommendation snapshot was not found")
    state = session.get(RecommendationTrackingState, recommendation_id)
    if state is None:
        raise RecommendationTrackingError("recommendation tracking state is missing")
    if reference < _utc(snapshot.captured_at):
        raise RecommendationTrackingError("refresh cutoff predates the decision snapshot")

    if reference >= _utc(snapshot.kickoff_at):
        _refresh_closing_line(session, snapshot, state, reference)
        _refresh_settlement(session, snapshot, state, reference)
    state.updated_at = reference
    session.commit()
    return _snapshot_view(session, snapshot)


def _refresh_closing_line(
    session: Session,
    snapshot: RecommendationSnapshot,
    state: RecommendationTrackingState,
    reference: datetime,
) -> None:
    taken = session.get(OddsSnapshot, snapshot.odds_snapshot_id)
    selection = session.get(Selection, snapshot.selection_id)
    if taken is None or selection is None:
        raise RecommendationTrackingError("closing-line provenance is incomplete")
    candidate = session.execute(
        select(OddsSnapshot, OddsPrice)
        .join(OddsPrice, OddsPrice.snapshot_id == OddsSnapshot.id)
        .where(
            OddsSnapshot.market_id == selection.market_id,
            OddsSnapshot.bookmaker_id == snapshot.bookmaker_id,
            OddsSnapshot.provider_id == taken.provider_id,
            OddsSnapshot.is_closing.is_(True),
            OddsSnapshot.is_complete.is_(True),
            OddsSnapshot.observed_at < snapshot.kickoff_at,
            OddsSnapshot.ingested_at <= reference,
            OddsPrice.selection_id == snapshot.selection_id,
        )
        .order_by(OddsSnapshot.observed_at.desc(), OddsSnapshot.id.desc())
    ).first()
    if candidate is None:
        state.closing_line_status = "UNAVAILABLE"
        return
    closing_snapshot, price = candidate
    if closing_snapshot.source_updated_at is not None and _utc(
        closing_snapshot.source_updated_at
    ) >= _utc(snapshot.kickoff_at):
        state.closing_line_status = "UNAVAILABLE"
        return
    closing_odds = float(price.decimal_odds)
    state.closing_line_status = "AVAILABLE"
    state.closing_odds_snapshot_id = closing_snapshot.id
    state.closing_odds = closing_odds
    state.closing_observed_at = _utc(closing_snapshot.observed_at)
    state.closing_recorded_at = reference
    state.closing_line_value = closing_line_value(snapshot.offered_odds, closing_odds)


def _refresh_settlement(
    session: Session,
    snapshot: RecommendationSnapshot,
    state: RecommendationTrackingState,
    reference: datetime,
) -> None:
    result = session.scalar(
        select(MatchResult)
        .where(
            MatchResult.event_id == snapshot.event_id,
            MatchResult.is_final.is_(True),
            MatchResult.observed_at <= reference,
        )
        .order_by(MatchResult.observed_at.desc(), MatchResult.id.desc())
    )
    if result is None:
        return
    outcome = settle(
        result.home_goals,
        result.away_goals,
        snapshot.market_type,
        snapshot.selection_code,
        snapshot.line,
    )
    state.settlement_status = "SETTLED"
    state.result_id = result.id
    state.settlement = outcome.value
    state.settled_at = _utc(result.settled_at)
    state.profit_units = profit_units(outcome, snapshot.offered_odds, snapshot.stake)


def _snapshot_view(
    session: Session, snapshot: RecommendationSnapshot
) -> RecommendationSnapshotView:
    state = session.get(RecommendationTrackingState, snapshot.id)
    if state is None:
        raise RecommendationTrackingError("recommendation tracking state is missing")
    return RecommendationSnapshotView(
        id=snapshot.id,
        signal_id=snapshot.signal_id,
        event_id=snapshot.event_id,
        selection_id=snapshot.selection_id,
        bookmaker_id=snapshot.bookmaker_id,
        odds_snapshot_id=snapshot.odds_snapshot_id,
        prediction_id=snapshot.prediction_id,
        model_version_id=snapshot.model_version_id,
        evaluation_run_id=snapshot.evaluation_run_id,
        tax_profile_id=snapshot.tax_profile_id,
        captured_at=_utc(snapshot.captured_at),
        kickoff_at=_utc(snapshot.kickoff_at),
        price_observed_at=_utc(snapshot.price_observed_at),
        tax_profile_verified_at=_utc(snapshot.tax_profile_verified_at),
        constraint_observed_at=_utc(snapshot.constraint_observed_at),
        market_type=snapshot.market_type,
        line=snapshot.line,
        selection_code=snapshot.selection_code,
        settlement_rule_key=snapshot.settlement_rule_key,
        currency=snapshot.currency,
        offered_odds=snapshot.offered_odds,
        model_probability=snapshot.model_probability,
        lower_probability=snapshot.lower_probability,
        lower_expected_value=snapshot.lower_expected_value,
        net_expected_value=snapshot.net_expected_value,
        lower_net_expected_value=snapshot.lower_net_expected_value,
        stake=snapshot.stake,
        cash_outlay=snapshot.cash_outlay,
        minimum_acceptable_odds=snapshot.minimum_acceptable_odds,
        recommendation_quality=RecommendationQualityView(**snapshot.recommendation_quality),
        model_input_fingerprint=snapshot.model_input_fingerprint,
        feature_version=snapshot.feature_version,
        fingerprint=snapshot.fingerprint,
        tracking=RecommendationTrackingView(
            closing_line_status=state.closing_line_status,
            closing_odds_snapshot_id=state.closing_odds_snapshot_id,
            closing_odds=state.closing_odds,
            closing_observed_at=(
                _utc(state.closing_observed_at) if state.closing_observed_at else None
            ),
            closing_recorded_at=(
                _utc(state.closing_recorded_at) if state.closing_recorded_at else None
            ),
            closing_line_value=state.closing_line_value,
            settlement_status=state.settlement_status,
            result_id=state.result_id,
            settlement=state.settlement,
            settled_at=_utc(state.settled_at) if state.settled_at else None,
            profit_units=state.profit_units,
            updated_at=_utc(state.updated_at),
        ),
    )


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
