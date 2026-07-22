from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from app.db.models import (
    Bookmaker,
    Competition,
    Event,
    Market,
    MatchResult,
    OddsSnapshot,
    Provider,
)
from app.schemas.api import CompetitionDataCoverage, DataCoverageView

MINIMUM_EVALUATION_RESULTS = 200
REQUIRED_BOOKMAKERS = {
    "allwyn-pamestoixima": "Allwyn / Pamestoixima",
    "novibet": "Novibet",
}


def data_coverage(session: Session) -> DataCoverageView:
    competitions = session.scalars(
        select(Competition)
        .join(Event, Event.competition_id == Competition.id)
        .distinct()
        .order_by(Competition.country, Competition.name, Competition.season)
    ).all()
    rows = [_competition_coverage(session, competition) for competition in competitions]
    return DataCoverageView(
        minimum_evaluation_results=MINIMUM_EVALUATION_RESULTS,
        required_bookmakers=list(REQUIRED_BOOKMAKERS.values()),
        total_events=_count(session, select(func.count(Event.id))),
        permitted_events=sum(row.permitted_events for row in rows),
        permitted_final_results=sum(row.permitted_final_results for row in rows),
        permitted_odds_snapshots=sum(row.permitted_odds_snapshots for row in rows),
        permitted_closing_snapshots=sum(row.permitted_closing_snapshots for row in rows),
        competitions=rows,
    )


def _competition_coverage(
    session: Session,
    competition: Competition,
) -> CompetitionDataCoverage:
    total_events = _count(
        session,
        select(func.count(Event.id)).where(Event.competition_id == competition.id),
    )
    permitted_event_rows = session.execute(
        select(Event.id, Event.home_team_id, Event.away_team_id)
        .join(Provider, Provider.id == Event.provider_id)
        .where(
            Event.competition_id == competition.id,
            Event.is_demo.is_(False),
            Provider.is_demo.is_(False),
        )
    ).all()
    permitted_event_ids = [row.id for row in permitted_event_rows]
    permitted_teams = {
        team_id for row in permitted_event_rows for team_id in (row.home_team_id, row.away_team_id)
    }
    if not permitted_event_ids:
        return CompetitionDataCoverage(
            competition_id=competition.id,
            competition=competition.name,
            country=competition.country,
            season=competition.season,
            total_events=total_events,
            permitted_events=0,
            permitted_teams=0,
            permitted_final_results=0,
            permitted_odds_snapshots=0,
            permitted_closing_snapshots=0,
            covered_required_bookmakers=[],
            missing_required_bookmakers=list(REQUIRED_BOOKMAKERS.values()),
            first_result_kickoff_at=None,
            last_result_kickoff_at=None,
            closing_event_coverage=0,
            evaluation_ready=False,
            blockers=[
                "no_permitted_events",
                "fewer_than_200_final_results",
                "no_timestamped_odds",
                "no_closing_prices",
                "missing_required_bookmakers",
            ],
        )

    result_statement = (
        select(
            func.count(func.distinct(Event.id)),
            func.min(Event.kickoff_at),
            func.max(Event.kickoff_at),
        )
        .join(MatchResult, MatchResult.event_id == Event.id)
        .join(Provider, Provider.id == MatchResult.provider_id)
        .where(
            Event.id.in_(permitted_event_ids),
            MatchResult.is_final.is_(True),
            Provider.is_demo.is_(False),
        )
    )
    result_count, first_result, last_result = session.execute(result_statement).one()
    odds_base = (
        select(func.count(OddsSnapshot.id))
        .join(Market, Market.id == OddsSnapshot.market_id)
        .join(Provider, Provider.id == OddsSnapshot.provider_id)
        .join(Bookmaker, Bookmaker.id == OddsSnapshot.bookmaker_id)
        .where(
            Market.event_id.in_(permitted_event_ids),
            Provider.is_demo.is_(False),
            Bookmaker.is_demo.is_(False),
        )
    )
    odds_count = _count(session, odds_base)
    closing_count = _count(session, odds_base.where(OddsSnapshot.is_closing.is_(True)))
    closing_events = _count(
        session,
        select(func.count(func.distinct(Market.event_id)))
        .join(OddsSnapshot, OddsSnapshot.market_id == Market.id)
        .join(Provider, Provider.id == OddsSnapshot.provider_id)
        .join(Bookmaker, Bookmaker.id == OddsSnapshot.bookmaker_id)
        .where(
            Market.event_id.in_(permitted_event_ids),
            OddsSnapshot.is_closing.is_(True),
            Provider.is_demo.is_(False),
            Bookmaker.is_demo.is_(False),
        ),
    )
    covered_slugs = set(
        session.scalars(
            select(Bookmaker.slug)
            .join(OddsSnapshot, OddsSnapshot.bookmaker_id == Bookmaker.id)
            .join(Market, Market.id == OddsSnapshot.market_id)
            .join(Provider, Provider.id == OddsSnapshot.provider_id)
            .where(
                Market.event_id.in_(permitted_event_ids),
                Provider.is_demo.is_(False),
                Bookmaker.is_demo.is_(False),
                Bookmaker.slug.in_(REQUIRED_BOOKMAKERS),
            )
            .distinct()
        ).all()
    )
    covered_bookmakers = [
        label for slug, label in REQUIRED_BOOKMAKERS.items() if slug in covered_slugs
    ]
    missing_bookmakers = [
        label for slug, label in REQUIRED_BOOKMAKERS.items() if slug not in covered_slugs
    ]
    blockers: list[str] = []
    if result_count < MINIMUM_EVALUATION_RESULTS:
        blockers.append("fewer_than_200_final_results")
    if odds_count == 0:
        blockers.append("no_timestamped_odds")
    if closing_count == 0:
        blockers.append("no_closing_prices")
    if missing_bookmakers:
        blockers.append("missing_required_bookmakers")
    return CompetitionDataCoverage(
        competition_id=competition.id,
        competition=competition.name,
        country=competition.country,
        season=competition.season,
        total_events=total_events,
        permitted_events=len(permitted_event_ids),
        permitted_teams=len(permitted_teams),
        permitted_final_results=result_count,
        permitted_odds_snapshots=odds_count,
        permitted_closing_snapshots=closing_count,
        covered_required_bookmakers=covered_bookmakers,
        missing_required_bookmakers=missing_bookmakers,
        first_result_kickoff_at=first_result,
        last_result_kickoff_at=last_result,
        closing_event_coverage=closing_events / len(permitted_event_ids),
        evaluation_ready=not blockers,
        blockers=blockers,
    )


def _count(session: Session, statement: Select[tuple[int]]) -> int:
    value = session.scalar(statement)
    return int(value or 0)
