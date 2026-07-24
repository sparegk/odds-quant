from __future__ import annotations

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
