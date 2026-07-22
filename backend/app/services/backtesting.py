from __future__ import annotations

import hashlib
import json
import math
import statistics
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    BacktestObservation,
    BacktestResult,
    BacktestRun,
    Bookmaker,
    Event,
    Market,
    MatchResult,
    ModelEventOutput,
    ModelPrediction,
    ModelVersion,
    OddsPrice,
    OddsSnapshot,
    Provider,
    Selection,
    ValueSignal,
)
from app.quant.bankroll import BankrollBet, simulate_bankroll
from app.quant.odds import closing_line_value
from app.quant.settlement import profit_units, settle
from app.schemas.backtesting import (
    BankrollPointView,
    BankrollSimulationView,
    RunSignalBacktestRequest,
    SignalBacktestObservationView,
    SignalBacktestView,
    SimulateBankrollRequest,
)


class BacktestingError(ValueError):
    pass


SignalRow = tuple[
    ValueSignal,
    Event,
    Selection,
    Market,
    ModelPrediction,
    ModelEventOutput,
    OddsSnapshot,
    Bookmaker,
    Provider,
]
SettledSignalRow = tuple[
    ValueSignal,
    Event,
    Selection,
    Market,
    ModelPrediction,
    ModelEventOutput,
    OddsSnapshot,
    Bookmaker,
    Provider,
    MatchResult,
]


def run_signal_backtest(
    session: Session,
    request: RunSignalBacktestRequest,
    *,
    now: datetime | None = None,
) -> SignalBacktestView:
    reference = _utc(now or datetime.now(UTC))
    start = _utc(request.evaluation_start)
    end = _utc(request.evaluation_end)
    if end > reference:
        raise BacktestingError("evaluation_end cannot be in the future")
    model = session.get(ModelVersion, request.model_version_id)
    if model is None:
        raise BacktestingError("model version not found")
    if start < _utc(model.training_end):
        raise BacktestingError("evaluation window begins before the model training cutoff")

    rows = session.execute(
        select(
            ValueSignal,
            Event,
            Selection,
            Market,
            ModelPrediction,
            ModelEventOutput,
            OddsSnapshot,
            Bookmaker,
            Provider,
        )
        .join(Selection, Selection.id == ValueSignal.selection_id)
        .join(Market, Market.id == Selection.market_id)
        .join(Event, Event.id == ValueSignal.event_id)
        .join(ModelPrediction, ModelPrediction.id == ValueSignal.prediction_id)
        .join(ModelEventOutput, ModelEventOutput.id == ModelPrediction.output_id)
        .join(OddsSnapshot, OddsSnapshot.id == ValueSignal.odds_snapshot_id)
        .join(Bookmaker, Bookmaker.id == ValueSignal.bookmaker_id)
        .join(Provider, Provider.id == OddsSnapshot.provider_id)
        .where(
            ModelEventOutput.model_version_id == model.id,
            Event.kickoff_at >= start,
            Event.kickoff_at < end,
            ValueSignal.signal_type.in_(request.signal_types),
            ValueSignal.generated_at < Event.kickoff_at,
        )
        .order_by(ValueSignal.generated_at, ValueSignal.id)
    ).all()
    latest: dict[tuple[int, int], SignalRow] = {}
    for row in rows:
        typed_row = cast(SignalRow, tuple(row))
        signal = typed_row[0]
        key = (signal.event_id, signal.selection_id)
        latest[key] = typed_row
    if not latest:
        raise BacktestingError("no stored signals are eligible in the evaluation window")

    event_ids = sorted({key[0] for key in latest})
    result_rows = session.execute(
        select(MatchResult)
        .where(
            MatchResult.event_id.in_(event_ids),
            MatchResult.is_final.is_(True),
            MatchResult.observed_at <= reference,
            MatchResult.settled_at <= reference,
        )
        .order_by(MatchResult.observed_at, MatchResult.id)
    ).scalars()
    latest_results: dict[int, MatchResult] = {}
    for candidate_result in result_rows:
        latest_results[candidate_result.event_id] = candidate_result

    eligible: list[SettledSignalRow] = []
    for raw in latest.values():
        (
            signal,
            event,
            selection,
            market,
            prediction,
            output,
            snapshot,
            bookmaker,
            provider,
        ) = raw
        settled_result = latest_results.get(event.id)
        if settled_result is None:
            continue
        generated_at = _utc(signal.generated_at)
        if (
            _utc(output.inputs_as_of) > generated_at
            or _utc(output.predicted_at) > generated_at
            or _utc(snapshot.observed_at) > generated_at
            or _utc(snapshot.ingested_at) > generated_at
        ):
            raise BacktestingError("stored signal contains post-cutoff evidence")
        eligible.append(
            (
                signal,
                event,
                selection,
                market,
                prediction,
                output,
                snapshot,
                bookmaker,
                provider,
                settled_result,
            )
        )
    if not eligible:
        raise BacktestingError("eligible signals have no final results known by the cutoff")
    eligible.sort(key=lambda row: (_utc(row[1].kickoff_at), row[0].id))
    closing_prices = {
        row[0].id: closing
        for row in eligible
        if (closing := _closing_price(session, row, reference)) is not None
    }

    is_demo = bool(
        model.is_demo
        or any(
            event.is_demo or bookmaker.is_demo or provider.is_demo
            for _, event, _, _, _, _, _, bookmaker, provider, _ in eligible
        )
    )
    fingerprint = _backtest_fingerprint(model, request, reference, eligible, closing_prices)
    existing = session.scalar(select(BacktestRun).where(BacktestRun.fingerprint == fingerprint))
    if existing is not None:
        return _backtest_view(session, existing)

    evaluation_status = "demo_only" if is_demo else "research_only"
    policy: dict[str, object] = {
        "version": "stored-value-signal-replay-v3",
        "decision": evaluation_status,
        "one_latest_signal_per_event_selection": True,
        "unit_stake": True,
        "profitability_claim_allowed": False,
        "closing_line_value_required_for_promotion": True,
    }
    config: dict[str, object] = {
        "evaluation_kind": "stored_value_signal_returns",
        "metrics_version": "recommendation-returns-v3",
        "evaluation_start": start.isoformat(),
        "evaluation_end": end.isoformat(),
        "result_known_at": reference.isoformat(),
        "signal_types": request.signal_types,
        "model_data_fingerprint": model.data_fingerprint,
        "feature_version": model.feature_version,
    }
    run = BacktestRun(
        model_version_id=model.id,
        status="completed",
        train_end=_utc(model.training_end),
        validation_end=start,
        test_end=end,
        fingerprint=fingerprint,
        config=config,
        policy=policy,
        evaluation_status=evaluation_status,
        is_demo=is_demo,
    )
    session.add(run)
    session.flush()
    profits: list[float] = []
    expected_values: list[float] = []
    offered_odds: list[float] = []
    model_probabilities: list[float] = []
    closing_line_values: list[float | None] = []
    for signal, event, selection, market, prediction, output, snapshot, _, _, result in eligible:
        line = float(market.line) if market.line is not None else None
        settlement = settle(
            result.home_goals,
            result.away_goals,
            market.market_type,
            selection.code,
            line,
        )
        profit = profit_units(settlement, signal.offered_odds)
        profits.append(profit)
        expected_values.append(signal.expected_value)
        offered_odds.append(signal.offered_odds)
        model_probabilities.append(signal.model_probability)
        closing = closing_prices.get(signal.id)
        closing_snapshot, closing_price = closing if closing is not None else (None, None)
        clv = (
            closing_line_value(signal.offered_odds, float(closing_price.decimal_odds))
            if closing_price is not None
            else None
        )
        closing_line_values.append(clv)
        probability_evidence = {
            "model_probability": signal.model_probability,
            "lower_probability": prediction.lower_probability,
            "expected_value": signal.expected_value,
            "offered_odds": signal.offered_odds,
        }
        if closing_snapshot is not None and closing_price is not None:
            probability_evidence["closing_odds_snapshot_id"] = closing_snapshot.id
            probability_evidence["closing_decimal_odds"] = float(closing_price.decimal_odds)
        session.add(
            BacktestObservation(
                run_id=run.id,
                event_id=event.id,
                selection_id=selection.id,
                odds_snapshot_id=snapshot.id,
                prediction_id=prediction.id,
                result_id=result.id,
                predicted_at=_utc(signal.generated_at),
                training_cutoff=_utc(output.inputs_as_of),
                training_sample_size=output.sample_size,
                training_fingerprint=model.data_fingerprint,
                market_type=market.market_type,
                probabilities=probability_evidence,
                actual_outcome=selection.code,
                brier_score=None,
                log_loss=None,
                market_snapshot_ids=[snapshot.id]
                + ([closing_snapshot.id] if closing_snapshot is not None else []),
                market_probabilities=None,
                market_brier_score=None,
                market_log_loss=None,
                settled_at=_utc(result.settled_at),
                settlement=settlement.value,
                stake=1.0,
                profit_units=profit,
                closing_line_value=clv,
            )
        )
    metrics = _return_metrics(
        profits,
        expected_values,
        offered_odds,
        model_probabilities,
        closing_line_values,
    )
    session.add(
        BacktestResult(
            run_id=run.id,
            benchmark="value_signals",
            dimension="overall",
            dimension_value="all",
            metrics=metrics,
        )
    )
    session.commit()
    return _backtest_view(session, run)


def list_signal_backtests(
    session: Session, *, model_id: int | None = None
) -> list[SignalBacktestView]:
    statement = select(BacktestRun).order_by(BacktestRun.created_at.desc(), BacktestRun.id.desc())
    if model_id is not None:
        statement = statement.where(BacktestRun.model_version_id == model_id)
    runs = [
        run
        for run in session.scalars(statement).all()
        if run.config.get("evaluation_kind") == "stored_value_signal_returns"
    ]
    return [_backtest_view(session, run) for run in runs]


def get_signal_backtest(session: Session, run_id: int) -> SignalBacktestView | None:
    run = session.get(BacktestRun, run_id)
    if run is None or run.config.get("evaluation_kind") != "stored_value_signal_returns":
        return None
    return _backtest_view(session, run)


def simulate_backtest_bankroll(
    session: Session, request: SimulateBankrollRequest
) -> BankrollSimulationView:
    run = session.get(BacktestRun, request.backtest_run_id)
    if run is None or run.config.get("evaluation_kind") != "stored_value_signal_returns":
        raise BacktestingError("signal backtest run not found")
    if run.fingerprint is None:
        raise BacktestingError("backtest run has no reproducibility fingerprint")
    rows = session.execute(
        select(BacktestObservation, Event)
        .join(Event, Event.id == BacktestObservation.event_id)
        .where(BacktestObservation.run_id == run.id)
        .order_by(Event.kickoff_at, BacktestObservation.id)
    ).all()
    bets: list[BankrollBet] = []
    for observation, event in rows:
        probabilities = observation.probabilities or {}
        if observation.profit_units is None:
            continue
        bets.append(
            BankrollBet(
                observation_id=observation.id,
                day=_utc(event.kickoff_at).date(),
                profit_per_unit=observation.profit_units,
                decimal_odds=_number(probabilities, "offered_odds"),
                probability=_number(probabilities, "lower_probability"),
            )
        )
    simulation = simulate_bankroll(
        bets,
        initial_bankroll=request.initial_bankroll,
        strategy=request.strategy,
        flat_stake=request.flat_stake,
        stake_fraction=request.stake_fraction,
        kelly_fraction=request.kelly_fraction,
        maximum_stake_fraction=request.maximum_stake_fraction,
        maximum_daily_exposure_fraction=request.maximum_daily_exposure_fraction,
    )
    simulation_fingerprint = hashlib.sha256(
        json.dumps(
            {"backtest_fingerprint": run.fingerprint, "request": request.model_dump(mode="json")},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    return BankrollSimulationView(
        backtest_run_id=run.id,
        backtest_fingerprint=run.fingerprint,
        simulation_fingerprint=simulation_fingerprint,
        strategy=request.strategy,
        initial_bankroll=request.initial_bankroll,
        final_bankroll=simulation.final_bankroll,
        total_staked=simulation.total_staked,
        net_profit=simulation.net_profit,
        roi=simulation.roi,
        maximum_drawdown=simulation.maximum_drawdown,
        maximum_drawdown_fraction=simulation.maximum_drawdown_fraction,
        bets_placed=simulation.bets_placed,
        bets_skipped=simulation.bets_skipped,
        is_demo=run.is_demo,
        warnings=[
            "This is a deterministic research replay, not a forecast of future returns.",
            "Kelly sizing uses the stored lower probability bound and is capped by "
            "exposure limits.",
            "Closing-line value is unavailable unless timestamped closing prices were stored.",
        ],
        points=[BankrollPointView(**point.__dict__) for point in simulation.points],
    )


def _backtest_view(session: Session, run: BacktestRun) -> SignalBacktestView:
    if run.fingerprint is None:
        raise BacktestingError("stored signal backtest has no fingerprint")
    model = session.get(ModelVersion, run.model_version_id)
    if model is None:
        raise BacktestingError("stored signal backtest model is missing")
    result = session.scalar(
        select(BacktestResult).where(
            BacktestResult.run_id == run.id,
            BacktestResult.benchmark == "value_signals",
            BacktestResult.dimension == "overall",
        )
    )
    if result is None:
        raise BacktestingError("stored signal backtest metrics are missing")
    rows = session.execute(
        select(BacktestObservation, Selection, Market)
        .join(Selection, Selection.id == BacktestObservation.selection_id)
        .join(Market, Market.id == Selection.market_id)
        .where(BacktestObservation.run_id == run.id)
        .order_by(BacktestObservation.predicted_at, BacktestObservation.id)
    ).all()
    observations: list[SignalBacktestObservationView] = []
    for observation, selection, market in rows:
        probabilities = observation.probabilities or {}
        if (
            observation.selection_id is None
            or observation.prediction_id is None
            or observation.odds_snapshot_id is None
            or observation.settled_at is None
            or observation.settlement is None
            or observation.profit_units is None
        ):
            raise BacktestingError("stored signal backtest observation is incomplete")
        closing_snapshot_id = _optional_integer(probabilities, "closing_odds_snapshot_id")
        closing_snapshot = (
            session.get(OddsSnapshot, closing_snapshot_id)
            if closing_snapshot_id is not None
            else None
        )
        observations.append(
            SignalBacktestObservationView(
                id=observation.id,
                event_id=observation.event_id,
                selection_id=observation.selection_id,
                prediction_id=observation.prediction_id,
                odds_snapshot_id=observation.odds_snapshot_id,
                predicted_at=_utc(observation.predicted_at),
                settled_at=_utc(observation.settled_at),
                market_type=market.market_type,
                selection_code=selection.code,
                decimal_odds=_number(probabilities, "offered_odds"),
                model_probability=_number(probabilities, "model_probability"),
                lower_probability=_number(probabilities, "lower_probability"),
                expected_value=_number(probabilities, "expected_value"),
                settlement=observation.settlement,
                stake=observation.stake,
                profit_units=observation.profit_units,
                closing_odds_snapshot_id=closing_snapshot_id,
                closing_decimal_odds=_optional_number(probabilities, "closing_decimal_odds"),
                closing_observed_at=(
                    _utc(closing_snapshot.observed_at) if closing_snapshot is not None else None
                ),
                closing_line_value=observation.closing_line_value,
            )
        )
    return SignalBacktestView(
        id=run.id,
        model_version_id=model.id,
        model_version=model.version,
        status=run.status,
        evaluation_start=_utc(run.validation_end),
        evaluation_end=_utc(run.test_end),
        fingerprint=run.fingerprint,
        evaluation_status=run.evaluation_status,
        is_demo=run.is_demo,
        config=run.config,
        policy=run.policy,
        metrics=result.metrics,
        observations=observations,
        created_at=_utc(run.created_at),
    )


def _return_metrics(
    profits: list[float],
    expected_values: list[float],
    offered_odds: list[float],
    model_probabilities: list[float],
    closing_line_values: list[float | None] | None = None,
) -> dict[str, object]:
    if not (len(profits) == len(expected_values) == len(offered_odds) == len(model_probabilities)):
        raise BacktestingError("recommendation return inputs have inconsistent lengths")
    if not profits:
        raise BacktestingError("recommendation return metrics require observations")
    clv_values = closing_line_values if closing_line_values is not None else [None] * len(profits)
    if len(clv_values) != len(profits):
        raise BacktestingError("closing-line value inputs have inconsistent lengths")
    covered_clv = [value for value in clv_values if value is not None]
    wins = sum(value > 0 for value in profits)
    losses = sum(value < 0 for value in profits)
    pushes = len(profits) - wins - losses
    net_profit = sum(profits)
    gross_profit = sum(value for value in profits if value > 0)
    gross_loss = -sum(value for value in profits if value < 0)
    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0
    maximum_losing_streak = 0
    losing_streak = 0
    for value in profits:
        equity += value
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)
        if value < 0:
            losing_streak += 1
            maximum_losing_streak = max(maximum_losing_streak, losing_streak)
        elif value > 0:
            losing_streak = 0
    outcomes = [1.0 if value > 0 else 0.0 for value in profits]
    hit_rate = wins / len(profits)
    average_model_probability = sum(model_probabilities) / len(model_probabilities)
    average_break_even_probability = sum(1 / value for value in offered_odds) / len(offered_odds)
    expected_profit = sum(expected_values)
    brier_score = sum(
        (outcome - probability) ** 2
        for outcome, probability in zip(outcomes, model_probabilities, strict=True)
    ) / len(profits)
    log_loss = -sum(
        outcome * math.log(min(max(probability, 1e-15), 1 - 1e-15))
        + (1 - outcome) * math.log(min(max(1 - probability, 1e-15), 1 - 1e-15))
        for outcome, probability in zip(outcomes, model_probabilities, strict=True)
    ) / len(profits)
    return {
        "bet_count": len(profits),
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "hit_rate": hit_rate,
        "net_profit_units": net_profit,
        "roi": net_profit / len(profits),
        "yield": net_profit / len(profits),
        "average_expected_value": sum(expected_values) / len(expected_values),
        "expected_profit_units": expected_profit,
        "average_decimal_odds": sum(offered_odds) / len(offered_odds),
        "median_decimal_odds": statistics.median(offered_odds),
        "average_break_even_probability": average_break_even_probability,
        "average_model_probability": average_model_probability,
        "hit_rate_minus_break_even": hit_rate - average_break_even_probability,
        "observed_to_model_hit_ratio": (
            hit_rate / average_model_probability if average_model_probability > 0 else None
        ),
        "realized_to_expected_profit_ratio": (
            net_profit / expected_profit if expected_profit > 0 else None
        ),
        "binary_brier_score": brier_score,
        "binary_log_loss": log_loss,
        "maximum_drawdown_units": max_drawdown,
        "maximum_losing_streak": maximum_losing_streak,
        "profit_factor": gross_profit / gross_loss if gross_loss else None,
        "closing_line_value_coverage": len(covered_clv) / len(profits),
        "average_closing_line_value": (
            sum(covered_clv) / len(covered_clv) if covered_clv else None
        ),
        "median_closing_line_value": statistics.median(covered_clv) if covered_clv else None,
    }


def _backtest_fingerprint(
    model: ModelVersion,
    request: RunSignalBacktestRequest,
    reference: datetime,
    rows: list[SettledSignalRow],
    closing_prices: dict[int, tuple[OddsSnapshot, OddsPrice]],
) -> str:
    payload = {
        "evaluator_version": "stored-value-signal-replay-v3",
        "model_version_id": model.id,
        "model_data_fingerprint": model.data_fingerprint,
        "request": request.model_dump(mode="json"),
        "result_known_at": reference.isoformat(),
        "observations": [
            {
                "signal_id": signal.id,
                "generated_at": _utc(signal.generated_at).isoformat(),
                "prediction_id": prediction.id,
                "inputs_as_of": _utc(output.inputs_as_of).isoformat(),
                "snapshot_id": snapshot.id,
                "snapshot_observed_at": _utc(snapshot.observed_at).isoformat(),
                "result_id": result.id,
                "result_observed_at": _utc(result.observed_at).isoformat(),
                "closing_snapshot_id": (
                    closing_prices[signal.id][0].id if signal.id in closing_prices else None
                ),
                "closing_odds": (
                    float(closing_prices[signal.id][1].decimal_odds)
                    if signal.id in closing_prices
                    else None
                ),
            }
            for signal, _, _, _, prediction, output, snapshot, _, _, result in rows
        ],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _number(values: dict[str, float], key: str) -> float:
    value = values.get(key)
    if not isinstance(value, (int, float)):
        raise BacktestingError(f"stored observation is missing {key}")
    return float(value)


def _optional_number(values: dict[str, float], key: str) -> float | None:
    value = values.get(key)
    return float(value) if isinstance(value, (int, float)) else None


def _optional_integer(values: dict[str, float], key: str) -> int | None:
    value = values.get(key)
    return int(value) if isinstance(value, (int, float)) else None


def _closing_price(
    session: Session,
    row: SettledSignalRow,
    reference: datetime,
) -> tuple[OddsSnapshot, OddsPrice] | None:
    signal, event, selection, market, _, _, taken_snapshot, _, _, _ = row
    kickoff = _utc(event.kickoff_at)
    candidate = session.execute(
        select(OddsSnapshot, OddsPrice)
        .join(OddsPrice, OddsPrice.snapshot_id == OddsSnapshot.id)
        .where(
            OddsSnapshot.market_id == market.id,
            OddsSnapshot.bookmaker_id == taken_snapshot.bookmaker_id,
            OddsSnapshot.provider_id == taken_snapshot.provider_id,
            OddsSnapshot.is_closing.is_(True),
            OddsSnapshot.is_complete.is_(True),
            OddsSnapshot.observed_at < kickoff,
            OddsSnapshot.ingested_at <= reference,
            OddsPrice.selection_id == selection.id,
        )
        .order_by(OddsSnapshot.observed_at.desc(), OddsSnapshot.id.desc())
    ).first()
    if candidate is None:
        return None
    snapshot, price = candidate
    if snapshot.source_updated_at is not None and _utc(snapshot.source_updated_at) >= kickoff:
        return None
    if _utc(signal.generated_at) >= kickoff:
        raise BacktestingError("closing-line lookup received an ineligible signal")
    return snapshot, price


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
