from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    ArbitrageLeg,
    ArbitrageOpportunity,
    Bookmaker,
    BookmakerConstraint,
    BookmakerTaxProfile,
    Event,
    Market,
    OddsPrice,
    OddsSnapshot,
    Provider,
    Selection,
    TaxProfile,
)
from app.quant.arbitrage import (
    ArbitrageMathError,
    ArbitrageQuote,
    StakeConstraint,
    TaxTerms,
    gross_inverse_sum,
    optimize_rounded_stakes,
)
from app.schemas.arbitrage import (
    ArbitrageBatchView,
    ArbitrageLegView,
    ArbitrageOpportunityView,
    CalculateArbitrageRequest,
)
from app.schemas.odds import EXPECTED_SELECTIONS, MarketType


class ArbitrageDiscoveryError(ValueError):
    pass


@dataclass(frozen=True)
class _BestQuote:
    selection: Selection
    bookmaker: Bookmaker
    provider: Provider
    snapshot: OddsSnapshot
    odds: Decimal


@dataclass(frozen=True)
class _Terms:
    tax_profile: TaxProfile | None
    constraint: BookmakerConstraint | None
    tax: TaxTerms
    stake_constraint: StakeConstraint
    tax_issue: str | None
    constraint_issue: str | None


def calculate_arbitrage(
    session: Session,
    request: CalculateArbitrageRequest,
    *,
    now: datetime | None = None,
) -> ArbitrageBatchView:
    event = session.get(Event, request.event_id)
    if event is None:
        raise ArbitrageDiscoveryError("event not found")
    reference = _utc(request.calculated_at or now or datetime.now(UTC))
    current = _utc(now or datetime.now(UTC))
    if reference > current:
        raise ArbitrageDiscoveryError("calculation timestamp cannot be in the future")
    if reference >= _utc(event.kickoff_at):
        raise ArbitrageDiscoveryError("arbitrage must be calculated before kickoff")

    markets = session.scalars(
        select(Market)
        .where(Market.event_id == event.id, Market.currency == request.currency)
        .order_by(Market.id)
    ).all()
    opportunities: list[ArbitrageOpportunity] = []
    for market in markets:
        best_quotes = _best_complete_quotes(session, market, reference)
        if not best_quotes:
            continue
        gross_quotes = [
            ArbitrageQuote(
                selection_code=quote.selection.code,
                decimal_odds=quote.odds,
                tax=TaxTerms(),
                constraint=StakeConstraint(),
            )
            for quote in best_quotes
        ]
        if gross_inverse_sum(gross_quotes) >= Decimal("1"):
            continue

        terms = [
            _terms_for_quote(
                session,
                quote,
                currency=request.currency,
                reference=reference,
                tax_max_age=timedelta(days=request.tax_max_age_days),
                constraint_max_age=timedelta(minutes=request.constraint_max_age_minutes),
            )
            for quote in best_quotes
        ]
        executable_quotes = [
            ArbitrageQuote(
                selection_code=quote.selection.code,
                decimal_odds=quote.odds,
                tax=item.tax,
                constraint=item.stake_constraint,
            )
            for quote, item in zip(best_quotes, terms, strict=True)
        ]
        try:
            allocation = optimize_rounded_stakes(executable_quotes, budget=request.budget)
        except ArbitrageMathError:
            continue

        fingerprint = _fingerprint(market, reference, request, best_quotes, terms)
        existing = session.scalar(
            select(ArbitrageOpportunity).where(ArbitrageOpportunity.fingerprint == fingerprint)
        )
        if existing is not None:
            opportunities.append(existing)
            continue

        tax_issues = [item.tax_issue for item in terms if item.tax_issue]
        constraint_issues = [item.constraint_issue for item in terms if item.constraint_issue]
        stale = [
            quote
            for quote in best_quotes
            if reference - _utc(quote.snapshot.observed_at)
            > timedelta(seconds=request.odds_stale_after_seconds)
        ]
        demo = event.is_demo or any(
            quote.bookmaker.is_demo or quote.provider.is_demo for quote in best_quotes
        )
        tax_status = "verified" if not tax_issues else "blocked"
        constraint_status = "verified" if not constraint_issues else "blocked"
        freshness_status = "fresh" if not stale else "stale"
        risks = [*tax_issues, *constraint_issues]
        if stale:
            risks.append("One or more selected prices are stale.")
        if demo:
            risks.append("Demo data cannot support an executable opportunity.")
        if allocation.worst_case_net_profit <= 0:
            risks.append("Worst-case net profit is not positive after configured costs.")
        executable = (
            tax_status == "verified"
            and constraint_status == "verified"
            and freshness_status == "fresh"
            and not demo
            and allocation.worst_case_net_profit > 0
        )
        opportunity = ArbitrageOpportunity(
            event_id=event.id,
            market_id=market.id,
            calculated_at=reference,
            fingerprint=fingerprint,
            status="executable" if executable else "blocked",
            inverse_sum=float(allocation.inverse_sum),
            budget=request.budget,
            total_cash_outlay=allocation.total_cash_outlay,
            minimum_net_payout=allocation.minimum_net_payout,
            net_profit=allocation.worst_case_net_profit,
            net_roi=float(allocation.net_roi),
            tax_status=tax_status,
            constraint_status=constraint_status,
            freshness_status=freshness_status,
            currency=request.currency,
            risks=risks,
        )
        session.add(opportunity)
        session.flush()
        by_code = {leg.selection_code: leg for leg in allocation.legs}
        for quote, item in zip(best_quotes, terms, strict=True):
            leg = by_code[quote.selection.code]
            session.add(
                ArbitrageLeg(
                    opportunity_id=opportunity.id,
                    selection_id=quote.selection.id,
                    bookmaker_id=quote.bookmaker.id,
                    odds_snapshot_id=quote.snapshot.id,
                    tax_profile_id=(item.tax_profile.id if item.tax_profile else None),
                    bookmaker_constraint_id=(item.constraint.id if item.constraint else None),
                    decimal_odds=leg.decimal_odds,
                    stake=leg.stake,
                    cash_outlay=leg.cash_outlay,
                    gross_payout=leg.gross_payout,
                    win_deductions=leg.win_deductions,
                    taxes_and_fees=(leg.cash_outlay - leg.stake) + leg.win_deductions,
                    net_payout=leg.net_payout,
                )
            )
        opportunities.append(opportunity)
    session.commit()
    return ArbitrageBatchView(
        event_id=event.id,
        calculated_at=reference,
        opportunities=[_opportunity_view(session, item) for item in opportunities],
    )


def list_arbitrage_opportunities(
    session: Session, *, event_id: int | None = None
) -> list[ArbitrageOpportunityView]:
    statement = select(ArbitrageOpportunity).where(ArbitrageOpportunity.fingerprint.is_not(None))
    if event_id is not None:
        statement = statement.where(ArbitrageOpportunity.event_id == event_id)
    rows = session.scalars(
        statement.order_by(ArbitrageOpportunity.net_profit.desc(), ArbitrageOpportunity.id)
    ).all()
    return [_opportunity_view(session, row) for row in rows]


def _best_complete_quotes(
    session: Session, market: Market, reference: datetime
) -> list[_BestQuote]:
    try:
        expected = EXPECTED_SELECTIONS[MarketType(market.market_type)]
    except (KeyError, ValueError):
        return []
    rows = session.execute(
        select(OddsSnapshot, Bookmaker, Provider)
        .join(Bookmaker, Bookmaker.id == OddsSnapshot.bookmaker_id)
        .join(Provider, Provider.id == OddsSnapshot.provider_id)
        .where(
            OddsSnapshot.market_id == market.id,
            OddsSnapshot.is_complete.is_(True),
            OddsSnapshot.observed_at <= reference,
            OddsSnapshot.ingested_at <= reference,
        )
        .order_by(
            OddsSnapshot.bookmaker_id,
            OddsSnapshot.observed_at.desc(),
            OddsSnapshot.id.desc(),
        )
    ).all()
    latest: dict[int, tuple[OddsSnapshot, Bookmaker, Provider]] = {}
    for snapshot, bookmaker, provider in rows:
        latest.setdefault(bookmaker.id, (snapshot, bookmaker, provider))

    best: dict[str, _BestQuote] = {}
    for snapshot, bookmaker, provider in latest.values():
        prices = session.execute(
            select(OddsPrice, Selection)
            .join(Selection, Selection.id == OddsPrice.selection_id)
            .where(OddsPrice.snapshot_id == snapshot.id)
            .order_by(Selection.code)
        ).all()
        if {selection.code for _, selection in prices} != set(expected):
            continue
        for price, selection in prices:
            candidate = _BestQuote(
                selection=selection,
                bookmaker=bookmaker,
                provider=provider,
                snapshot=snapshot,
                odds=Decimal(price.decimal_odds),
            )
            current = best.get(selection.code)
            if current is None or (candidate.odds, candidate.snapshot.id) > (
                current.odds,
                current.snapshot.id,
            ):
                best[selection.code] = candidate
    if set(best) != set(expected):
        return []
    return [best[code] for code in sorted(expected)]


def _terms_for_quote(
    session: Session,
    quote: _BestQuote,
    *,
    currency: str,
    reference: datetime,
    tax_max_age: timedelta,
    constraint_max_age: timedelta,
) -> _Terms:
    mapping = session.scalar(
        select(BookmakerTaxProfile)
        .where(
            BookmakerTaxProfile.bookmaker_id == quote.bookmaker.id,
            BookmakerTaxProfile.valid_from <= reference,
            (BookmakerTaxProfile.valid_to.is_(None) | (BookmakerTaxProfile.valid_to > reference)),
        )
        .order_by(BookmakerTaxProfile.valid_from.desc(), BookmakerTaxProfile.id.desc())
    )
    profile = session.get(TaxProfile, mapping.tax_profile_id) if mapping else None
    tax_issue: str | None = None
    if profile is None:
        tax_issue = f"Tax rules are unknown for {quote.bookmaker.name}."
    elif profile.currency != currency:
        tax_issue = f"Tax currency does not match for {quote.bookmaker.name}."
    elif profile.status != "verified":
        tax_issue = f"Tax rules are not verified for {quote.bookmaker.name}."
    elif not (_utc(profile.effective_from) <= reference):
        tax_issue = f"Tax rules are not yet effective for {quote.bookmaker.name}."
    elif profile.effective_to is not None and _utc(profile.effective_to) <= reference:
        tax_issue = f"Tax rules have expired for {quote.bookmaker.name}."
    elif _utc(profile.verified_at) > reference:
        tax_issue = f"Tax rules were verified after the cutoff for {quote.bookmaker.name}."
    elif reference - _utc(profile.verified_at) > tax_max_age:
        tax_issue = f"Tax verification is stale for {quote.bookmaker.name}."

    constraint = session.scalar(
        select(BookmakerConstraint)
        .where(
            BookmakerConstraint.bookmaker_id == quote.bookmaker.id,
            BookmakerConstraint.currency == currency,
            BookmakerConstraint.observed_at <= reference,
        )
        .order_by(BookmakerConstraint.observed_at.desc(), BookmakerConstraint.id.desc())
    )
    constraint_issue: str | None = None
    if constraint is None:
        constraint_issue = f"Stake limits are unknown for {quote.bookmaker.name}."
    elif reference - _utc(constraint.observed_at) > constraint_max_age:
        constraint_issue = f"Stake limits are stale for {quote.bookmaker.name}."

    tax = TaxTerms()
    if profile is not None:
        tax = TaxTerms(
            stake_tax_rate=Decimal(profile.stake_tax_rate),
            winnings_tax_rate=Decimal(profile.winnings_tax_rate),
            payout_withholding_rate=Decimal(profile.payout_withholding_rate),
            commission_rate=Decimal(profile.commission_rate),
            fixed_fee=Decimal(profile.fixed_fee),
        )
    stake_constraint = StakeConstraint()
    if constraint is not None:
        stake_constraint = StakeConstraint(
            minimum_stake=Decimal(constraint.minimum_stake),
            maximum_stake=(
                Decimal(constraint.maximum_stake) if constraint.maximum_stake is not None else None
            ),
            stake_increment=Decimal(constraint.stake_increment),
        )
    return _Terms(
        tax_profile=profile,
        constraint=constraint,
        tax=tax,
        stake_constraint=stake_constraint,
        tax_issue=tax_issue,
        constraint_issue=constraint_issue,
    )


def _fingerprint(
    market: Market,
    reference: datetime,
    request: CalculateArbitrageRequest,
    quotes: list[_BestQuote],
    terms: list[_Terms],
) -> str:
    payload = {
        "market_id": market.id,
        "calculated_at": reference.isoformat(),
        "budget": str(request.budget),
        "currency": request.currency,
        "odds_stale_after_seconds": request.odds_stale_after_seconds,
        "tax_max_age_days": request.tax_max_age_days,
        "constraint_max_age_minutes": request.constraint_max_age_minutes,
        "legs": [
            {
                "selection_id": quote.selection.id,
                "snapshot_id": quote.snapshot.id,
                "odds": str(quote.odds),
                "tax_profile_id": item.tax_profile.id if item.tax_profile else None,
                "constraint_id": item.constraint.id if item.constraint else None,
            }
            for quote, item in zip(quotes, terms, strict=True)
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _opportunity_view(
    session: Session, opportunity: ArbitrageOpportunity
) -> ArbitrageOpportunityView:
    if opportunity.fingerprint is None:
        raise ArbitrageDiscoveryError("stored opportunity is missing its fingerprint")
    market = session.get(Market, opportunity.market_id)
    if market is None:
        raise ArbitrageDiscoveryError("stored opportunity market provenance is incomplete")
    rows = session.execute(
        select(ArbitrageLeg, Selection, Bookmaker)
        .join(Selection, Selection.id == ArbitrageLeg.selection_id)
        .join(Bookmaker, Bookmaker.id == ArbitrageLeg.bookmaker_id)
        .where(ArbitrageLeg.opportunity_id == opportunity.id)
        .order_by(Selection.code)
    ).all()
    return ArbitrageOpportunityView(
        id=opportunity.id,
        event_id=opportunity.event_id,
        market_id=market.id,
        market_type=market.market_type,
        line=float(market.line) if market.line is not None else None,
        period=market.period,
        settlement_rule_key=market.settlement_rule_key,
        calculated_at=_utc(opportunity.calculated_at),
        fingerprint=opportunity.fingerprint,
        status=opportunity.status,
        inverse_sum=opportunity.inverse_sum,
        budget=opportunity.budget,
        total_cash_outlay=opportunity.total_cash_outlay,
        minimum_net_payout=opportunity.minimum_net_payout,
        net_profit=opportunity.net_profit,
        net_roi=opportunity.net_roi,
        tax_status=opportunity.tax_status,
        constraint_status=opportunity.constraint_status,
        freshness_status=opportunity.freshness_status,
        currency=opportunity.currency,
        risks=opportunity.risks,
        legs=[
            ArbitrageLegView(
                id=leg.id,
                selection_id=selection.id,
                selection_code=selection.code,
                selection_name=selection.name,
                bookmaker_id=bookmaker.id,
                bookmaker=bookmaker.name,
                odds_snapshot_id=leg.odds_snapshot_id,
                tax_profile_id=leg.tax_profile_id,
                bookmaker_constraint_id=leg.bookmaker_constraint_id,
                decimal_odds=leg.decimal_odds,
                stake=leg.stake,
                cash_outlay=leg.cash_outlay,
                gross_payout=leg.gross_payout,
                win_deductions=leg.win_deductions,
                taxes_and_fees=leg.taxes_and_fees,
                net_payout=leg.net_payout,
            )
            for leg, selection, bookmaker in rows
        ],
    )


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
