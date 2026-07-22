from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from typing import cast

from apscheduler.schedulers.blocking import BlockingScheduler  # type: ignore[import-untyped]
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.collectors.registry import register_odds_provider, registered_odds_providers
from app.core.config import Settings, get_settings
from app.db.models import Provider, ProviderJob
from app.db.session import SessionLocal
from app.providers.base import OddsProvider
from app.providers.odds_api_io import OddsApiIoProvider
from app.schemas.fixtures import FixtureImportRow
from app.services.demo_seed import seed_demo_data
from app.services.fixture_import import import_provider_fixtures
from app.services.odds_import import import_odds_csv, serialize_odds_rows_csv

logger = logging.getLogger("oddsquant.worker")
SessionFactory = Callable[[], Session]


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
        )
        session.add(job)
        session.commit()
        job_id = job.id

    try:
        fixtures = _collect_fixtures(provider_adapter)
        rows = list(provider_adapter.collect_odds())
        collected_at = datetime.now(UTC)
        fixture_result = None
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
        _finish_job(session_factory, job_id, "completed", message, started_at)
    except Exception as exc:
        error_type = type(exc).__name__
        logger.error(
            "Provider collection failed: provider=%s error_type=%s",
            provider_adapter.slug,
            error_type,
        )
        _finish_job(
            session_factory,
            job_id,
            "failed",
            f"Collection failed ({error_type})",
            started_at,
        )
    return job_id


def _collect_fixtures(provider: OddsProvider) -> list[FixtureImportRow]:
    collector = getattr(provider, "collect_fixtures", None)
    if collector is None:
        return []
    typed = cast(Callable[[], Iterable[FixtureImportRow]], collector)
    return list(typed())


def _finish_job(
    session_factory: SessionFactory,
    job_id: int,
    status: str,
    message: str,
    started_at: datetime,
) -> None:
    with session_factory() as session:
        job = session.get(ProviderJob, job_id)
        if job is None:
            raise RuntimeError(f"provider job {job_id} disappeared")
        job.status = status
        job.finished_at = max(datetime.now(UTC), started_at)
        job.message = message
        session.commit()


def poll_registered_providers() -> None:
    providers = registered_odds_providers()
    if not providers:
        logger.info("No external odds provider adapters are registered")
        return
    for provider in providers:
        run_provider_collection(provider)


def register_configured_providers(settings: Settings) -> None:
    if settings.odds_api_io_key:
        register_odds_provider(
            OddsApiIoProvider(
                settings.odds_api_io_key,
                base_url=settings.odds_api_io_base_url,
            )
        )


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
        poll_registered_providers,
        "interval",
        seconds=runtime_settings.provider_poll_seconds,
        id="poll-registered-odds-providers",
        coalesce=True,
        max_instances=1,
        next_run_time=datetime.now(UTC),
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
