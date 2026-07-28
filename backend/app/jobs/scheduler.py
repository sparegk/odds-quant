from __future__ import annotations

import logging
import re
from collections import Counter
from collections.abc import Callable, Iterable
from datetime import UTC, datetime, timedelta
from typing import cast

from apscheduler.schedulers.blocking import BlockingScheduler  # type: ignore[import-untyped]
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.collectors.registry import register_odds_provider, registered_odds_providers
from app.core.config import Settings, get_settings
from app.db.models import Event, Provider, ProviderJob
from app.db.session import SessionLocal
from app.providers.api_football import (
    API_FOOTBALL_TERMS_URL,
    ApiFootballClient,
    ApiFootballLeagueCoverage,
)
from app.providers.base import OddsProvider
from app.providers.odds_api_io import OddsApiIoError, OddsApiIoProvider
from app.schemas.fixtures import FixtureImportRow
from app.schemas.odds import OddsImportRow
from app.services.api_football_collection import collect_api_football_intelligence
from app.services.demo_seed import seed_demo_data
from app.services.fixture_import import import_provider_fixtures
from app.services.odds_import import import_odds_csv, serialize_odds_rows_csv
from app.services.research_pipeline import (
    PredictionRefreshSummary,
    refresh_confirmed_lineup_predictions,
    refresh_upcoming_predictions,
)

logger = logging.getLogger("oddsquant.worker")
SessionFactory = Callable[[], Session]
_SENSITIVE_QUERY_PATTERN = re.compile(r"(?i)([?&](?:api[_-]?key|access[_-]?token|token)=)[^&\s]+")
_api_football_coverage_cache: tuple[datetime, list[ApiFootballLeagueCoverage]] | None = None


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class SensitiveQueryFilter(logging.Filter):
    """Redact credentials embedded in third-party request log arguments."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _redact_sensitive_query(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(_redact_log_argument(value) for value in record.args)
        elif isinstance(record.args, dict):
            record.args = {key: _redact_log_argument(value) for key, value in record.args.items()}
        return True


def configure_safe_http_logging() -> None:
    http_logger = logging.getLogger("httpx")
    if not any(isinstance(item, SensitiveQueryFilter) for item in http_logger.filters):
        http_logger.addFilter(SensitiveQueryFilter())


def _redact_log_argument(value: object) -> object:
    if isinstance(value, str) or value.__class__.__name__ == "URL":
        return _redact_sensitive_query(str(value))
    return value


def _redact_sensitive_query(value: str) -> str:
    return _SENSITIVE_QUERY_PATTERN.sub(r"\1[REDACTED]", value)


def run_provider_collection(
    provider_adapter: OddsProvider,
    *,
    session_factory: SessionFactory = SessionLocal,
    now: datetime | None = None,
) -> int:
    started_at = now or datetime.now(UTC)
    supports_fixtures = callable(getattr(provider_adapter, "collect_fixtures", None))
    with session_factory() as session:
        provider = session.scalar(select(Provider).where(Provider.slug == provider_adapter.slug))
        if provider is None:
            provider = Provider(
                slug=provider_adapter.slug,
                name=provider_adapter.name,
                kind=provider_adapter.kind,
                is_demo=provider_adapter.is_demo,
                terms_url=provider_adapter.terms_url,
                capabilities={
                    "fixtures": supports_fixtures,
                    "odds": True,
                    "football": True,
                },
            )
            session.add(provider)
            session.flush()
        elif (
            provider.name != provider_adapter.name
            or provider.kind != provider_adapter.kind
            or provider.is_demo != provider_adapter.is_demo
        ):
            raise ValueError("registered provider metadata conflicts with persisted provider")

        job = ProviderJob(
            provider_id=provider.id,
            job_type="collect_odds",
            status="running",
            finished_at=None,
            message="",
            created_at=started_at,
            metrics={},
        )
        session.add(job)
        session.commit()
        job_id = job.id

    try:
        fixtures = _collect_fixtures(provider_adapter)
        rows = list(provider_adapter.collect_odds())
        collected_at = max(
            [
                datetime.now(UTC),
                *(_utc(row.observed_at) for row in rows),
                *(_utc(fixture.observed_at) for fixture in fixtures),
            ]
        )
        prediction_cutoff = max([started_at, *(_utc(row.observed_at) for row in rows)])
        fixture_result = None
        prediction_summary = None
        if fixtures or rows:
            with session_factory() as import_session:
                fixture_result = import_provider_fixtures(
                    import_session,
                    rows=fixtures,
                    provider_slug=provider_adapter.slug,
                    provider_name=provider_adapter.name,
                    provider_kind=provider_adapter.kind,
                    terms_url=provider_adapter.terms_url,
                    is_demo=provider_adapter.is_demo,
                    now=collected_at,
                )
                if rows:
                    result = import_odds_csv(
                        import_session,
                        filename=(
                            f"provider_{provider_adapter.slug}_{started_at:%Y%m%dT%H%M%SZ}.csv"
                        ),
                        content=serialize_odds_rows_csv(rows),
                        provider_slug=provider_adapter.slug,
                        provider_name=provider_adapter.name,
                        is_demo=provider_adapter.is_demo,
                        now=collected_at,
                    )
                else:
                    import_session.commit()
        if rows:
            with session_factory() as prediction_session:
                prediction_summary = refresh_upcoming_predictions(
                    prediction_session,
                    as_of=prediction_cutoff,
                )
        fixture_message = ""
        if fixture_result is not None and fixture_result.fixtures_received:
            fixture_message = (
                f"Observed {fixture_result.fixtures_received} fixtures "
                f"({fixture_result.events_created} new)"
            )
        if rows:
            odds_message = (
                f"Imported {result.rows_imported} prices across "
                f"{result.snapshots_created} snapshots"
            )
            message = f"{fixture_message}; {odds_message}" if fixture_message else odds_message
        elif fixture_message:
            message = f"{fixture_message}; provider returned no odds rows"
        else:
            message = "Provider returned no fixture or odds rows"
        _finish_job(
            session_factory,
            job_id,
            "completed",
            message,
            started_at,
            metrics=_collection_metrics(fixtures, rows, prediction_summary),
        )
    except Exception as exc:
        error_type = type(exc).__name__
        failure_detail = f": {exc}" if isinstance(exc, OddsApiIoError) and str(exc).strip() else ""
        logger.error(
            "Provider collection failed: provider=%s error_type=%s%s",
            provider_adapter.slug,
            error_type,
            failure_detail,
        )
        _finish_job(
            session_factory,
            job_id,
            "failed",
            f"Collection failed ({error_type}){failure_detail}",
            started_at,
        )
    return job_id


def _collect_fixtures(provider: OddsProvider) -> list[FixtureImportRow]:
    collector = getattr(provider, "collect_fixtures", None)
    if collector is None:
        return []
    typed = cast(Callable[[], Iterable[FixtureImportRow]], collector)
    return list(typed())


def _collection_metrics(
    fixtures: list[FixtureImportRow],
    rows: list[OddsImportRow],
    prediction_summary: PredictionRefreshSummary | None = None,
) -> dict[str, object]:
    fixture_counts = Counter(item.competition for item in fixtures)
    price_counts: dict[str, Counter[str]] = {}
    for row in rows:
        price_counts.setdefault(row.competition, Counter())[row.bookmaker] += 1
    competitions = {
        competition: {
            "fixtures": fixture_counts[competition],
            "bookmakers": dict(sorted(price_counts.get(competition, Counter()).items())),
        }
        for competition in sorted(set(fixture_counts) | set(price_counts))
    }
    metrics: dict[str, object] = {
        "fixtures_received": len(fixtures),
        "prices_received": len(rows),
        "competitions": competitions,
    }
    if prediction_summary is not None:
        metrics["prediction_refresh"] = {
            "eligible_events": prediction_summary.eligible_events,
            "predictions_created": prediction_summary.predictions_created,
            "predictions_reused": prediction_summary.predictions_reused,
            "events_skipped": prediction_summary.events_skipped,
            "skip_reasons": prediction_summary.skip_reasons,
            "research_candidates_available": (prediction_summary.research_candidates_available),
        }
    return metrics


def _finish_job(
    session_factory: SessionFactory,
    job_id: int,
    status: str,
    message: str,
    started_at: datetime,
    metrics: dict[str, object] | None = None,
) -> None:
    with session_factory() as session:
        job = session.get(ProviderJob, job_id)
        if job is None:
            raise RuntimeError(f"provider job {job_id} disappeared")
        job.status = status
        job.finished_at = max(datetime.now(UTC), started_at)
        job.message = message
        job.metrics = metrics or {}
        session.commit()


def poll_registered_providers() -> None:
    providers = registered_odds_providers()
    if not providers:
        logger.info("No external odds provider adapters are registered")
        return
    for provider in providers:
        run_provider_collection(provider)


def adaptive_poll_seconds(
    session: Session,
    *,
    now: datetime,
    base_seconds: int,
    near_kickoff_seconds: int,
    near_kickoff_window_seconds: int,
) -> int:
    current = _utc(now)
    nearest = session.scalar(
        select(Event.kickoff_at)
        .where(
            Event.is_demo.is_(False),
            Event.status == "scheduled",
            Event.kickoff_at > current,
        )
        .order_by(Event.kickoff_at, Event.id)
        .limit(1)
    )
    if nearest is None:
        return base_seconds
    until_kickoff = (_utc(nearest) - current).total_seconds()
    if until_kickoff <= near_kickoff_window_seconds:
        return near_kickoff_seconds
    return base_seconds


def poll_registered_providers_adaptively(
    *,
    settings: Settings | None = None,
    session_factory: SessionFactory = SessionLocal,
    now: datetime | None = None,
) -> int:
    runtime_settings = settings or get_settings()
    current = _utc(now or datetime.now(UTC))
    with session_factory() as session:
        interval = adaptive_poll_seconds(
            session,
            now=current,
            base_seconds=runtime_settings.provider_poll_seconds,
            near_kickoff_seconds=runtime_settings.provider_near_kickoff_poll_seconds,
            near_kickoff_window_seconds=runtime_settings.provider_near_kickoff_window_seconds,
        )
    jobs_started = 0
    for provider_adapter in registered_odds_providers():
        with session_factory() as session:
            provider = session.scalar(
                select(Provider).where(Provider.slug == provider_adapter.slug)
            )
            latest_started = None
            if provider is not None:
                latest_started = session.scalar(
                    select(ProviderJob.created_at)
                    .where(ProviderJob.provider_id == provider.id)
                    .order_by(ProviderJob.created_at.desc(), ProviderJob.id.desc())
                    .limit(1)
                )
        if latest_started is not None:
            elapsed = (current - _utc(latest_started)).total_seconds()
            if elapsed < interval:
                continue
        run_provider_collection(provider_adapter, session_factory=session_factory, now=current)
        jobs_started += 1
    return jobs_started


def register_configured_providers(settings: Settings) -> None:
    if settings.odds_api_io_key:
        register_odds_provider(
            OddsApiIoProvider(
                settings.odds_api_io_key,
                base_url=settings.odds_api_io_base_url,
            )
        )


def poll_api_football_intelligence(
    *,
    settings: Settings | None = None,
    session_factory: SessionFactory = SessionLocal,
    now: datetime | None = None,
) -> int | None:
    runtime_settings = settings or get_settings()
    if not runtime_settings.api_football_key:
        return None
    current = _utc(now or datetime.now(UTC))
    with session_factory() as session:
        provider = session.scalar(select(Provider).where(Provider.slug == "api-football"))
        if provider is not None:
            latest_started = session.scalar(
                select(ProviderJob.created_at)
                .where(ProviderJob.provider_id == provider.id)
                .order_by(ProviderJob.created_at.desc(), ProviderJob.id.desc())
                .limit(1)
            )
            if latest_started is not None:
                elapsed = (current - _utc(latest_started)).total_seconds()
                if elapsed < runtime_settings.api_football_poll_seconds:
                    return None
        if provider is None:
            provider = Provider(
                slug="api-football",
                name="API-Football",
                kind="licensed_api",
                is_demo=False,
                terms_url=API_FOOTBALL_TERMS_URL,
                capabilities={
                    "football_intelligence": True,
                    "acquisition_method": "licensed_api",
                    "usage_authorized": True,
                },
            )
            session.add(provider)
            session.flush()
        job = ProviderJob(
            provider_id=provider.id,
            job_type="collect_football_intelligence",
            status="running",
            finished_at=None,
            message="",
            created_at=current,
            metrics={},
        )
        session.add(job)
        session.commit()
        job_id = job.id
    try:
        global _api_football_coverage_cache
        with ApiFootballClient(
            runtime_settings.api_football_key,
            base_url=runtime_settings.api_football_base_url,
            daily_request_reserve=runtime_settings.api_football_daily_request_reserve,
        ) as client:
            cached = _api_football_coverage_cache
            if cached is None or current - cached[0] >= timedelta(hours=24):
                account = client.account_probe()
                if not account.active:
                    raise RuntimeError("API-Football account is inactive")
                coverage = client.target_coverage().leagues
                _api_football_coverage_cache = (current, coverage)
            else:
                coverage = cached[1]
            with session_factory() as session:
                summary = collect_api_football_intelligence(
                    session,
                    client=client,
                    coverage=coverage,
                    on_date=current.date(),
                    now=current,
                )
        prediction_cutoff = current if now is not None else datetime.now(UTC)
        with session_factory() as prediction_session:
            lineup_prediction_summary = refresh_confirmed_lineup_predictions(
                prediction_session,
                as_of=prediction_cutoff,
            )
        message = (
            f"Matched {summary.fixtures_matched}/{summary.fixtures_seen} API-Football fixtures; "
            f"imported {summary.lineups_imported} lineups, "
            f"{summary.injuries_imported} availability records, and "
            f"{summary.player_snapshots_imported} player snapshots"
        )
        _finish_job(
            session_factory,
            job_id,
            "completed",
            message,
            current,
            metrics={
                **summary.model_dump(mode="json"),
                "confirmed_lineup_prediction_refresh": {
                    "eligible_events": lineup_prediction_summary.eligible_events,
                    "predictions_created": lineup_prediction_summary.predictions_created,
                    "predictions_reused": lineup_prediction_summary.predictions_reused,
                    "events_skipped": lineup_prediction_summary.events_skipped,
                    "research_candidates_available": (
                        lineup_prediction_summary.research_candidates_available
                    ),
                },
            },
        )
    except Exception as exc:
        error_type = type(exc).__name__
        logger.error("API-Football collection failed: error_type=%s", error_type)
        _finish_job(
            session_factory,
            job_id,
            "failed",
            f"Collection failed ({error_type})",
            current,
        )
    return job_id


def seed_development_demo(
    *,
    settings: Settings | None = None,
    session_factory: SessionFactory = SessionLocal,
    now: datetime | None = None,
) -> bool:
    runtime_settings = settings or get_settings()
    if not runtime_settings.seed_demo or runtime_settings.environment.casefold() == "production":
        return False
    current = now or datetime.now(UTC)
    anchor = current.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    with session_factory() as session:
        seed_demo_data(session, as_of=anchor, ingested_at=current)
    return True


def build_scheduler(settings: Settings | None = None) -> BlockingScheduler:
    runtime_settings = settings or get_settings()
    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(
        poll_registered_providers_adaptively,
        "interval",
        seconds=runtime_settings.provider_near_kickoff_poll_seconds,
        id="poll-registered-odds-providers",
        coalesce=True,
        max_instances=1,
        next_run_time=datetime.now(UTC),
        kwargs={"settings": runtime_settings},
    )
    if runtime_settings.api_football_key:
        scheduler.add_job(
            poll_api_football_intelligence,
            "interval",
            seconds=min(
                runtime_settings.api_football_poll_seconds,
                runtime_settings.provider_near_kickoff_poll_seconds,
            ),
            id="poll-api-football-intelligence",
            coalesce=True,
            max_instances=1,
            next_run_time=datetime.now(UTC),
            kwargs={"settings": runtime_settings},
        )
    if runtime_settings.seed_demo and runtime_settings.environment.casefold() != "production":
        scheduler.add_job(
            seed_development_demo,
            "cron",
            hour=0,
            minute=5,
            id="refresh-development-demo-data",
            coalesce=True,
            max_instances=1,
        )
    return scheduler


def main() -> None:
    settings = get_settings()
    configure_safe_http_logging()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    register_configured_providers(settings)
    seed_development_demo(settings=settings)
    scheduler = build_scheduler(settings)
    logger.info("OddsQuant worker started")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("OddsQuant worker stopped")


if __name__ == "__main__":
    main()
