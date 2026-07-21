from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.models import (
    AvailabilityReport,
    CoachTenure,
    Event,
    LineupSnapshot,
    PlayerStatistic,
    TacticalSnapshot,
)
from app.schemas.intelligence import IntelligenceCoverageView


class IntelligenceError(ValueError):
    pass


def event_intelligence_coverage(
    session: Session, *, event_id: int, as_of: datetime
) -> IntelligenceCoverageView:
    event = session.get(Event, event_id)
    if event is None:
        raise IntelligenceError("event not found")
    cutoff = _utc(as_of)
    kickoff = _utc(event.kickoff_at)
    cutoff = min(cutoff, kickoff - timedelta(microseconds=1))
    teams = (event.home_team_id, event.away_team_id)
    player_statistics = (
        session.scalar(
            select(func.count())
            .select_from(PlayerStatistic)
            .join(Event, Event.id == PlayerStatistic.event_id)
            .where(
                PlayerStatistic.team_id.in_(teams),
                Event.kickoff_at < event.kickoff_at,
                PlayerStatistic.observed_at <= cutoff,
                PlayerStatistic.source_updated_at <= cutoff,
            )
        )
        or 0
    )
    availability = (
        session.scalar(
            select(func.count())
            .select_from(AvailabilityReport)
            .where(
                AvailabilityReport.team_id.in_(teams),
                or_(AvailabilityReport.event_id == event.id, AvailabilityReport.event_id.is_(None)),
                AvailabilityReport.observed_at <= cutoff,
                AvailabilityReport.source_updated_at <= cutoff,
                AvailabilityReport.effective_from <= cutoff,
                or_(
                    AvailabilityReport.effective_to.is_(None),
                    AvailabilityReport.effective_to > cutoff,
                ),
            )
        )
        or 0
    )
    expected = _lineup_count(session, event.id, teams, cutoff, "expected")
    confirmed = _lineup_count(session, event.id, teams, cutoff, "confirmed")
    tactics = (
        session.scalar(
            select(func.count())
            .select_from(TacticalSnapshot)
            .where(
                TacticalSnapshot.team_id.in_(teams),
                or_(TacticalSnapshot.event_id == event.id, TacticalSnapshot.event_id.is_(None)),
                TacticalSnapshot.observed_at <= cutoff,
                TacticalSnapshot.source_updated_at <= cutoff,
                TacticalSnapshot.as_of <= cutoff,
            )
        )
        or 0
    )
    tenures = (
        session.scalar(
            select(func.count())
            .select_from(CoachTenure)
            .where(
                CoachTenure.team_id.in_(teams),
                CoachTenure.observed_at <= cutoff,
                CoachTenure.source_updated_at <= cutoff,
                CoachTenure.valid_from <= cutoff,
                or_(CoachTenure.valid_to.is_(None), CoachTenure.valid_to > cutoff),
            )
        )
        or 0
    )
    missing: list[str] = []
    if player_statistics == 0:
        missing.append("historical_player_statistics")
    if availability == 0:
        missing.append("availability_reports")
    if expected + confirmed < 2:
        missing.append("both_team_lineups")
    if tactics < 2:
        missing.append("both_team_tactical_snapshots")
    if tenures < 2:
        missing.append("both_team_coach_tenures")
    total_families = 5
    available_families = total_families - len(missing)
    status = "available" if not missing else "partial" if available_families else "missing"
    return IntelligenceCoverageView(
        event_id=event.id,
        as_of=cutoff,
        historical_player_statistics=player_statistics,
        availability_reports=availability,
        expected_lineups=expected,
        confirmed_lineups=confirmed,
        tactical_snapshots=tactics,
        coach_tenures=tenures,
        status=status,
        missing_inputs=missing,
    )


def _lineup_count(
    session: Session,
    event_id: int,
    teams: tuple[int, int],
    cutoff: datetime,
    lineup_type: str,
) -> int:
    return (
        session.scalar(
            select(func.count())
            .select_from(LineupSnapshot)
            .where(
                LineupSnapshot.event_id == event_id,
                LineupSnapshot.team_id.in_(teams),
                LineupSnapshot.lineup_type == lineup_type,
                LineupSnapshot.observed_at <= cutoff,
                LineupSnapshot.source_updated_at <= cutoff,
            )
        )
        or 0
    )


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
