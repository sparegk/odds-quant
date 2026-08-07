from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Event, FixtureObservation, MatchResult, Sport, Team
from app.db.session import Base
from app.schemas.fixtures import FixtureImportRow
from app.services.fixture_import import FixtureImportError, import_provider_fixtures

AS_OF = datetime(2026, 7, 30, 10, 0, tzinfo=UTC)


@pytest.fixture
def sessions(tmp_path: Path) -> sessionmaker[Session]:
    engine = create_engine(f"sqlite:///{tmp_path}/fixtures.db")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _row(
    *,
    observed_at: datetime,
    kickoff_at: datetime,
    home_team: str,
    away_team: str,
) -> FixtureImportRow:
    return FixtureImportRow(
        provider_event_key="stable-uefa-event",
        competition="UEFA Champions League Qualification",
        country="International",
        season="2026/27",
        kickoff_at=kickoff_at,
        home_team=home_team,
        away_team=away_team,
        observed_at=observed_at,
    )


def _import(session: Session, row: FixtureImportRow) -> None:
    import_provider_fixtures(
        session,
        rows=[row],
        provider_slug="licensed-fixtures",
        provider_name="Licensed fixtures",
        provider_kind="licensed_api",
        terms_url="https://example.test/terms",
        is_demo=False,
        now=row.observed_at,
    )
    session.commit()


def test_pre_kickoff_resolution_versions_fixture_identity(
    sessions: sessionmaker[Session],
) -> None:
    provisional = _row(
        observed_at=AS_OF,
        kickoff_at=AS_OF + timedelta(days=5),
        home_team="Winner Match 1",
        away_team="Winner Match 2",
    )
    resolved = _row(
        observed_at=AS_OF + timedelta(days=1),
        kickoff_at=AS_OF + timedelta(days=5, hours=1),
        home_team="Resolved Home",
        away_team="Resolved Away",
    )

    with sessions() as session:
        _import(session, provisional)
        _import(session, resolved)

        event = session.scalar(select(Event))
        observations = list(
            session.scalars(select(FixtureObservation).order_by(FixtureObservation.observed_at))
        )
        assert event is not None
        assert len(observations) == 2
        assert event.home_team_id == observations[1].home_team_id
        assert event.away_team_id == observations[1].away_team_id
        assert event.kickoff_at == resolved.kickoff_at.replace(tzinfo=None)
        assert observations[0].home_team_id != observations[1].home_team_id
        assert observations[0].away_team_id != observations[1].away_team_id
        assert observations[0].kickoff_at == provisional.kickoff_at.replace(tzinfo=None)
        assert observations[1].kickoff_at == resolved.kickoff_at.replace(tzinfo=None)


def test_fixture_correction_fails_closed_after_result_evidence(
    sessions: sessionmaker[Session],
) -> None:
    provisional = _row(
        observed_at=AS_OF,
        kickoff_at=AS_OF + timedelta(days=5),
        home_team="Winner Match 1",
        away_team="Winner Match 2",
    )
    resolved = _row(
        observed_at=AS_OF + timedelta(days=1),
        kickoff_at=AS_OF + timedelta(days=5, hours=1),
        home_team="Resolved Home",
        away_team="Resolved Away",
    )

    with sessions() as session:
        _import(session, provisional)
        event = session.scalar(select(Event))
        assert event is not None
        first_observation = session.scalar(select(FixtureObservation))
        assert first_observation is not None
        session.add(
            MatchResult(
                event_id=event.id,
                provider_id=first_observation.provider_id,
                home_goals=1,
                away_goals=0,
                status="final",
                is_final=True,
                source_updated_at=AS_OF,
                settled_at=AS_OF,
                observed_at=AS_OF,
            )
        )
        session.commit()

        with pytest.raises(FixtureImportError, match="downstream event evidence"):
            _import(session, resolved)
        session.rollback()

        unchanged = session.get_one(Event, event.id)
        assert unchanged.home_team_id == first_observation.home_team_id
        assert unchanged.away_team_id == first_observation.away_team_id


def test_fixture_import_reuses_earliest_team_for_trailing_fc_name_variant(
    sessions: sessionmaker[Session],
) -> None:
    with sessions() as session:
        sport = Sport(slug="football", name="Football")
        session.add(sport)
        session.flush()
        canonical = Team(sport_id=sport.id, name="Manchester United FC")
        session.add(canonical)
        session.commit()

        _import(
            session,
            _row(
                observed_at=AS_OF,
                kickoff_at=AS_OF + timedelta(days=5),
                home_team="Manchester United",
                away_team="Chelsea FC",
            ),
        )

        event = session.scalar(select(Event))
        assert event is not None
        assert event.home_team_id == canonical.id
        assert session.scalar(select(Team.id).where(Team.name == "Manchester United")) is None
