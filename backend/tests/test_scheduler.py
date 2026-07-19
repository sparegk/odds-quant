from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
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
from app.db.models import OddsSnapshot, ProviderJob
from app.db.session import Base
from app.jobs.scheduler import run_provider_collection, seed_development_demo
from app.schemas.odds import OddsImportRow
from app.services.demo_seed import build_demo_odds_csv
from app.services.odds_import import parse_odds_csv

AS_OF = datetime(2026, 7, 19, 10, 0, tzinfo=UTC)


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
