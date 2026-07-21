from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.models import Competition, Event
from app.db.session import Base, get_db
from app.main import app
from app.schemas.builder import BetBuilderLeg, CreateBetBuilderQuoteRequest
from app.schemas.models import PredictEventRequest, TrainPoissonRequest
from app.services.builder import (
    BetBuilderError,
    create_bet_builder_quote,
    list_bet_builder_quotes,
)
from app.services.demo_seed import seed_demo_data, seed_demo_results
from app.services.modeling import predict_event, train_poisson_model

AS_OF = datetime(2026, 7, 19, 10, 0, tzinfo=UTC)


@pytest.fixture
def session(tmp_path: Path) -> Generator[Session, None, None]:
    engine = create_engine(f"sqlite:///{tmp_path}/builder.db")
    Base.metadata.create_all(engine)
    with Session(engine) as database_session:
        seed_demo_results(database_session, as_of=AS_OF, ingested_at=AS_OF)
        seed_demo_data(database_session, as_of=AS_OF, ingested_at=AS_OF)
        yield database_session


def _prediction(session: Session) -> tuple[int, int]:
    competition_id = session.scalar(select(Competition.id))
    target = session.scalar(
        select(Event).where(Event.status == "scheduled").order_by(Event.kickoff_at)
    )
    assert competition_id is not None and target is not None
    model = train_poisson_model(
        session,
        TrainPoissonRequest(
            competition_id=competition_id,
            training_start=AS_OF - timedelta(days=150),
            training_end=AS_OF,
            minimum_matches=20,
            minimum_team_matches=3,
            shrinkage_matches=5,
        ),
        now=AS_OF,
    )
    output = predict_event(
        session,
        model.id,
        PredictEventRequest(event_id=target.id, predicted_at=AS_OF, inputs_as_of=AS_OF),
        now=AS_OF,
    )
    return target.id, output.id


def _request(session: Session) -> CreateBetBuilderQuoteRequest:
    event_id, output_id = _prediction(session)
    return CreateBetBuilderQuoteRequest(
        event_id=event_id,
        prediction_output_id=output_id,
        legs=[
            BetBuilderLeg(market_type="MATCH_RESULT", selection="HOME"),
            BetBuilderLeg(market_type="TOTAL_GOALS", selection="OVER", line=2.5),
        ],
        offered_odds=4.2,
        offered_odds_source="User-entered research price",
        offered_odds_observed_at=AS_OF + timedelta(minutes=1),
        quoted_at=AS_OF + timedelta(minutes=2),
    )


def test_builder_uses_scorelines_and_persists_exact_provenance(session: Session) -> None:
    request = _request(session)

    quote = create_bet_builder_quote(session, request, now=AS_OF + timedelta(minutes=3))
    repeated = create_bet_builder_quote(session, request, now=AS_OF + timedelta(minutes=3))

    assert repeated.id == quote.id
    assert quote.joint_probability != pytest.approx(quote.independent_product)
    assert quote.lower_joint_probability < quote.joint_probability < quote.upper_joint_probability
    assert quote.lower_expected_value is not None
    assert len(quote.fingerprint) == 64
    assert len(quote.input_fingerprint) == 64
    assert quote.feature_version == "final-score-home-away-v1"
    assert quote.predicted_at <= quote.inputs_as_of <= quote.quoted_at
    assert quote.offered_odds_source == "User-entered research price"
    assert quote.is_demo is True
    assert "summed from scorelines" in quote.warnings[0]
    assert list_bet_builder_quotes(session, event_id=request.event_id)[0].id == quote.id


def test_builder_rejects_price_observed_after_quote_cutoff(session: Session) -> None:
    request = _request(session)
    request.offered_odds_observed_at = AS_OF + timedelta(minutes=3)

    with pytest.raises(BetBuilderError, match="after the quote cutoff"):
        create_bet_builder_quote(session, request, now=AS_OF + timedelta(minutes=4))


def test_offered_price_provenance_is_atomic() -> None:
    with pytest.raises(ValidationError, match="require source"):
        CreateBetBuilderQuoteRequest(
            event_id=1,
            prediction_output_id=1,
            legs=[
                BetBuilderLeg(market_type="MATCH_RESULT", selection="HOME"),
                BetBuilderLeg(market_type="BTTS", selection="YES"),
            ],
            offered_odds=3.5,
        )


def test_builder_api_creates_and_lists_quotes(session: Session) -> None:
    request = _request(session)
    engine = session.get_bind()

    def database_override() -> Generator[Session, None, None]:
        with Session(engine) as request_session:
            yield request_session

    app.dependency_overrides[get_db] = database_override
    try:
        with TestClient(app) as client:
            created = client.post(
                "/api/v1/bet-builder/quotes", json=request.model_dump(mode="json")
            )
            listed = client.get("/api/v1/bet-builder/quotes", params={"event_id": request.event_id})
    finally:
        app.dependency_overrides.clear()

    assert created.status_code == 201
    assert created.json()["prediction_output_id"] == request.prediction_output_id
    assert created.json()["is_demo"] is True
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [created.json()["id"]]
