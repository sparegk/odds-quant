from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import (
    AvailabilityReport,
    Competition,
    Event,
    Player,
    PlayerAppearance,
    Provider,
    Sport,
    Team,
)
from app.db.session import Base
from app.services.lineup_projection import project_expected_lineups

NOW = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)


@pytest.fixture
def session(tmp_path: Path) -> Generator[Session, None, None]:
    engine = create_engine(f"sqlite:///{tmp_path}/lineups.db")
    Base.metadata.create_all(engine)
    with Session(engine) as database:
        yield database


def _seed_projection_history(session: Session) -> tuple[Event, list[Player], Provider]:
    sport = Sport(slug="football", name="Football")
    provider = Provider(
        slug="licensed-lineups",
        name="Licensed lineups",
        kind="licensed_api",
        is_demo=False,
        terms_url="https://provider.example/terms",
        capabilities={"football_intelligence": True},
    )
    session.add_all([sport, provider])
    session.flush()
    competition = Competition(
        sport_id=sport.id,
        name="Test League",
        country="Test",
        season="2026",
    )
    home = Team(sport_id=sport.id, name="Home FC")
    away = Team(sport_id=sport.id, name="Away FC")
    session.add_all([competition, home, away])
    session.flush()
    players = [
        Player(
            sport_id=sport.id,
            provider_id=provider.id,
            provider_player_key=f"p-{index}",
            name=f"Player {index}",
            position=("GK" if index < 2 else "DF" if index < 7 else "MF" if index < 11 else "FW"),
            preferred_side=None,
            birth_year=None,
            is_demo=False,
        )
        for index in range(15)
    ]
    future_only = Player(
        sport_id=sport.id,
        provider_id=provider.id,
        provider_player_key="future-star",
        name="Future Star",
        position="FW",
        preferred_side=None,
        birth_year=None,
        is_demo=False,
    )
    players.append(future_only)
    session.add_all(players)
    session.flush()
    history: list[Event] = []
    for index in range(3):
        event = Event(
            competition_id=competition.id,
            home_team_id=home.id,
            away_team_id=away.id,
            provider_id=provider.id,
            provider_event_key=f"history-{index}",
            kickoff_at=NOW - timedelta(days=21 - index * 7),
            status="final",
            is_demo=False,
        )
        session.add(event)
        session.flush()
        history.append(event)
        for player in players[:-1]:
            session.add(
                PlayerAppearance(
                    event_id=event.id,
                    player_id=player.id,
                    team_id=home.id,
                    provider_id=provider.id,
                    starter=player.provider_player_key != "p-14",
                    minutes=90 if player.provider_player_key != "p-14" else 20,
                    position=player.position,
                    role=None,
                    source_updated_at=event.kickoff_at + timedelta(hours=2),
                    observed_at=event.kickoff_at + timedelta(hours=3),
                )
            )
    target = Event(
        competition_id=competition.id,
        home_team_id=home.id,
        away_team_id=away.id,
        provider_id=provider.id,
        provider_event_key="target",
        kickoff_at=NOW + timedelta(days=4),
        status="scheduled",
        is_demo=False,
    )
    later = Event(
        competition_id=competition.id,
        home_team_id=home.id,
        away_team_id=away.id,
        provider_id=provider.id,
        provider_event_key="later",
        kickoff_at=NOW + timedelta(days=10),
        status="scheduled",
        is_demo=False,
    )
    session.add_all([target, later])
    session.flush()
    session.add(
        PlayerAppearance(
            event_id=later.id,
            player_id=future_only.id,
            team_id=home.id,
            provider_id=provider.id,
            starter=True,
            minutes=90,
            position="FW",
            role=None,
            source_updated_at=NOW + timedelta(days=10, hours=2),
            observed_at=NOW + timedelta(days=10, hours=3),
        )
    )
    session.commit()
    return target, players, provider


def test_projection_is_position_valid_deterministic_and_rejects_future_appearances(
    session: Session,
) -> None:
    target, _, _ = _seed_projection_history(session)

    first = project_expected_lineups(session, event_id=target.id, as_of=NOW, history_matches=3)
    repeated = project_expected_lineups(session, event_id=target.id, as_of=NOW, history_matches=3)
    home = first[0]

    assert home.status == "projected"
    assert len(home.starters) == 11
    assert {
        position: sum(member.position == position for member in home.starters)
        for position in ("GK", "DF", "MF", "FW")
    } == {"GK": 1, "DF": 4, "MF": 3, "FW": 3}
    assert "Future Star" not in {member.player for member in home.starters + home.alternates}
    assert home.input_fingerprint == repeated[0].input_fingerprint


def test_projection_separates_doubtful_available_scenario(session: Session) -> None:
    target, players, provider = _seed_projection_history(session)
    doubtful = players[11]
    session.add(
        AvailabilityReport(
            player_id=doubtful.id,
            team_id=target.home_team_id,
            event_id=target.id,
            provider_id=provider.id,
            status="doubtful",
            reason="late fitness test",
            evidence_class="licensed_provider",
            confidence=0.7,
            source_updated_at=NOW - timedelta(minutes=5),
            observed_at=NOW - timedelta(minutes=4),
            effective_from=NOW - timedelta(hours=1),
            effective_to=None,
            supersedes_id=None,
        )
    )
    session.commit()

    scenarios = project_expected_lineups(session, event_id=target.id, as_of=NOW, history_matches=3)
    home = [scenario for scenario in scenarios if scenario.team_id == target.home_team_id]

    assert [scenario.scenario_kind for scenario in home] == [
        "availability_weighted",
        "doubtful_available",
    ]
    baseline = next(
        member
        for member in home[0].starters + home[0].alternates
        if member.player_id == doubtful.id
    )
    available = next(
        member
        for member in home[1].starters + home[1].alternates
        if member.player_id == doubtful.id
    )
    assert baseline.start_probability < available.start_probability


def test_projection_excludes_availability_published_after_cutoff(session: Session) -> None:
    target, players, provider = _seed_projection_history(session)
    player = players[11]
    session.add(
        AvailabilityReport(
            player_id=player.id,
            team_id=target.home_team_id,
            event_id=target.id,
            provider_id=provider.id,
            status="out",
            reason="future correction",
            evidence_class="correction",
            confidence=1,
            source_updated_at=NOW + timedelta(hours=1),
            observed_at=NOW - timedelta(minutes=1),
            effective_from=NOW - timedelta(hours=1),
            effective_to=None,
            supersedes_id=None,
        )
    )
    session.commit()

    scenarios = project_expected_lineups(session, event_id=target.id, as_of=NOW, history_matches=3)
    projected = scenarios[0]
    stored = next(
        member
        for member in projected.starters + projected.alternates
        if member.player_id == player.id
    )

    assert stored.availability_status == "unknown"
    assert stored.start_probability > 0
