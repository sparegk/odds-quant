from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db.models import LineupSnapshot, Player
from app.db.session import Base
from app.providers.api_football import ApiFootballClient, ApiFootballLeagueCoverage
from app.schemas.fixtures import FixtureImportRow
from app.services.api_football_collection import collect_api_football_intelligence
from app.services.fixture_import import import_provider_fixtures

NOW = datetime(2026, 7, 28, 17, 30, tzinfo=UTC)
KICKOFF = NOW + timedelta(minutes=30)


def _envelope(response: list[object]) -> dict[str, object]:
    return {"errors": [], "results": len(response), "response": response}


def _coverage() -> list[ApiFootballLeagueCoverage]:
    return [
        ApiFootballLeagueCoverage(
            league_id=2,
            name="UEFA Champions League",
            country="World",
            season=2026,
            current=True,
            fixtures=True,
            lineups=True,
            player_statistics=True,
            players=True,
            injuries=False,
        )
    ]


def _lineup(team_id: int, team_name: str, first_player: int) -> dict[str, object]:
    return {
        "team": {"id": team_id, "name": team_name},
        "formation": "4-3-3",
        "startXI": [
            {
                "player": {
                    "id": first_player + index,
                    "name": f"{team_name} Player {index + 1}",
                    "pos": "G" if index == 0 else "D",
                }
            }
            for index in range(11)
        ],
        "substitutes": [],
    }


def _session(tmp_path: Path, *, home_name: str = "Northbridge") -> Session:
    engine = create_engine(f"sqlite:///{tmp_path}/collection.db")
    Base.metadata.create_all(engine)
    session = Session(engine)
    import_provider_fixtures(
        session,
        rows=[
            FixtureImportRow(
                provider_event_key="local-1",
                competition="UEFA Champions League Qualification",
                country="International",
                season="2026/27",
                kickoff_at=KICKOFF,
                home_team=home_name,
                away_team="Harbour Athletic",
                observed_at=NOW - timedelta(hours=1),
            )
        ],
        provider_slug="licensed-fixtures",
        provider_name="Licensed fixtures",
        provider_kind="licensed_api",
        terms_url="https://example.test/terms",
        is_demo=False,
        now=NOW,
    )
    session.commit()
    return session


def test_collector_imports_only_exactly_matched_confirmed_lineups(tmp_path: Path) -> None:
    session = _session(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        headers = {
            "date": "Tue, 28 Jul 2026 17:29:55 GMT",
            "x-ratelimit-requests-remaining": "90",
        }
        if request.url.path.endswith("/fixtures/lineups"):
            return httpx.Response(
                200,
                headers=headers,
                json=_envelope(
                    [
                        _lineup(51, "Northbridge", 700),
                        _lineup(52, "Harbour Athletic", 800),
                    ]
                ),
            )
        return httpx.Response(
            200,
            headers=headers,
            json=_envelope(
                [
                    {
                        "fixture": {
                            "id": 9001,
                            "date": KICKOFF.isoformat(),
                            "status": {"short": "NS"},
                        },
                        "league": {
                            "id": 2,
                            "name": "UEFA Champions League",
                            "season": 2026,
                        },
                        "teams": {
                            "home": {"id": 51, "name": "Northbridge"},
                            "away": {"id": 52, "name": "Harbour Athletic"},
                        },
                    }
                ]
            ),
        )

    with ApiFootballClient(
        "test-key",
        transport=httpx.MockTransport(handler),
        clock=lambda: NOW,
    ) as client:
        summary = collect_api_football_intelligence(
            session,
            client=client,
            coverage=_coverage(),
            on_date=date(2026, 7, 28),
            now=NOW,
        )

    assert summary.fixtures_matched == 1
    assert summary.lineups_imported == 2
    assert session.scalar(select(func.count()).select_from(LineupSnapshot)) == 2
    assert session.scalar(select(func.count()).select_from(Player)) == 22
    session.close()


def test_collector_refuses_near_name_matches(tmp_path: Path) -> None:
    session = _session(tmp_path, home_name="Northbridge FC")
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        return httpx.Response(
            200,
            headers={"date": "Tue, 28 Jul 2026 17:29:55 GMT"},
            json=_envelope(
                [
                    {
                        "fixture": {
                            "id": 9001,
                            "date": KICKOFF.isoformat(),
                            "status": {"short": "NS"},
                        },
                        "league": {
                            "id": 2,
                            "name": "UEFA Champions League",
                            "season": 2026,
                        },
                        "teams": {
                            "home": {"id": 51, "name": "Northbridge"},
                            "away": {"id": 52, "name": "Harbour Athletic"},
                        },
                    }
                ]
            ),
        )

    with ApiFootballClient(
        "test-key",
        transport=httpx.MockTransport(handler),
        clock=lambda: NOW,
    ) as client:
        summary = collect_api_football_intelligence(
            session,
            client=client,
            coverage=_coverage(),
            on_date=date(2026, 7, 28),
            now=NOW,
        )

    assert summary.fixtures_matched == 0
    assert summary.fixtures_unmatched == 1
    assert requests == ["/fixtures"]
    session.close()
