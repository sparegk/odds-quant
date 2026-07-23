from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Provider, ProviderJob
from app.schemas.api import CollectionMonitoringView, ProviderCollectionHealth
from app.services.data_coverage import data_coverage


def collection_monitoring(
    session: Session,
    *,
    expected_poll_seconds: int,
    now: datetime | None = None,
    recent_job_limit: int = 10,
) -> CollectionMonitoringView:
    if not expected_poll_seconds >= 1 or not recent_job_limit >= 2:
        raise ValueError("invalid monitoring interval or limit")
    observed_at = _utc(now or datetime.now(UTC))
    return _build_monitoring(session, expected_poll_seconds, observed_at, recent_job_limit)


def _build_monitoring(
    session: Session, poll: int, now: datetime, limit: int
) -> CollectionMonitoringView:
    providers = _provider_rows(session)
    health = [_provider_health(session, item, poll, now, limit) for item in providers]
    return _monitoring_view(session, poll, now, limit, health)


def _provider_rows(session: Session) -> list[Provider]:
    return list(
        session.scalars(
            select(Provider).where(
                Provider.is_demo.is_(False),
                Provider.id.in_(select(ProviderJob.provider_id).distinct()),
            )
        ).all()
    )


def _monitoring_view(
    session: Session, poll: int, now: datetime, limit: int, health: list[ProviderCollectionHealth]
) -> CollectionMonitoringView:
    return CollectionMonitoringView(
        observed_at=now,
        expected_poll_seconds=poll,
        recent_job_limit=limit,
        healthy=bool(health) and all(item.healthy for item in health),
        providers=health,
        coverage=data_coverage(session),
    )


def _provider_jobs(session: Session, provider_id: int, limit: int) -> list[ProviderJob]:
    return list(
        session.scalars(
            select(ProviderJob)
            .where(ProviderJob.provider_id == provider_id)
            .order_by(ProviderJob.created_at.desc(), ProviderJob.id.desc())
            .limit(limit)
        ).all()
    )


def _completed_streak(jobs: list[ProviderJob]) -> int:
    count = 0
    for job in jobs:
        if job.status != "completed":
            break
        count += 1
    return count


def _age(now: datetime, value: datetime | None) -> int | None:
    if value is None:
        return None
    return max(0, int((now - _utc(value)).total_seconds()))


def _blockers(
    terminal: list[ProviderJob],
    streak: int,
    success_age: int | None,
    running_age: int | None,
    poll: int,
) -> list[str]:
    blockers: list[str] = []
    if not terminal or terminal[0].status != "completed":
        blockers.append("latest_provider_job_not_completed")
    if not streak >= 2:
        blockers.append("fewer_than_two_consecutive_completed_jobs")
    if success_age is None or success_age > poll * 2:
        blockers.append("latest_provider_success_stale")
    if running_age is not None and running_age > poll:
        blockers.append("provider_job_running_too_long")
    return blockers


def _provider_health(
    session: Session, provider: Provider, poll: int, now: datetime, limit: int
) -> ProviderCollectionHealth:
    jobs = _provider_jobs(session, provider.id, limit)
    latest = jobs[0]
    running = latest if latest.status == "running" else None
    terminal = [job for job in jobs if job.status != "running"]
    success = next((job for job in terminal if job.status == "completed"), None)
    streak = _completed_streak(terminal)
    success_age = _age(now, success.finished_at if success is not None else None)
    running_age = _age(now, running.created_at if running is not None else None)
    blockers = _blockers(terminal, streak, success_age, running_age, poll)
    return _health_view(provider, latest, success, streak, jobs, success_age, running_age, blockers)


def _health_view(
    provider: Provider,
    latest: ProviderJob,
    success: ProviderJob | None,
    streak: int,
    jobs: list[ProviderJob],
    success_age: int | None,
    running_age: int | None,
    blockers: list[str],
) -> ProviderCollectionHealth:
    return ProviderCollectionHealth(
        provider_id=provider.id,
        provider=provider.name,
        provider_slug=provider.slug,
        latest_job_id=latest.id,
        latest_job_status=latest.status,
        latest_job_created_at=_utc(latest.created_at),
        latest_job_finished_at=_utc(latest.finished_at) if latest.finished_at else None,
        latest_success_at=_utc(success.finished_at) if success and success.finished_at else None,
        consecutive_completed_jobs=streak,
        failures_in_recent_window=sum(job.status == "failed" for job in jobs),
        running_job_age_seconds=running_age,
        latest_success_age_seconds=success_age,
        healthy=not blockers,
        blockers=blockers,
    )


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
