from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    BacktestResult,
    BacktestRun,
    Bookmaker,
    Event,
    Market,
    ModelEventOutput,
    ModelPrediction,
    ModelVersion,
    OddsPrice,
    OddsSnapshot,
    Provider,
    Selection,
    ValueSignal,
)
from app.quant.odds import devig_proportional, implied_probability
from app.schemas.signals import GenerateSignalsRequest, SignalBatchView, ValueSignalView
from app.signals.policy import SignalInput, classify_signal


class SignalGenerationError(ValueError):
    pass


@dataclass(frozen=True)
class _SnapshotPrices:
    snapshot: OddsSnapshot
    bookmaker: Bookmaker
    prices: dict[int, float]
    fair_probabilities: dict[int, float]


def generate_value_signals(
    session: Session,
    request: GenerateSignalsRequest,
    *,
    now: datetime | None = None,
) -> SignalBatchView:
    output = session.get(ModelEventOutput, request.output_id)
    if output is None:
        raise SignalGenerationError("model output not found")
    model = session.get(ModelVersion, output.model_version_id)
    event = session.get(Event, output.event_id)
    if model is None or event is None:
        raise SignalGenerationError("prediction provenance is incomplete")
    generated_at = _utc(request.generated_at or now or datetime.now(UTC))
    if generated_at < _utc(output.predicted_at):
        raise SignalGenerationError("signals cannot be generated before the prediction")
    if generated_at >= _utc(event.kickoff_at):
        raise SignalGenerationError("signals must be generated before kickoff")
    if model.is_demo or event.is_demo:
        raise SignalGenerationError("demo models or events cannot generate value signals")
    if model.evaluation_status != "calibrated":
        raise SignalGenerationError("model is not calibrated")

    evaluation, calibration_error = _calibration_evidence(
        session, model.id, _utc(output.inputs_as_of)
    )
    existing = _signals_for_output_at(session, output.id, generated_at)
    if existing:
        return _batch_view(
            session=session,
            event_id=event.id,
            output_id=output.id,
            model_version_id=model.id,
            evaluation_run_id=evaluation.id,
            generated_at=generated_at,
            signals=existing,
        )

    prediction_rows = session.execute(
        select(ModelPrediction, Selection, Market)
        .join(Selection, Selection.id == ModelPrediction.selection_id)
        .join(Market, Market.id == Selection.market_id)
        .where(ModelPrediction.output_id == output.id)
        .order_by(Market.id, Selection.id)
    ).all()
    by_market: dict[int, list[tuple[ModelPrediction, Selection, Market]]] = defaultdict(list)
    for prediction, selection, market in prediction_rows:
        by_market[market.id].append((prediction, selection, market))
    if not by_market:
        raise SignalGenerationError("model output has no supported market predictions")

    sample_size_per_team = _venue_sample_size(model.config, event)
    created: list[ValueSignal] = []
    for rows in by_market.values():
        market = rows[0][2]
        snapshots = _latest_compatible_snapshots(session, market, generated_at=generated_at)
        if not snapshots:
            continue
        fresh_snapshots = [
            snapshot
            for snapshot in snapshots
            if (generated_at - _utc(snapshot.snapshot.observed_at)).total_seconds() <= 60 * 60
        ]
        analysis_snapshots = fresh_snapshots or snapshots
        consensus = {
            selection_id: sum(
                snapshot.fair_probabilities[selection_id] for snapshot in analysis_snapshots
            )
            / len(analysis_snapshots)
            for selection_id in analysis_snapshots[0].fair_probabilities
        }
        for prediction, selection, _ in rows:
            if selection.id not in consensus:
                continue
            best = max(
                analysis_snapshots,
                key=lambda snapshot: (
                    snapshot.prices[selection.id],
                    _utc(snapshot.snapshot.observed_at),
                    snapshot.snapshot.id,
                ),
            )
            offered_odds = best.prices[selection.id]
            age_minutes = max(
                0.0,
                (generated_at - _utc(best.snapshot.observed_at)).total_seconds() / 60,
            )
            odds_move_ratio, implied_move_points = _price_movement(
                session,
                market_id=market.id,
                bookmaker_id=best.bookmaker.id,
                selection_id=selection.id,
                current_snapshot=best.snapshot,
                current_odds=offered_odds,
            )
            classified = classify_signal(
                SignalInput(
                    offered_odds=offered_odds,
                    market_probability=consensus[selection.id],
                    model_probability=prediction.probability,
                    lower_probability=prediction.lower_probability,
                    sample_size_per_team=sample_size_per_team,
                    calibration_error=calibration_error,
                    age_minutes=age_minutes,
                    bookmaker_count=len(analysis_snapshots),
                    odds_move_ratio=odds_move_ratio,
                    implied_move_points=implied_move_points,
                )
            )
            reasons = list(_string_list(classified, "reasons"))
            reasons.extend(
                [
                    f"Best compatible price is {offered_odds:.2f} at {best.bookmaker.name}.",
                    (
                        f"Market consensus uses {len(analysis_snapshots)} latest complete "
                        "bookmaker snapshot(s)."
                    ),
                    f"Calibration evidence is evaluation run {evaluation.id}.",
                ]
            )
            signal = ValueSignal(
                event_id=event.id,
                selection_id=selection.id,
                bookmaker_id=best.bookmaker.id,
                odds_snapshot_id=best.snapshot.id,
                prediction_id=prediction.id,
                evaluation_run_id=evaluation.id,
                signal_type=_string(classified, "signal"),
                offered_odds=offered_odds,
                raw_implied_probability=implied_probability(offered_odds),
                market_fair_probability=consensus[selection.id],
                model_probability=prediction.probability,
                expected_value=_number(classified, "expected_value"),
                lower_expected_value=_number(classified, "lower_expected_value"),
                probability_edge=_number(classified, "edge"),
                confidence=_number(classified, "confidence"),
                calibration_error=calibration_error,
                odds_age_minutes=age_minutes,
                bookmaker_count=len(analysis_snapshots),
                odds_move_ratio=odds_move_ratio,
                implied_move_points=implied_move_points,
                generated_at=generated_at,
                reasons=reasons,
                risks=list(_string_list(classified, "risks")),
            )
            session.add(signal)
            created.append(signal)
    if not created:
        raise SignalGenerationError(
            "no complete non-demo compatible odds snapshots exist for this prediction"
        )
    session.commit()
    return _batch_view(
        session=session,
        event_id=event.id,
        output_id=output.id,
        model_version_id=model.id,
        evaluation_run_id=evaluation.id,
        generated_at=generated_at,
        signals=created,
    )


def list_value_signals(
    session: Session,
    *,
    event_id: int | None = None,
    output_id: int | None = None,
    signal_type: str | None = None,
    limit: int = 200,
) -> list[ValueSignalView]:
    statement = (
        select(ValueSignal)
        .join(ModelPrediction, ModelPrediction.id == ValueSignal.prediction_id)
        .join(ModelEventOutput, ModelEventOutput.id == ModelPrediction.output_id)
        .order_by(
            ValueSignal.generated_at.desc(),
            ValueSignal.expected_value.desc(),
            ValueSignal.id.desc(),
        )
        .limit(limit)
    )
    if event_id is not None:
        statement = statement.where(ValueSignal.event_id == event_id)
    if output_id is not None:
        statement = statement.where(ModelEventOutput.id == output_id)
    if signal_type is not None:
        statement = statement.where(ValueSignal.signal_type == signal_type)
    return [_signal_view(session, signal) for signal in session.scalars(statement).all()]


def list_underdog_signals(session: Session, *, limit: int = 50) -> list[ValueSignalView]:
    candidates = list_value_signals(session, limit=1000)
    ranked = [
        signal
        for signal in candidates
        if signal.selection_code in {"HOME", "AWAY"}
        and signal.offered_odds >= 2
        and signal.expected_value > 0
        and signal.signal_type in {"VALUE", "WATCH"}
    ]
    return sorted(
        ranked,
        key=lambda signal: (
            signal.signal_type == "VALUE",
            signal.expected_value,
            signal.confidence,
        ),
        reverse=True,
    )[:limit]


def _calibration_evidence(
    session: Session, model_id: int, inputs_as_of: datetime
) -> tuple[BacktestRun, float]:
    run = session.scalar(
        select(BacktestRun)
        .where(
            BacktestRun.model_version_id == model_id,
            BacktestRun.status == "completed",
            BacktestRun.evaluation_status == "calibrated",
            BacktestRun.is_demo.is_(False),
            BacktestRun.test_end <= inputs_as_of,
        )
        .order_by(BacktestRun.test_end.desc(), BacktestRun.id.desc())
    )
    if run is None:
        raise SignalGenerationError(
            "no non-demo calibrated evaluation predates the prediction input cutoff"
        )
    result = session.scalar(
        select(BacktestResult).where(
            BacktestResult.run_id == run.id,
            BacktestResult.benchmark == "poisson",
            BacktestResult.dimension == "overall",
            BacktestResult.dimension_value == "all",
        )
    )
    if result is None:
        raise SignalGenerationError("calibration run has no overall Poisson metrics")
    calibration_error = result.metrics.get("expected_calibration_error")
    if isinstance(calibration_error, bool) or not isinstance(calibration_error, (int, float)):
        raise SignalGenerationError("calibration run has no valid calibration error")
    if calibration_error < 0:
        raise SignalGenerationError("calibration error cannot be negative")
    return run, float(calibration_error)


def _latest_compatible_snapshots(
    session: Session,
    market: Market,
    *,
    generated_at: datetime,
) -> list[_SnapshotPrices]:
    expected_selection_ids = set(
        session.scalars(
            select(Selection.id).where(Selection.market_id == market.id).order_by(Selection.id)
        ).all()
    )
    rows = session.execute(
        select(OddsSnapshot, Bookmaker, OddsPrice, Selection)
        .join(Bookmaker, Bookmaker.id == OddsSnapshot.bookmaker_id)
        .join(Provider, Provider.id == OddsSnapshot.provider_id)
        .join(OddsPrice, OddsPrice.snapshot_id == OddsSnapshot.id)
        .join(Selection, Selection.id == OddsPrice.selection_id)
        .where(
            OddsSnapshot.market_id == market.id,
            OddsSnapshot.is_complete.is_(True),
            OddsSnapshot.observed_at <= generated_at,
            Provider.is_demo.is_(False),
            Bookmaker.is_demo.is_(False),
        )
        .order_by(OddsSnapshot.observed_at, OddsSnapshot.id, Selection.id)
    ).all()
    grouped: dict[int, tuple[OddsSnapshot, Bookmaker, dict[int, float]]] = {}
    for snapshot, bookmaker, price, selection in rows:
        stored = grouped.setdefault(snapshot.id, (snapshot, bookmaker, {}))
        stored[2][selection.id] = float(price.decimal_odds)

    latest_by_bookmaker: dict[int, tuple[OddsSnapshot, Bookmaker, dict[int, float]]] = {}
    for snapshot, bookmaker, prices in grouped.values():
        if set(prices) != expected_selection_ids:
            continue
        existing = latest_by_bookmaker.get(bookmaker.id)
        if existing is None or (
            _utc(snapshot.observed_at),
            snapshot.id,
        ) > (_utc(existing[0].observed_at), existing[0].id):
            latest_by_bookmaker[bookmaker.id] = (snapshot, bookmaker, prices)

    results: list[_SnapshotPrices] = []
    for snapshot, bookmaker, prices in latest_by_bookmaker.values():
        ordered_ids = sorted(prices)
        fair = devig_proportional([prices[selection_id] for selection_id in ordered_ids])
        results.append(
            _SnapshotPrices(
                snapshot=snapshot,
                bookmaker=bookmaker,
                prices=prices,
                fair_probabilities=dict(zip(ordered_ids, fair, strict=True)),
            )
        )
    return sorted(results, key=lambda value: value.bookmaker.id)


def _price_movement(
    session: Session,
    *,
    market_id: int,
    bookmaker_id: int,
    selection_id: int,
    current_snapshot: OddsSnapshot,
    current_odds: float,
) -> tuple[float, float]:
    previous = session.execute(
        select(OddsPrice.decimal_odds)
        .join(OddsSnapshot, OddsSnapshot.id == OddsPrice.snapshot_id)
        .join(Provider, Provider.id == OddsSnapshot.provider_id)
        .where(
            OddsSnapshot.market_id == market_id,
            OddsSnapshot.bookmaker_id == bookmaker_id,
            OddsSnapshot.is_complete.is_(True),
            OddsSnapshot.observed_at < current_snapshot.observed_at,
            OddsPrice.selection_id == selection_id,
            Provider.is_demo.is_(False),
        )
        .order_by(OddsSnapshot.observed_at.desc(), OddsSnapshot.id.desc())
        .limit(1)
    ).one_or_none()
    if previous is None:
        return (0.0, 0.0)
    previous_odds = float(previous[0])
    return (
        abs(current_odds / previous_odds - 1),
        abs(implied_probability(current_odds) - implied_probability(previous_odds)),
    )


def _venue_sample_size(config: dict[str, object], event: Event) -> int:
    teams = config.get("teams")
    if not isinstance(teams, dict):
        raise SignalGenerationError("model configuration has no team parameters")
    home = teams.get(str(event.home_team_id))
    away = teams.get(str(event.away_team_id))
    if not isinstance(home, dict) or not isinstance(away, dict):
        raise SignalGenerationError("event teams are absent from the model configuration")
    home_matches = home.get("home_matches")
    away_matches = away.get("away_matches")
    if (
        isinstance(home_matches, bool)
        or not isinstance(home_matches, int)
        or isinstance(away_matches, bool)
        or not isinstance(away_matches, int)
    ):
        raise SignalGenerationError("model venue sample sizes are invalid")
    return min(home_matches, away_matches)


def _signals_for_output_at(
    session: Session, output_id: int, generated_at: datetime
) -> list[ValueSignal]:
    return list(
        session.scalars(
            select(ValueSignal)
            .join(ModelPrediction, ModelPrediction.id == ValueSignal.prediction_id)
            .where(
                ModelPrediction.output_id == output_id,
                ValueSignal.generated_at == generated_at,
            )
            .order_by(ValueSignal.expected_value.desc(), ValueSignal.id)
        ).all()
    )


def _signal_view(session: Session, signal: ValueSignal) -> ValueSignalView:
    prediction = session.get(ModelPrediction, signal.prediction_id)
    selection = session.get(Selection, signal.selection_id)
    bookmaker = session.get(Bookmaker, signal.bookmaker_id)
    if prediction is None or selection is None or bookmaker is None:
        raise SignalGenerationError("stored signal provenance is incomplete")
    output = session.get(ModelEventOutput, prediction.output_id)
    market = session.get(Market, selection.market_id)
    if output is None or market is None:
        raise SignalGenerationError("stored signal prediction provenance is incomplete")
    model = session.get(ModelVersion, output.model_version_id)
    if model is None:
        raise SignalGenerationError("stored signal model provenance is incomplete")
    return ValueSignalView(
        id=signal.id,
        event_id=signal.event_id,
        output_id=output.id,
        model_version_id=model.id,
        model_version=model.version,
        evaluation_run_id=signal.evaluation_run_id,
        prediction_id=prediction.id,
        market_id=market.id,
        market_type=market.market_type,
        line=float(market.line) if market.line is not None else None,
        selection_id=selection.id,
        selection_code=selection.code,
        selection_name=selection.name,
        bookmaker_id=bookmaker.id,
        bookmaker=bookmaker.name,
        odds_snapshot_id=signal.odds_snapshot_id,
        signal_type=signal.signal_type,
        offered_odds=signal.offered_odds,
        raw_implied_probability=signal.raw_implied_probability,
        market_fair_probability=signal.market_fair_probability,
        model_probability=signal.model_probability,
        lower_probability=prediction.lower_probability,
        expected_value=signal.expected_value,
        lower_expected_value=signal.lower_expected_value,
        probability_edge=signal.probability_edge,
        confidence=signal.confidence,
        calibration_error=signal.calibration_error,
        odds_age_minutes=signal.odds_age_minutes,
        bookmaker_count=signal.bookmaker_count,
        odds_move_ratio=signal.odds_move_ratio,
        implied_move_points=signal.implied_move_points,
        generated_at=_utc(signal.generated_at),
        reasons=signal.reasons,
        risks=signal.risks,
    )


def _batch_view(
    session: Session,
    *,
    event_id: int,
    output_id: int,
    model_version_id: int,
    evaluation_run_id: int,
    generated_at: datetime,
    signals: list[ValueSignal],
) -> SignalBatchView:
    return SignalBatchView(
        event_id=event_id,
        output_id=output_id,
        model_version_id=model_version_id,
        evaluation_run_id=evaluation_run_id,
        generated_at=generated_at,
        signals=[
            _signal_view(session, signal)
            for signal in sorted(
                signals, key=lambda value: (value.expected_value, value.id), reverse=True
            )
        ],
    )


def _string(values: dict[str, object], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str):
        raise SignalGenerationError(f"signal policy field {key} is invalid")
    return value


def _number(values: dict[str, object], key: str) -> float:
    value = values.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SignalGenerationError(f"signal policy field {key} is invalid")
    return float(value)


def _string_list(values: dict[str, object], key: str) -> list[str]:
    value = values.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise SignalGenerationError(f"signal policy field {key} is invalid")
    return value


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
