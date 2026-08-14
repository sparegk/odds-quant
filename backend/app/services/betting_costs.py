from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import BookmakerConstraint, BookmakerTaxProfile, TaxProfile
from app.quant.arbitrage import ArbitrageMathError, StakeConstraint, TaxTerms
from app.quant.betting_costs import valid_reference_stake


@dataclass(frozen=True)
class QuoteCostEvidence:
    tax: TaxTerms | None
    constraint: StakeConstraint | None
    tax_profile_id: int | None
    tax_verified_at: datetime | None
    constraint_observed_at: datetime | None
    blockers: tuple[str, ...]


def resolve_quote_cost_evidence(
    session: Session,
    *,
    bookmaker_id: int,
    bookmaker_name: str,
    currency: str,
    reference: datetime,
    tax_max_age: timedelta = timedelta(days=365),
    constraint_max_age: timedelta = timedelta(minutes=1_440),
) -> QuoteCostEvidence:
    reference = _utc(reference)
    mapping = session.scalar(
        select(BookmakerTaxProfile)
        .where(
            BookmakerTaxProfile.bookmaker_id == bookmaker_id,
            BookmakerTaxProfile.valid_from <= reference,
            BookmakerTaxProfile.valid_to.is_(None) | (BookmakerTaxProfile.valid_to > reference),
        )
        .order_by(BookmakerTaxProfile.valid_from.desc(), BookmakerTaxProfile.id.desc())
    )
    profile = session.get(TaxProfile, mapping.tax_profile_id) if mapping else None
    tax_issue: str | None = None
    if profile is None:
        tax_issue = f"Tax rules are unknown for {bookmaker_name}."
    elif profile.currency != currency:
        tax_issue = f"Tax currency does not match for {bookmaker_name}."
    elif profile.status != "verified":
        tax_issue = f"Tax rules are not verified for {bookmaker_name}."
    elif not profile.source_label.strip():
        tax_issue = f"Tax-rule source is missing for {bookmaker_name}."
    elif _utc(profile.effective_from) > reference:
        tax_issue = f"Tax rules are not yet effective for {bookmaker_name}."
    elif profile.effective_to is not None and _utc(profile.effective_to) <= reference:
        tax_issue = f"Tax rules have expired for {bookmaker_name}."
    elif _utc(profile.verified_at) > reference:
        tax_issue = f"Tax rules were verified after the cutoff for {bookmaker_name}."
    elif reference - _utc(profile.verified_at) > tax_max_age:
        tax_issue = f"Tax verification is stale for {bookmaker_name}."

    constraint_row = session.scalar(
        select(BookmakerConstraint)
        .where(
            BookmakerConstraint.bookmaker_id == bookmaker_id,
            BookmakerConstraint.currency == currency,
            BookmakerConstraint.observed_at <= reference,
        )
        .order_by(BookmakerConstraint.observed_at.desc(), BookmakerConstraint.id.desc())
    )
    constraint_issue: str | None = None
    if constraint_row is None:
        constraint_issue = f"Stake limits are unknown for {bookmaker_name}."
    elif not constraint_row.source_label.strip():
        constraint_issue = f"Stake-limit source is missing for {bookmaker_name}."
    elif reference - _utc(constraint_row.observed_at) > constraint_max_age:
        constraint_issue = f"Stake limits are stale for {bookmaker_name}."

    tax = (
        TaxTerms(
            stake_tax_rate=Decimal(profile.stake_tax_rate),
            winnings_tax_rate=Decimal(profile.winnings_tax_rate),
            payout_withholding_rate=Decimal(profile.payout_withholding_rate),
            commission_rate=Decimal(profile.commission_rate),
            fixed_fee=Decimal(profile.fixed_fee),
        )
        if profile is not None and tax_issue is None
        else None
    )
    constraint: StakeConstraint | None = None
    if constraint_row is not None and constraint_issue is None:
        try:
            constraint = StakeConstraint(
                minimum_stake=Decimal(constraint_row.minimum_stake),
                maximum_stake=(
                    Decimal(constraint_row.maximum_stake)
                    if constraint_row.maximum_stake is not None
                    else None
                ),
                stake_increment=Decimal(constraint_row.stake_increment),
            )
            valid_reference_stake(constraint)
        except ArbitrageMathError:
            constraint = None
            constraint_issue = (
                f"Stake limits cannot produce a valid rounded stake for {bookmaker_name}."
            )
    tax_profile_id = profile.id if profile is not None and tax is not None else None
    tax_verified_at = _utc(profile.verified_at) if profile is not None and tax is not None else None
    constraint_observed_at = (
        _utc(constraint_row.observed_at)
        if constraint_row is not None and constraint is not None
        else None
    )
    return QuoteCostEvidence(
        tax=tax,
        constraint=constraint,
        tax_profile_id=tax_profile_id,
        tax_verified_at=tax_verified_at,
        constraint_observed_at=constraint_observed_at,
        blockers=tuple(item for item in (tax_issue, constraint_issue) if item is not None),
    )


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
