from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Bookmaker, BookmakerConstraint, BookmakerTaxProfile, TaxProfile
from app.schemas.arbitrage import (
    ArbitrageSettingsView,
    BookmakerConstraintView,
    BookmakerSettingsView,
    CreateBookmakerConstraintRequest,
    CreateTaxProfileRequest,
    TaxProfileView,
)


class ArbitrageSettingsError(ValueError):
    pass


def list_arbitrage_settings(session: Session) -> ArbitrageSettingsView:
    bookmakers = session.scalars(select(Bookmaker).order_by(Bookmaker.name, Bookmaker.id)).all()
    bookmaker_names = {item.id: item.name for item in bookmakers}
    tax_rows = session.execute(
        select(TaxProfile, BookmakerTaxProfile.bookmaker_id)
        .join(BookmakerTaxProfile, BookmakerTaxProfile.tax_profile_id == TaxProfile.id)
        .order_by(TaxProfile.verified_at.desc(), TaxProfile.id.desc())
    ).all()
    constraints = session.scalars(
        select(BookmakerConstraint).order_by(
            BookmakerConstraint.observed_at.desc(), BookmakerConstraint.id.desc()
        )
    ).all()
    return ArbitrageSettingsView(
        bookmakers=[
            BookmakerSettingsView(id=item.id, slug=item.slug, name=item.name, is_demo=item.is_demo)
            for item in bookmakers
        ],
        tax_profiles=[
            _tax_view(profile, bookmaker_id, bookmaker_names[bookmaker_id])
            for profile, bookmaker_id in tax_rows
        ],
        constraints=[
            _constraint_view(item, bookmaker_names[item.bookmaker_id]) for item in constraints
        ],
    )


def create_tax_profile(session: Session, request: CreateTaxProfileRequest) -> TaxProfileView:
    bookmaker = session.get(Bookmaker, request.bookmaker_id)
    if bookmaker is None:
        raise ArbitrageSettingsError("bookmaker not found")
    profile = TaxProfile(
        name=request.name,
        jurisdiction=request.jurisdiction,
        currency=request.currency,
        tax_basis=request.tax_basis,
        stake_tax_rate=request.stake_tax_rate,
        winnings_tax_rate=request.winnings_tax_rate,
        payout_withholding_rate=request.payout_withholding_rate,
        commission_rate=request.commission_rate,
        fixed_fee=request.fixed_fee,
        effective_from=request.effective_from,
        effective_to=request.effective_to,
        verified_at=request.verified_at,
        source_url=request.source_url,
        source_label=request.source_label,
        status="verified",
    )
    session.add(profile)
    session.flush()
    session.add(
        BookmakerTaxProfile(
            bookmaker_id=bookmaker.id,
            tax_profile_id=profile.id,
            valid_from=request.effective_from,
            valid_to=request.effective_to,
        )
    )
    session.commit()
    session.refresh(profile)
    return _tax_view(profile, bookmaker.id, bookmaker.name)


def create_bookmaker_constraint(
    session: Session, request: CreateBookmakerConstraintRequest
) -> BookmakerConstraintView:
    bookmaker = session.get(Bookmaker, request.bookmaker_id)
    if bookmaker is None:
        raise ArbitrageSettingsError("bookmaker not found")
    item = BookmakerConstraint(
        bookmaker_id=bookmaker.id,
        currency=request.currency,
        minimum_stake=request.minimum_stake,
        maximum_stake=request.maximum_stake,
        stake_increment=request.stake_increment,
        observed_at=request.observed_at,
        source_label=request.source_label,
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return _constraint_view(item, bookmaker.name)


def _tax_view(profile: TaxProfile, bookmaker_id: int, bookmaker: str) -> TaxProfileView:
    return TaxProfileView(
        id=profile.id,
        bookmaker_id=bookmaker_id,
        bookmaker=bookmaker,
        name=profile.name,
        jurisdiction=profile.jurisdiction,
        currency=profile.currency,
        stake_tax_rate=profile.stake_tax_rate,
        winnings_tax_rate=profile.winnings_tax_rate,
        payout_withholding_rate=profile.payout_withholding_rate,
        commission_rate=profile.commission_rate,
        fixed_fee=profile.fixed_fee,
        effective_from=profile.effective_from,
        effective_to=profile.effective_to,
        verified_at=profile.verified_at,
        source_url=profile.source_url,
        source_label=profile.source_label,
        status=profile.status,
    )


def _constraint_view(item: BookmakerConstraint, bookmaker: str) -> BookmakerConstraintView:
    return BookmakerConstraintView(
        id=item.id,
        bookmaker_id=item.bookmaker_id,
        bookmaker=bookmaker,
        currency=item.currency,
        minimum_stake=item.minimum_stake,
        maximum_stake=item.maximum_stake,
        stake_increment=item.stake_increment,
        observed_at=item.observed_at,
        source_label=item.source_label,
    )
