from __future__ import annotations

import logging
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.collectors.registry import (
    clear_provider_registry,
    register_odds_provider,
    registered_odds_providers,
)
from app.core.config import Settings
from app.db.models import Event, FixtureObservation, OddsSnapshot, ProviderJob
from app.db.session import Base
from app.jobs.scheduler import (
    SensitiveQueryFilter,
    register_configured_providers,
    run_provider_collection,
    seed_development_demo,
)
from app.schemas.fixtures import FixtureImportRow
from app.schemas.odds import OddsImportRow
from app.services.demo_seed import build_demo_odds_csv
from app.services.odds_import import parse_odds_csv

AS_OF = datetime(2026, 7, 19, 10, 0, tzinfo=UTC)
LOG_SECRET = "credential-that-must-never-be-logged"


class FakeLicensedProvider:
    slug: str = "licensed-test-feed"
    name: str = "Licensed test feed"
    kind: str = "licensed_api"
    is_demo: bool = False
    terms_url: str | None = "https://example.test/terms"

    def __init__(self, rows: list[OddsImportRow]) -> None:
        self.rows = rows

    def collect_odds(self) -> Iterable[OddsImportRow]:
        return self.rows


class FailingProvider(FakeLicensedProvider):
    def collect_odds(self) -> Iterable[OddsImportRow]:
        raise RuntimeError("secret-token-must-not-be-persisted")


class FixtureOnlyProvider(FakeLicensedProvider):
    def __init__(self, fixtures: list[FixtureImportRow]) -> None:
        super().__init__([])
        self.fixtures = fixtures

    def collect_fixtures(self) -> Iterable[FixtureImportRow]:
        return self.fixtures


@pytest.fixture(autouse=True)
def empty_registry() -> Iterator[None]:
    clear_provider_registry()
    yield
    clear_provider_registry()


@pytest.fixture
def sessions(tmp_path: Path) -> sessionmaker[Session]:
    engine = create_engine(f"sqlite:///{tmp_path}/worker.db")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _provider_rows() -> list[OddsImportRow]:
    content = build_demo_odds_csv(AS_OF).replace(b"Demo Atlas Sports", b"Licensed Atlas Sports")
    content = content.replace(b"Demo Beacon Bet", b"Licensed Beacon Bet")
    return parse_odds_csv(content, now=AS_OF)


def test_registered_provider_collection_records_completed_job(
    sessions: sessionmaker[Session],
) -> None:
    provider = FakeLicensedProvider(_provider_rows())
    register_odds_provider(provider)

    job_id = run_provider_collection(provider, session_factory=sessions, now=AS_OF)

    assert [item.slug for item in registered_odds_providers()] == [provider.slug]
    with sessions() as session:
        job = session.get(ProviderJob, job_id)
        assert job is not None
        assert job.status == "completed"
        assert job.message == "Imported 24 prices across 8 snapshots"
        assert session.scalar(select(func.count()).select_from(OddsSnapshot)) == 8


def test_registered_provider_persists_fixture_without_supported_odds(
    sessions: sessionmaker[Session],
) -> None:
    provider = FixtureOnlyProvider(
        [
            FixtureImportRow(
                provider_event_key="ucl-321",
                competition="UEFA Champions League Qualification",
                country="International",
                season="2026/27",
                kickoff_at=AS_OF + timedelta(days=1),
                home_team="Northbridge FC",
                away_team="Harbour Athletic",
                observed_at=AS_OF,
            )
        ]
    )

    job_id = run_provider_collection(provider, session_factory=sessions, now=AS_OF)

    with sessions() as session:
        job = session.get(ProviderJob, job_id)
        assert job is not None
        assert job.status == "completed"
        assert job.message == "Observed 1 fixtures (1 new); provider returned no odds rows"
        assert session.scalar(select(func.count()).select_from(Event)) == 1
        assert session.scalar(select(func.count()).select_from(FixtureObservation)) == 1
        assert session.scalar(select(func.count()).select_from(OddsSnapshot)) == 0


def test_collection_cutoff_is_recorded_after_provider_observation(
    sessions: sessionmaker[Session],
) -> None:
    observed_after_start = [
        row.model_copy(update={"observed_at": AS_OF + timedelta(seconds=1)})
        for row in _provider_rows()
    ]
    provider = FakeLicensedProvider(observed_after_start)

    job_id = run_provider_collection(provider, session_factory=sessions, now=AS_OF)

    with sessions() as session:
        job = session.get(ProviderJob, job_id)
        assert job is not None
        assert job.status == "completed"
        assert session.scalar(select(func.count()).select_from(OddsSnapshot)) == 8


def test_provider_failure_is_recorded_without_exception_secrets(
    sessions: sessionmaker[Session],
) -> None:
    provider = FailingProvider([])

    job_id = run_provider_collection(provider, session_factory=sessions, now=AS_OF)

    with sessions() as session:
        job = session.get(ProviderJob, job_id)
        assert job is not None
        assert job.status == "failed"
        assert job.message == "Collection failed (RuntimeError)"
        assert "secret-token" not in job.message


def test_registry_rejects_unverified_scheduled_provider() -> None:
    provider = FakeLicensedProvider([])
    provider.terms_url = None

    with pytest.raises(ValueError, match="terms or source URL"):
        register_odds_provider(provider)


def test_production_never_seeds_demo_data(sessions: sessionmaker[Session]) -> None:
    settings = Settings(environment="production", seed_demo=True)

    seeded = seed_development_demo(
        settings=settings,
        session_factory=sessions,
        now=AS_OF,
    )

    assert seeded is False
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(OddsSnapshot)) == 0


def test_render_postgres_url_selects_installed_psycopg_driver() -> None:
    settings = Settings(database_url="postgresql://user:password@db:5432/oddsquant")
    assert settings.database_url == "postgresql+psycopg://user:password@db:5432/oddsquant"


def test_configured_odds_api_provider_is_registered() -> None:
    register_configured_providers(
        Settings(
            odds_api_io_key="configured-test-key",
            odds_api_io_base_url="https://provider.example/v3",
        )
    )

    providers = registered_odds_providers()

    assert len(providers) == 1
    assert providers[0].slug == "odds-api-io"
    assert providers[0].kind == "licensed_api"
    assert providers[0].is_demo is False


@pytest.mark.parametrize("parameter", ["apiKey", "api_key", "token", "access_token"])
def test_sensitive_query_filter_redacts_http_credentials(parameter: str) -> None:
    record = logging.LogRecord(
        "httpx",
        logging.INFO,
        __file__,
        1,
        'HTTP Request: GET %s "HTTP/1.1 200 OK"',
        (f"https://provider.example/events?league=epl&{parameter}={LOG_SECRET}&limit=5",),
        None,
    )

    assert SensitiveQueryFilter().filter(record) is True

    rendered = record.getMessage()
    assert LOG_SECRET not in rendered
    assert f"{parameter}=[REDACTED]" in rendered
