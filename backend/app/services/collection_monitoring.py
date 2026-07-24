from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Provider, ProviderJob
from app.schemas.api import CollectionAlert, CollectionMonitoringView, ProviderCollectionHealth
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
    alerts = _collection_alerts(session, providers, health, limit)
    return _monitoring_view(session, poll, now, limit, health, alerts)


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
    session: Session,
    poll: int,
    now: datetime,
    limit: int,
    health: list[ProviderCollectionHealth],
    alerts: list[CollectionAlert],
) -> CollectionMonitoringView:
    return CollectionMonitoringView(
        observed_at=now,
        expected_poll_seconds=poll,
        recent_job_limit=limit,
        healthy=bool(health) and all(item.healthy for item in health) and not alerts,
        providers=health,
        alerts=alerts,
        coverage=data_coverage(session),
    )


def _collection_alerts(
    session: Session,
    providers: list[Provider],
    health: list[ProviderCollectionHealth],
    limit: int,
) -> list[CollectionAlert]:
    health_by_provider = {item.provider_id: item for item in health}
    alerts: list[CollectionAlert] = []
    for provider in providers:
        item = health_by_provider[provider.id]
        alerts.extend(_health_alerts(item))
        jobs = _provider_jobs(session, provider.id, limit)
        alerts.extend(_coverage_regression_alerts(provider, jobs))
    return alerts


def _health_alerts(health: ProviderCollectionHealth) -> list[CollectionAlert]:
    alerts: list[CollectionAlert] = []
    if "latest_provider_success_stale" in health.blockers:
        alerts.append(
            CollectionAlert(
                code="provider_collection_stale",
                severity="critical",
                provider_slug=health.provider_slug,
                detail="Latest successful provider collection exceeded two expected intervals.",
            )
        )
    if health.latest_job_status == "failed":
        alerts.append(
            CollectionAlert(
                code="provider_collection_failed",
                severity="critical",
                provider_slug=health.provider_slug,
                detail="Latest provider collection failed.",
            )
        )
    elif health.failures_in_recent_window >= 2:
        alerts.append(
            CollectionAlert(
                code="repeated_provider_failures",
                severity="warning",
                provider_slug=health.provider_slug,
                detail="At least two provider collections failed in the recent job window.",
            )
        )
    return alerts


def _coverage_regression_alerts(
    provider: Provider, jobs: list[ProviderJob]
) -> list[CollectionAlert]:
    completed = [job for job in jobs if job.status == "completed" and job.metrics]
    if len(completed) < 2:
        return []
    latest = _job_competition_coverage(completed[0])
    previous = _job_competition_coverage(completed[1])
    alerts: list[CollectionAlert] = []
    for competition in sorted(set(latest) & set(previous)):
        missing = previous[competition] - latest[competition]
        for bookmaker in sorted(missing):
            alerts.append(
                CollectionAlert(
                    code="bookmaker_coverage_regressed",
                    severity="warning",
                    provider_slug=provider.slug,
                    competition=competition,
                    bookmaker=bookmaker,
                    detail=(
                        "Bookmaker supplied prices in the previous completed collection but "
                        "not in the latest completed collection for this active competition."
                    ),
                )
            )
    return alerts


def _job_competition_coverage(job: ProviderJob) -> dict[str, set[str]]:
    competitions = job.metrics.get("competitions")
    if not isinstance(competitions, dict):
        return {}
    coverage: dict[str, set[str]] = {}
    for competition, value in competitions.items():
        if not isinstance(competition, str) or not isinstance(value, dict):
            continue
        bookmakers = value.get("bookmakers")
        if not isinstance(bookmakers, dict):
            continue
        coverage[competition] = {
            bookmaker
            for bookmaker, count in bookmakers.items()
            if isinstance(bookmaker, str)
            and isinstance(count, int)
            and not isinstance(count, bool)
            and count > 0
        }
    return coverage


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
