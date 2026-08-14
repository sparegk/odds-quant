from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.db.models import (
    Market,
    MatchResult,
    OddsPrice,
    OddsSnapshot,
    RecommendationSnapshot,
    RecommendationTrackingState,
    Selection,
)
from app.db.session import Base
from app.quant.odds import closing_line_value
from app.services.recommendation_tracking import (
    RecommendationTrackingError,
    refresh_recommendation,
)

KICKOFF = datetime(2026, 8, 14, 18, tzinfo=UTC)


def _session(tmp_path: Path) -> Session:
    engine = create_engine(f"sqlite:///{tmp_path}/recommendations.db")
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.execute(text("PRAGMA foreign_keys=OFF"))
    return session


def _seed_snapshot(session: Session) -> RecommendationSnapshot:
    market = Market(
        id=1,
        event_id=1,
        market_type="MATCH_RESULT",
        line=None,
        line_key="",
        period="FULL_TIME",
        currency="EUR",
        settlement_rule_key="football.match-result.v1",
    )
    selection = Selection(id=1, market_id=1, code="HOME", name="Home")
    taken = OddsSnapshot(
        id=10,
        market_id=1,
        bookmaker_id=1,
        provider_id=1,
        import_job_id=None,
        source_updated_at=KICKOFF - timedelta(minutes=10),
        observed_at=KICKOFF - timedelta(minutes=10),
        ingested_at=KICKOFF - timedelta(minutes=9),
        is_closing=False,
        is_complete=True,
        source_label="user CSV",
    )
    snapshot = RecommendationSnapshot(
        id=1,
        signal_id=1,
        event_id=1,
        selection_id=1,
        bookmaker_id=1,
        odds_snapshot_id=10,
        prediction_id=1,
        model_version_id=1,
        evaluation_run_id=1,
        tax_profile_id=1,
        captured_at=KICKOFF - timedelta(minutes=5),
        kickoff_at=KICKOFF,
        price_observed_at=KICKOFF - timedelta(minutes=10),
        tax_profile_verified_at=KICKOFF - timedelta(days=1),
        constraint_observed_at=KICKOFF - timedelta(hours=1),
        market_type="MATCH_RESULT",
        line=None,
        selection_code="HOME",
        settlement_rule_key="football.match-result.v1",
        currency="EUR",
        offered_odds=2.0,
        model_probability=0.6,
        lower_probability=0.55,
        lower_expected_value=0.1,
        net_expected_value=0.18,
        lower_net_expected_value=0.08,
        stake=100,
        cash_outlay=102,
        minimum_acceptable_odds=1.85,
        recommendation_quality={
            "probability_interval_retention": 0.92,
            "calibration_quality": 0.8,
            "price_freshness_quality": 0.5,
            "market_agreement_quality": 0.8,
            "net_economics_quality": 0.8,
            "bookmaker_disagreement": 0.02,
            "overall_quality_score": 0.74,
        },
        model_input_fingerprint="a" * 64,
        feature_version="team-form-v1",
        fingerprint="b" * 64,
    )
    state = RecommendationTrackingState(
        recommendation_id=1,
        closing_line_status="PENDING",
        settlement_status="PENDING",
        updated_at=KICKOFF - timedelta(minutes=5),
    )
    session.add_all([market, selection, taken, snapshot, state])
    session.commit()
    return snapshot


def test_refresh_tracks_timestamp_valid_close_and_settlement_without_mutating_decision(
    tmp_path: Path,
) -> None:
    session = _session(tmp_path)
    snapshot = _seed_snapshot(session)
    decision_fingerprint = snapshot.fingerprint
    decision_values = (
        snapshot.offered_odds,
        snapshot.lower_net_expected_value,
        snapshot.captured_at,
    )
    closing = OddsSnapshot(
        id=11,
        market_id=1,
        bookmaker_id=1,
        provider_id=1,
        import_job_id=None,
        source_updated_at=KICKOFF - timedelta(minutes=1),
        observed_at=KICKOFF - timedelta(minutes=1),
        ingested_at=KICKOFF + timedelta(minutes=1),
        is_closing=True,
        is_complete=True,
        source_label="user CSV closing flag",
    )
    session.add_all(
        [
            closing,
            OddsPrice(
                snapshot_id=11,
                selection_id=1,
                decimal_odds=Decimal("1.90000"),
            ),
            MatchResult(
                id=1,
                event_id=1,
                provider_id=1,
                home_goals=2,
                away_goals=1,
                status="final",
                is_final=True,
                source_updated_at=KICKOFF + timedelta(hours=2),
                observed_at=KICKOFF + timedelta(hours=2),
                settled_at=KICKOFF + timedelta(hours=2),
                supersedes_id=None,
            ),
        ]
    )
    session.commit()

    view = refresh_recommendation(
        session,
        recommendation_id=1,
        as_of=KICKOFF + timedelta(hours=3),
    )
    session.refresh(snapshot)

    assert view.tracking.closing_line_status == "AVAILABLE"
    assert view.tracking.closing_odds_snapshot_id == 11
    assert view.tracking.closing_odds == pytest.approx(1.9)
    assert view.tracking.closing_line_value == pytest.approx(closing_line_value(2.0, 1.9))
    assert view.tracking.settlement_status == "SETTLED"
    assert view.tracking.settlement == "WIN"
    assert view.tracking.profit_units == pytest.approx(100)
    assert snapshot.fingerprint == decision_fingerprint
    assert (snapshot.offered_odds, snapshot.lower_net_expected_value, snapshot.captured_at) == (
        decision_values
    )
    session.close()


def test_refresh_rejects_a_cutoff_before_the_decision(tmp_path: Path) -> None:
    session = _session(tmp_path)
    _seed_snapshot(session)

    with pytest.raises(RecommendationTrackingError, match="predates the decision"):
        refresh_recommendation(
            session,
            recommendation_id=1,
            as_of=KICKOFF - timedelta(minutes=6),
        )
    session.close()


def test_decision_snapshot_rejects_updates(tmp_path: Path) -> None:
    session = _session(tmp_path)
    snapshot = _seed_snapshot(session)
    snapshot.offered_odds = 3.0

    with pytest.raises(ValueError, match="decision snapshots are immutable"):
        session.commit()
    session.rollback()
    assert session.get_one(RecommendationSnapshot, 1).offered_odds == 2.0
    session.close()
