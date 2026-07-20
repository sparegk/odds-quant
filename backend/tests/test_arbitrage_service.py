from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.models import (
    ArbitrageOpportunity,
    Bookmaker,
    BookmakerConstraint,
    BookmakerTaxProfile,
    Event,
    OddsPrice,
    OddsSnapshot,
    Provider,
    Selection,
    TaxProfile,
)
from app.db.session import Base, get_db
from app.main import app
from app.schemas.arbitrage import CalculateArbitrageRequest
from app.services.arbitrage import (
    ArbitrageDiscoveryError,
    calculate_arbitrage,
    list_arbitrage_opportunities,
)
from app.services.demo_seed import seed_demo_data

AS_OF = datetime(2026, 7, 19, 10, 0, tzinfo=UTC)


@pytest.fixture
def session(tmp_path: Path) -> Generator[Session, None, None]:
    engine = create_engine(f"sqlite:///{tmp_path}/arbitrage.db")
    Base.metadata.create_all(engine)
    with Session(engine) as database_session:
        seed_demo_data(database_session, as_of=AS_OF, ingested_at=AS_OF)
        event = database_session.scalar(select(Event).order_by(Event.kickoff_at))
        assert event is not None
        event.is_demo = False
        bookmakers = database_session.scalars(select(Bookmaker).order_by(Bookmaker.id)).all()
        for bookmaker in bookmakers:
            bookmaker.is_demo = False
        providers = database_session.scalars(select(Provider)).all()
        for provider in providers:
            provider.is_demo = False
        prices = database_session.execute(
            select(OddsPrice, Selection)
            .join(Selection, Selection.id == OddsPrice.selection_id)
            .where(Selection.market_id.in_(select(Selection.market_id).limit(1)))
        ).all()
        target = {"AWAY": Decimal("4.00"), "DRAW": Decimal("4.00"), "HOME": Decimal("3.50")}
        for price, selection in prices:
            price.decimal_odds = target[selection.code]
        database_session.commit()
        yield database_session


def _add_verified_terms(session: Session) -> None:
    for bookmaker in session.scalars(select(Bookmaker)).all():
        profile = TaxProfile(
            name=f"Test tax {bookmaker.id}",
            jurisdiction="Test",
            currency="EUR",
            tax_basis="per_bet",
            stake_tax_rate=Decimal("0"),
            winnings_tax_rate=Decimal("0"),
            payout_withholding_rate=Decimal("0"),
            commission_rate=Decimal("0"),
            fixed_fee=Decimal("0"),
            effective_from=AS_OF - timedelta(days=30),
            effective_to=None,
            verified_at=AS_OF,
            source_url="https://example.test/tax",
            source_label="Deterministic test fixture",
            status="verified",
        )
        session.add(profile)
        session.flush()
        session.add(
            BookmakerTaxProfile(
                bookmaker_id=bookmaker.id,
                tax_profile_id=profile.id,
                valid_from=AS_OF - timedelta(days=30),
                valid_to=None,
            )
        )
        session.add(
            BookmakerConstraint(
                bookmaker_id=bookmaker.id,
                currency="EUR",
                minimum_stake=Decimal("1"),
                maximum_stake=Decimal("1000"),
                stake_increment=Decimal("0.01"),
                observed_at=AS_OF,
                source_label="Deterministic test fixture",
            )
        )
    session.commit()


def _request(session: Session) -> CalculateArbitrageRequest:
    event_id = session.scalar(select(Event.id).order_by(Event.kickoff_at))
    assert event_id is not None
    return CalculateArbitrageRequest(
        event_id=event_id,
        budget=Decimal("100"),
        calculated_at=AS_OF + timedelta(minutes=1),
    )


def test_verified_fresh_opportunity_is_executable_and_idempotent(session: Session) -> None:
    _add_verified_terms(session)
    request = _request(session)

    batch = calculate_arbitrage(session, request, now=AS_OF + timedelta(minutes=2))
    repeated = calculate_arbitrage(session, request, now=AS_OF + timedelta(minutes=2))

    assert len(batch.opportunities) == 1
    opportunity = batch.opportunities[0]
    assert opportunity.status == "executable"
    assert opportunity.net_profit > 0
    assert opportunity.total_cash_outlay <= Decimal("100")
    assert len(opportunity.legs) == 3
    assert repeated.opportunities[0].id == opportunity.id


def test_unknown_tax_and_constraints_block_execution(session: Session) -> None:
    batch = calculate_arbitrage(session, _request(session), now=AS_OF + timedelta(minutes=2))

    assert len(batch.opportunities) == 1
    opportunity = batch.opportunities[0]
    assert opportunity.status == "blocked"
    assert opportunity.tax_status == "blocked"
    assert opportunity.constraint_status == "blocked"
    assert any("Tax rules are unknown" in risk for risk in opportunity.risks)
    assert any("Stake limits are unknown" in risk for risk in opportunity.risks)


def test_future_tax_verification_blocks_execution(session: Session) -> None:
    _add_verified_terms(session)
    request = _request(session)
    assert request.calculated_at is not None
    for profile in session.scalars(select(TaxProfile)).all():
        profile.verified_at = request.calculated_at + timedelta(minutes=1)
    session.commit()

    batch = calculate_arbitrage(session, request, now=request.calculated_at + timedelta(minutes=2))

    assert batch.opportunities[0].status == "blocked"
    assert batch.opportunities[0].tax_status == "blocked"
    assert any("verified after the cutoff" in risk for risk in batch.opportunities[0].risks)


def test_odds_ingested_after_cutoff_are_excluded(session: Session) -> None:
    request = _request(session)
    assert request.calculated_at is not None
    for snapshot in session.scalars(select(OddsSnapshot)).all():
        snapshot.ingested_at = request.calculated_at + timedelta(minutes=1)
    session.commit()

    batch = calculate_arbitrage(session, request, now=request.calculated_at + timedelta(minutes=2))

    assert batch.opportunities == []


def test_post_kickoff_calculation_is_rejected(session: Session) -> None:
    event = session.get_one(Event, _request(session).event_id)
    kickoff_at = event.kickoff_at.replace(tzinfo=UTC)
    request = CalculateArbitrageRequest(
        event_id=event.id,
        budget=Decimal("100"),
        calculated_at=kickoff_at,
    )

    with pytest.raises(ArbitrageDiscoveryError, match="before kickoff"):
        calculate_arbitrage(session, request, now=kickoff_at)


def test_listing_excludes_legacy_rows_without_provenance(session: Session) -> None:
    _add_verified_terms(session)
    request = _request(session)
    batch = calculate_arbitrage(session, request, now=AS_OF + timedelta(minutes=2))
    stored = session.get_one(ArbitrageOpportunity, batch.opportunities[0].id)
    stored.fingerprint = None
    session.commit()

    assert list_arbitrage_opportunities(session, event_id=request.event_id) == []


def test_arbitrage_api_calculates_and_lists_opportunities(session: Session) -> None:
    _add_verified_terms(session)
    request = _request(session)
    engine = session.get_bind()

    def database_override() -> Generator[Session, None, None]:
        with Session(engine) as request_session:
            yield request_session

    app.dependency_overrides[get_db] = database_override
    try:
        with TestClient(app) as client:
            calculated = client.post(
                "/api/v1/arbitrage/calculate",
                json=request.model_dump(mode="json"),
            )
            listed = client.get(
                "/api/v1/arbitrage/opportunities",
                params={"event_id": request.event_id},
            )
    finally:
        app.dependency_overrides.clear()

    assert calculated.status_code == 201
    assert len(calculated.json()["opportunities"]) == 1
    assert calculated.json()["opportunities"][0]["status"] == "executable"
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [calculated.json()["opportunities"][0]["id"]]
