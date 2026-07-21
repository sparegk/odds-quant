from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, datetime

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import BetBuilderQuote, Event, ModelEventOutput, ModelVersion
from app.quant.poisson import evaluate_builder
from app.schemas.builder import (
    BetBuilderLegView,
    BetBuilderQuoteView,
    CreateBetBuilderQuoteRequest,
)


class BetBuilderError(ValueError):
    pass


def create_bet_builder_quote(
    session: Session,
    request: CreateBetBuilderQuoteRequest,
    *,
    now: datetime | None = None,
) -> BetBuilderQuoteView:
    reference = request.quoted_at or now or datetime.now(UTC)
    reference = _utc(reference)
    current = _utc(now or datetime.now(UTC))
    if reference > current:
        raise BetBuilderError("quote timestamp cannot be in the future")

    event = session.get(Event, request.event_id)
    if event is None:
        raise BetBuilderError("event not found")
    if reference >= _utc(event.kickoff_at):
        raise BetBuilderError("bet-builder quote must be created before kickoff")

    output = session.get(ModelEventOutput, request.prediction_output_id)
    if output is None or output.event_id != event.id:
        raise BetBuilderError("prediction output does not belong to this event")
    if _utc(output.predicted_at) > reference or _utc(output.inputs_as_of) > reference:
        raise BetBuilderError("prediction output was not available at the quote cutoff")

    model = session.get(ModelVersion, output.model_version_id)
    if model is None:
        raise BetBuilderError("model version not found")
    if _utc(model.training_end) > _utc(output.inputs_as_of):
        raise BetBuilderError("model training window exceeds the prediction input cutoff")

    observed_at = request.offered_odds_observed_at
    if observed_at is not None:
        observed_at = _utc(observed_at)
        if observed_at > reference:
            raise BetBuilderError("offered odds were observed after the quote cutoff")
        if observed_at >= _utc(event.kickoff_at):
            raise BetBuilderError("offered odds must be observed before kickoff")

    normalized_legs = [leg.model_dump() for leg in request.legs]
    matrix = np.asarray(output.score_matrix, dtype=np.float64)
    try:
        evaluation = evaluate_builder(matrix, normalized_legs, request.offered_odds)
    except (KeyError, TypeError, ValueError) as exc:
        raise BetBuilderError(str(exc)) from exc
    joint = float(evaluation["joint_probability"])
    if joint <= 0:
        raise BetBuilderError("selected legs have no winning scoreline in the stored grid")
    evaluated_fair_odds = evaluation["fair_odds"]
    if evaluated_fair_odds is None:
        raise BetBuilderError("selected legs do not produce finite fair odds")
    lower, upper = _wilson_interval(joint, output.sample_size)
    lower_ev = lower * request.offered_odds - 1 if request.offered_odds else None
    leg_probabilities = [float(value) for value in evaluation["leg_probabilities"]]
    stored_legs = [
        {**leg, "marginal_probability": probability}
        for leg, probability in zip(normalized_legs, leg_probabilities, strict=True)
    ]
    fingerprint = _fingerprint(
        output=output,
        model=model,
        legs=normalized_legs,
        offered_odds=request.offered_odds,
        offered_odds_source=request.offered_odds_source,
        offered_odds_observed_at=observed_at,
        quoted_at=reference,
    )
    existing = session.scalar(
        select(BetBuilderQuote).where(BetBuilderQuote.fingerprint == fingerprint)
    )
    if existing is not None:
        return _quote_view(existing, output, model)

    quote = BetBuilderQuote(
        event_id=event.id,
        model_version_id=model.id,
        prediction_output_id=output.id,
        fingerprint=fingerprint,
        feature_version=model.feature_version,
        input_fingerprint=model.data_fingerprint,
        legs=stored_legs,
        joint_probability=joint,
        lower_joint_probability=lower,
        upper_joint_probability=upper,
        independent_product=float(evaluation["independent_product"]),
        dependence_ratio=float(evaluation["dependence_ratio"]),
        fair_odds=evaluated_fair_odds,
        offered_odds=request.offered_odds,
        offered_odds_source=request.offered_odds_source,
        offered_odds_observed_at=observed_at,
        expected_value=(
            float(evaluation["expected_value"])
            if evaluation["expected_value"] is not None
            else None
        ),
        lower_expected_value=lower_ev,
        warnings=[str(evaluation["dependence_warning"]), str(evaluation["uncertainty"])],
        created_at=reference,
    )
    session.add(quote)
    session.commit()
    session.refresh(quote)
    return _quote_view(quote, output, model)


def list_bet_builder_quotes(
    session: Session, *, event_id: int | None = None
) -> list[BetBuilderQuoteView]:
    statement = (
        select(BetBuilderQuote, ModelEventOutput, ModelVersion)
        .join(ModelEventOutput, ModelEventOutput.id == BetBuilderQuote.prediction_output_id)
        .join(ModelVersion, ModelVersion.id == BetBuilderQuote.model_version_id)
        .where(BetBuilderQuote.fingerprint.is_not(None))
    )
    if event_id is not None:
        statement = statement.where(BetBuilderQuote.event_id == event_id)
    rows = session.execute(statement.order_by(BetBuilderQuote.created_at.desc())).all()
    return [_quote_view(quote, output, model) for quote, output, model in rows]


def _quote_view(
    quote: BetBuilderQuote, output: ModelEventOutput, model: ModelVersion
) -> BetBuilderQuoteView:
    if (
        quote.prediction_output_id is None
        or quote.fingerprint is None
        or quote.feature_version is None
        or quote.input_fingerprint is None
        or quote.lower_joint_probability is None
        or quote.upper_joint_probability is None
        or quote.independent_product is None
        or quote.dependence_ratio is None
    ):
        raise BetBuilderError("stored bet-builder quote has incomplete provenance")
    return BetBuilderQuoteView(
        id=quote.id,
        event_id=quote.event_id,
        model_version_id=model.id,
        model_version=model.version,
        is_demo=model.is_demo,
        evidence_class=output.evidence_class,
        prediction_output_id=output.id,
        predicted_at=_utc(output.predicted_at),
        inputs_as_of=_utc(output.inputs_as_of),
        quoted_at=_utc(quote.created_at),
        fingerprint=quote.fingerprint,
        feature_version=quote.feature_version,
        input_fingerprint=quote.input_fingerprint,
        legs=[BetBuilderLegView.model_validate(leg) for leg in quote.legs],
        joint_probability=quote.joint_probability,
        lower_joint_probability=quote.lower_joint_probability,
        upper_joint_probability=quote.upper_joint_probability,
        independent_product=quote.independent_product,
        dependence_ratio=quote.dependence_ratio,
        fair_odds=quote.fair_odds,
        offered_odds=quote.offered_odds,
        offered_odds_source=quote.offered_odds_source,
        offered_odds_observed_at=(
            _utc(quote.offered_odds_observed_at)
            if quote.offered_odds_observed_at is not None
            else None
        ),
        expected_value=quote.expected_value,
        lower_expected_value=quote.lower_expected_value,
        warnings=quote.warnings,
    )


def _fingerprint(
    *,
    output: ModelEventOutput,
    model: ModelVersion,
    legs: list[dict[str, object]],
    offered_odds: float | None,
    offered_odds_source: str | None,
    offered_odds_observed_at: datetime | None,
    quoted_at: datetime,
) -> str:
    payload = {
        "prediction_output_id": output.id,
        "predicted_at": _utc(output.predicted_at).isoformat(),
        "inputs_as_of": _utc(output.inputs_as_of).isoformat(),
        "model_data_fingerprint": model.data_fingerprint,
        "feature_version": model.feature_version,
        "legs": legs,
        "offered_odds": offered_odds,
        "offered_odds_source": offered_odds_source,
        "offered_odds_observed_at": (
            offered_odds_observed_at.isoformat() if offered_odds_observed_at else None
        ),
        "quoted_at": quoted_at.isoformat(),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _wilson_interval(probability: float, sample_size: int) -> tuple[float, float]:
    z = 1.96
    denominator = 1 + z * z / sample_size
    center = (probability + z * z / (2 * sample_size)) / denominator
    margin = (
        z
        * math.sqrt(
            probability * (1 - probability) / sample_size + z * z / (4 * sample_size * sample_size)
        )
        / denominator
    )
    return max(0.0, center - margin), min(1.0, center + margin)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
