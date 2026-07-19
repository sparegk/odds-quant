from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from app.db.models import (
    Bookmaker,
    Competition,
    Event,
    ImportJob,
    Market,
    OddsPrice,
    OddsSnapshot,
    Provider,
    ProviderJob,
    Selection,
    Team,
)
from app.quant.odds import (
    bookmaker_margin,
    devig_power,
    devig_proportional,
    fair_odds,
    implied_probability,
    overround,
)
from app.schemas.api import (
    BestPrice,
    EventSummary,
    ImportJobView,
    MarketComparison,
    PriceComparison,
    ProviderJobView,
    ProviderSummary,
    SnapshotComparison,
)


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def list_events(
    session: Session,
    *,
    offset: int = 0,
    limit: int = 50,
    include_past: bool = False,
    now: datetime | None = None,
) -> list[EventSummary]:
    home = aliased(Team)
    away = aliased(Team)
    latest_odds = (
        select(func.max(OddsSnapshot.observed_at))
        .join(Market, Market.id == OddsSnapshot.market_id)
        .where(Market.event_id == Event.id)
        .correlate(Event)
        .scalar_subquery()
    )
    statement = (
        select(Event, Competition, home.name, away.name, latest_odds)
        .join(Competition, Competition.id == Event.competition_id)
        .join(home, home.id == Event.home_team_id)
        .join(away, away.id == Event.away_team_id)
        .order_by(Event.kickoff_at, Event.id)
        .offset(offset)
        .limit(limit)
    )
    if not include_past:
        reference = now or datetime.now(UTC)
        statement = statement.where(Event.kickoff_at >= reference)
    return [
        EventSummary(
            id=event.id,
            provider_event_key=event.provider_event_key,
            competition=competition.name,
            country=competition.country,
            season=competition.season,
            home_team=home_name,
            away_team=away_name,
            kickoff_at=_utc(event.kickoff_at),
            status=event.status,
            is_demo=event.is_demo,
            latest_odds_at=_utc(latest) if latest is not None else None,
        )
        for event, competition, home_name, away_name, latest in session.execute(statement)
    ]


def get_event(session: Session, event_id: int) -> EventSummary | None:
    home = aliased(Team)
    away = aliased(Team)
    latest_odds = (
        select(func.max(OddsSnapshot.observed_at))
        .join(Market, Market.id == OddsSnapshot.market_id)
        .where(Market.event_id == Event.id)
        .correlate(Event)
        .scalar_subquery()
    )
    row = session.execute(
        select(Event, Competition, home.name, away.name, latest_odds)
        .join(Competition, Competition.id == Event.competition_id)
        .join(home, home.id == Event.home_team_id)
        .join(away, away.id == Event.away_team_id)
        .where(Event.id == event_id)
    ).one_or_none()
    if row is None:
        return None
    event, competition, home_name, away_name, latest = row
    return EventSummary(
        id=event.id,
        provider_event_key=event.provider_event_key,
        competition=competition.name,
        country=competition.country,
        season=competition.season,
        home_team=home_name,
        away_team=away_name,
        kickoff_at=_utc(event.kickoff_at),
        status=event.status,
        is_demo=event.is_demo,
        latest_odds_at=_utc(latest) if latest is not None else None,
    )


def list_providers(session: Session) -> list[ProviderSummary]:
    providers = session.scalars(select(Provider).order_by(Provider.name)).all()
    results: list[ProviderSummary] = []
    for provider in providers:
        event_count = session.scalar(
            select(func.count()).select_from(Event).where(Event.provider_id == provider.id)
        )
        snapshot_count = session.scalar(
            select(func.count())
            .select_from(OddsSnapshot)
            .where(OddsSnapshot.provider_id == provider.id)
        )
        results.append(
            ProviderSummary(
                id=provider.id,
                slug=provider.slug,
                name=provider.name,
                kind=provider.kind,
                is_demo=provider.is_demo,
                terms_url=provider.terms_url,
                capabilities=provider.capabilities,
                event_count=event_count or 0,
                snapshot_count=snapshot_count or 0,
            )
        )
    return results


def list_import_jobs(session: Session, *, limit: int = 50) -> list[ImportJobView]:
    jobs = session.scalars(
        select(ImportJob).order_by(ImportJob.created_at.desc(), ImportJob.id.desc()).limit(limit)
    ).all()
    return [_import_view(job) for job in jobs]


def get_import_job(session: Session, job_id: int) -> ImportJobView | None:
    job = session.get(ImportJob, job_id)
    return _import_view(job) if job is not None else None


def list_provider_jobs(session: Session, *, limit: int = 50) -> list[ProviderJobView]:
    rows = session.execute(
        select(ProviderJob, Provider.name)
        .join(Provider, Provider.id == ProviderJob.provider_id)
        .order_by(ProviderJob.created_at.desc(), ProviderJob.id.desc())
        .limit(limit)
    )
    return [
        ProviderJobView(
            id=job.id,
            provider_id=job.provider_id,
            provider=provider_name,
            job_type=job.job_type,
            status=job.status,
            message=job.message,
            created_at=_utc(job.created_at),
            finished_at=_utc(job.finished_at) if job.finished_at is not None else None,
        )
        for job, provider_name in rows
    ]


def _import_view(job: ImportJob) -> ImportJobView:
    return ImportJobView(
        id=job.id,
        filename=job.filename,
        status=job.status,
        rows_received=job.rows_received,
        rows_imported=job.rows_imported,
        errors=job.errors,
        created_at=_utc(job.created_at),
    )


def odds_comparison(
    session: Session,
    *,
    event_id: int,
    as_of: datetime | None = None,
    stale_after_seconds: int = 300,
) -> list[MarketComparison]:
    reference = _utc(as_of or datetime.now(UTC))
    rows = session.execute(
        select(
            Market,
            OddsSnapshot,
            Bookmaker,
            Provider,
            Selection,
            OddsPrice.decimal_odds,
        )
        .join(OddsSnapshot, OddsSnapshot.market_id == Market.id)
        .join(Bookmaker, Bookmaker.id == OddsSnapshot.bookmaker_id)
        .join(Provider, Provider.id == OddsSnapshot.provider_id)
        .join(OddsPrice, OddsPrice.snapshot_id == OddsSnapshot.id)
        .join(Selection, Selection.id == OddsPrice.selection_id)
        .where(Market.event_id == event_id, OddsSnapshot.observed_at <= reference)
        .order_by(OddsSnapshot.observed_at.desc(), OddsSnapshot.id, Selection.code)
    ).all()

    snapshot_rows: dict[
        int, list[tuple[Market, OddsSnapshot, Bookmaker, Provider, Selection, Decimal]]
    ] = defaultdict(list)
    for market, snapshot, bookmaker, provider, selection, price in rows:
        snapshot_rows[snapshot.id].append((market, snapshot, bookmaker, provider, selection, price))

    latest_snapshot_ids: set[int] = set()
    seen_bookmaker_market: set[tuple[int, int]] = set()
    for market, snapshot, bookmaker, _, _, _ in rows:
        identity = (market.id, bookmaker.id)
        if identity not in seen_bookmaker_market:
            seen_bookmaker_market.add(identity)
            latest_snapshot_ids.add(snapshot.id)

    markets: dict[int, list[SnapshotComparison]] = defaultdict(list)
    market_models: dict[int, Market] = {}
    for snapshot_id in latest_snapshot_ids:
        grouped = snapshot_rows[snapshot_id]
        market, snapshot, bookmaker, provider, _, _ = grouped[0]
        market_models[market.id] = market
        decimal_odds = [float(row[5]) for row in grouped]
        proportional = devig_proportional(decimal_odds)
        power = devig_power(decimal_odds)
        observed_at = _utc(snapshot.observed_at)
        freshness = max(0, int((reference - observed_at).total_seconds()))
        prices = [
            PriceComparison(
                selection_code=row[4].code,
                selection_name=row[4].name,
                decimal_odds=odds,
                raw_implied_probability=implied_probability(odds),
                proportional_fair_probability=proportional[index],
                proportional_fair_odds=fair_odds(proportional[index]),
                power_fair_probability=power[index],
                power_fair_odds=fair_odds(power[index]),
            )
            for index, (row, odds) in enumerate(zip(grouped, decimal_odds, strict=True))
        ]
        markets[market.id].append(
            SnapshotComparison(
                snapshot_id=snapshot.id,
                bookmaker_id=bookmaker.id,
                bookmaker=bookmaker.name,
                provider=provider.name,
                observed_at=observed_at,
                source_updated_at=(
                    _utc(snapshot.source_updated_at)
                    if snapshot.source_updated_at is not None
                    else None
                ),
                is_closing=snapshot.is_closing,
                is_demo=provider.is_demo,
                source_label=snapshot.source_label,
                freshness_seconds=freshness,
                is_stale=freshness > stale_after_seconds,
                overround=overround(decimal_odds),
                bookmaker_margin=bookmaker_margin(decimal_odds),
                prices=prices,
            )
        )

    results: list[MarketComparison] = []
    for market_id, snapshots in markets.items():
        market = market_models[market_id]
        best_by_code: dict[str, BestPrice] = {}
        for snapshot in snapshots:
            for price in snapshot.prices:
                current = best_by_code.get(price.selection_code)
                if current is None or price.decimal_odds > current.decimal_odds:
                    best_by_code[price.selection_code] = BestPrice(
                        selection_code=price.selection_code,
                        selection_name=price.selection_name,
                        bookmaker=snapshot.bookmaker,
                        decimal_odds=price.decimal_odds,
                        observed_at=snapshot.observed_at,
                        freshness_seconds=snapshot.freshness_seconds,
                    )
        results.append(
            MarketComparison(
                market_id=market.id,
                market_type=market.market_type,
                line=float(market.line) if market.line is not None else None,
                period=market.period,
                currency=market.currency,
                settlement_rule_key=market.settlement_rule_key,
                snapshots=sorted(snapshots, key=lambda value: value.bookmaker),
                best_prices=sorted(best_by_code.values(), key=lambda value: value.selection_code),
            )
        )
    return sorted(results, key=lambda value: (value.market_type, value.line or 0.0))
