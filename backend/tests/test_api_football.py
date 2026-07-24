from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from app.providers.api_football import ApiFootballClient, ApiFootballError

SECRET = "never-print-this-api-football-key"


def _envelope(response: object) -> dict[str, object]:
    return {
        "get": "test",
        "parameters": [],
        "errors": [],
        "results": len(response) if isinstance(response, list) else 1,
        "paging": {"current": 1, "total": 1},
        "response": response,
    }


def _league(
    league_id: int,
    name: str,
    country: str,
    *,
    lineups: bool,
    player_statistics: bool,
    injuries: bool,
) -> dict[str, object]:
    return {
        "league": {"id": league_id, "name": name},
        "country": {"name": country},
        "seasons": [
            {
                "year": 2026,
                "current": True,
                "coverage": {
                    "fixtures": {
                        "events": True,
                        "lineups": lineups,
                        "statistics_fixtures": True,
                        "statistics_players": player_statistics,
                    },
                    "players": player_statistics,
                    "injuries": injuries,
                },
            }
        ],
    }


def test_account_probe_uses_header_auth_and_never_exposes_secret() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-apisports-key"] == SECRET
        assert SECRET not in str(request.url)
        return httpx.Response(
            200,
            headers={"x-ratelimit-requests-remaining": "97"},
            json=_envelope(
                {
                    "subscription": {"plan": "Free", "active": True},
                    "requests": {"current": 3, "limit_day": 100},
                }
            ),
        )

    with ApiFootballClient(SECRET, transport=httpx.MockTransport(handler)) as client:
        probe = client.account_probe()

    assert probe.plan == "Free"
    assert probe.active is True
    assert probe.requests_remaining == 97
    assert client.requests_remaining == 97
    assert SECRET not in repr(probe)


def test_target_coverage_matches_id_name_and_country_and_fails_closed() -> None:
    rows = [
        _league(
            39,
            "Premier League",
            "England",
            lineups=False,
            player_statistics=False,
            injuries=False,
        ),
        _league(
            2,
            "UEFA Champions League",
            "World",
            lineups=True,
            player_statistics=True,
            injuries=False,
        ),
        _league(
            39,
            "Premier League",
            "Namibia",
            lineups=True,
            player_statistics=True,
            injuries=True,
        ),
    ]

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"x-ratelimit-requests-remaining": "96"},
            json=_envelope(rows),
        )

    with ApiFootballClient(SECRET, transport=httpx.MockTransport(handler)) as client:
        probe = client.target_coverage()

    by_id = {item.league_id: item for item in probe.leagues}
    assert by_id[39].country == "England"
    assert by_id[39].lineups is False
    assert by_id[2].lineups is True
    assert by_id[2].player_statistics is True
    assert set(probe.missing_league_ids) == {3, 61, 78, 140, 848}


def test_daily_quota_reserve_blocks_calls_before_provider_exhaustion() -> None:
    requests = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(
            200,
            headers={"x-ratelimit-requests-remaining": "10"},
            json=_envelope(
                {
                    "subscription": {"plan": "Free", "active": True},
                    "requests": {"current": 90, "limit_day": 100},
                }
            ),
        )

    with ApiFootballClient(
        SECRET,
        daily_request_reserve=10,
        transport=httpx.MockTransport(handler),
    ) as client:
        client.account_probe()
        with pytest.raises(ApiFootballError, match="reserve reached"):
            client.target_coverage()

    assert requests == 1


def test_provider_errors_are_sanitized() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"message": SECRET})

    with ApiFootballClient(SECRET, transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ApiFootballError) as caught:
            client.account_probe()

    assert SECRET not in str(caught.value)


def test_fixture_player_snapshot_requires_server_publication_time_and_normalizes() -> None:
    observed_at = datetime(2026, 7, 25, 10, 0, 5, tzinfo=UTC)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/fixtures/players")
        assert request.url.params["fixture"] == "9001"
        return httpx.Response(
            200,
            headers={
                "date": "Sat, 25 Jul 2026 10:00:00 GMT",
                "x-ratelimit-requests-remaining": "95",
            },
            json=_envelope(
                [
                    {
                        "team": {"id": 51, "name": "Northbridge"},
                        "players": [
                            {
                                "player": {"id": 701, "name": "Research Keeper"},
                                "statistics": [
                                    {
                                        "games": {
                                            "minutes": 90,
                                            "position": "G",
                                            "rating": "7.2",
                                            "captain": False,
                                            "substitute": False,
                                        },
                                        "goals": {"saves": 4},
                                        "passes": {"total": 32, "key": 1},
                                    }
                                ],
                            }
                        ],
                    }
                ]
            ),
        )

    with ApiFootballClient(
        SECRET,
        transport=httpx.MockTransport(handler),
        clock=lambda: observed_at,
    ) as client:
        snapshot = client.fixture_player_snapshot(9001)

    assert snapshot.published_at == datetime(2026, 7, 25, 10, 0, tzinfo=UTC)
    assert snapshot.observed_at == observed_at
    assert len(snapshot.performances) == 1
    performance = snapshot.performances[0]
    assert performance.position == "GK"
    assert performance.starter is True
    assert performance.minutes == 90
    assert performance.metrics == {
        "games.rating": 7.2,
        "goals.saves": 4.0,
        "passes.key": 1.0,
        "passes.total": 32.0,
    }


def test_fixture_player_snapshot_rejects_missing_publication_timestamp() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_envelope([]))

    with ApiFootballClient(SECRET, transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ApiFootballError, match="omitted the publication timestamp"):
            client.fixture_player_snapshot(9001)
