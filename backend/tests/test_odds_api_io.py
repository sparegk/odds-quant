from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest

from app.providers.odds_api_io import LEAGUE_COUNTRIES, OddsApiIoClient, OddsApiIoError
from app.schemas.odds import MarketType

SECRET = "test-secret-that-must-not-escape"
OBSERVED_AT = datetime(2026, 7, 22, 10, 0, tzinfo=UTC)


def _event(
    event_id: int = 123,
    *,
    league_name: str = "Premier League",
    league_slug: str = "england-premier-league",
) -> dict[str, object]:
    return {
        "id": event_id,
        "home": "Arsenal",
        "away": "Liverpool",
        "date": "2026-07-25T15:00:00Z",
        "status": "pending",
        "league": {"name": league_name, "slug": league_slug},
        "sport": {"name": "Football", "slug": "football"},
    }


def _event_odds(
    *,
    event: dict[str, object] | None = None,
    prices: dict[str, str] | None = None,
    updated_at: str | None = "2026-07-22T09:59:00Z",
) -> dict[str, object]:
    market: dict[str, object] = {
        "name": "ML",
        "odds": [prices or {"home": "2.10", "draw": "3.40", "away": "3.20"}],
    }
    if updated_at is not None:
        market["updatedAt"] = updated_at
    return {
        **(event or _event()),
        "bookmakers": {
            "Pamestoixima": [market],
            "Novibet": [market],
        },
    }


def test_probe_requires_both_target_bookmakers() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["apiKey"] == SECRET
        return httpx.Response(
            200,
            json={
                "bookmakers": ["Pamestoixima", "Novibet", "Another Book"],
                "count": 3,
            },
        )

    with OddsApiIoClient(SECRET, transport=httpx.MockTransport(handler)) as client:
        probe = client.probe_target_bookmakers()

    assert probe.complete is True
    assert probe.active_bookmakers == ["Allwyn / Pamestoixima", "Novibet"]
    assert probe.missing_bookmakers == []


def test_probe_fails_closed_when_a_target_is_not_selected() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"bookmakers": ["Pamestoixima"], "count": 1},
        )

    with OddsApiIoClient(SECRET, transport=httpx.MockTransport(handler)) as client:
        probe = client.probe_target_bookmakers()

    assert probe.complete is False
    assert probe.missing_bookmakers == ["Novibet"]


def test_provider_error_never_exposes_the_api_key() -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(401, json={"error": "bad key"}))
    with OddsApiIoClient(SECRET, transport=transport) as client:
        with pytest.raises(OddsApiIoError) as caught:
            client.probe_target_bookmakers()

    assert SECRET not in str(caught.value)


def test_collects_complete_timestamped_prematch_match_result_rows() -> None:
    requested_leagues: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["apiKey"] == SECRET
        if request.url.path.endswith("/bookmakers/selected"):
            return httpx.Response(
                200,
                json={"bookmakers": ["Pamestoixima", "Novibet"], "count": 2},
            )
        if request.url.path.endswith("/events"):
            league = request.url.params["league"]
            requested_leagues.append(league)
            assert request.url.params["status"] == "pending"
            return httpx.Response(
                200,
                json=[_event()] if league == "england-premier-league" else [],
            )
        assert request.url.path.endswith("/odds/multi")
        assert request.url.params["eventIds"] == "123"
        assert request.url.params["bookmakers"] == "Pamestoixima,Novibet"
        return httpx.Response(200, json=[_event_odds()])

    with OddsApiIoClient(SECRET, transport=httpx.MockTransport(handler)) as client:
        rows = client.collect_prematch_odds(observed_at=OBSERVED_AT)

    assert len(rows) == 6
    assert {row.bookmaker for row in rows} == {
        "Allwyn / Pamestoixima",
        "Novibet",
    }
    assert {row.selection_code for row in rows} == {"HOME", "DRAW", "AWAY"}
    assert {row.provider_event_key for row in rows} == {"123"}
    assert {row.season for row in rows} == {"2026/27"}
    assert {row.observed_at for row in rows} == {OBSERVED_AT}
    assert {row.source_updated_at for row in rows} == {datetime(2026, 7, 22, 9, 59, tzinfo=UTC)}
    assert all(row.is_closing is False for row in rows)
    assert requested_leagues == list(LEAGUE_COUNTRIES)


def test_collects_uefa_conference_league_corner_totals_from_novibet() -> None:
    league_slug = "international-clubs-uefa-conference-league-qualification"
    event = _event(
        456,
        league_name="UEFA Conference League Qualification",
        league_slug=league_slug,
    )
    corner_market = {
        "name": "Corners Totals",
        "updatedAt": "2026-07-22T09:58:00Z",
        "odds": [{"hdp": "9.5", "over": "1.90", "under": "1.90"}],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/bookmakers/selected"):
            return httpx.Response(
                200,
                json={"bookmakers": ["Pamestoixima", "Novibet"], "count": 2},
            )
        if request.url.path.endswith("/events"):
            return httpx.Response(
                200,
                json=[event] if request.url.params["league"] == league_slug else [],
            )
        return httpx.Response(
            200,
            json=[
                {
                    **event,
                    "bookmakers": {
                        "Pamestoixima": [corner_market],
                        "Novibet": [corner_market],
                    },
                }
            ],
        )

    with OddsApiIoClient(SECRET, transport=httpx.MockTransport(handler)) as client:
        rows = client.collect_prematch_odds(observed_at=OBSERVED_AT)

    assert len(rows) == 2
    assert {row.bookmaker for row in rows} == {"Novibet"}
    assert {row.market_type for row in rows} == {MarketType.TOTAL_CORNERS}
    assert {row.selection_code for row in rows} == {"OVER", "UNDER"}
    assert {row.line for row in rows} == {Decimal("9.5")}
    assert {row.country for row in rows} == {"International"}
    assert {row.settlement_rule_key for row in rows} == {"novibet_total_corners_regulation_time"}


@pytest.mark.parametrize(
    ("odds", "message"),
    [
        ([], "empty corners-total prices"),
        ([{"hdp": "9.5", "over": "1.90"}], "incomplete corners-total prices"),
        (
            [
                {"hdp": "9.5", "over": "1.90", "under": "1.90"},
                {"hdp": "9.5", "over": "1.91", "under": "1.89"},
            ],
            "duplicate corners-total lines",
        ),
    ],
)
def test_rejects_unsafe_corner_total_snapshots(
    odds: list[dict[str, str]],
    message: str,
) -> None:
    league_slug = "international-clubs-uefa-conference-league-qualification"
    event = _event(
        456,
        league_name="Conference League Qualification",
        league_slug=league_slug,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/bookmakers/selected"):
            return httpx.Response(
                200,
                json={"bookmakers": ["Pamestoixima", "Novibet"], "count": 2},
            )
        if request.url.path.endswith("/events"):
            return httpx.Response(
                200,
                json=[event] if request.url.params["league"] == league_slug else [],
            )
        return httpx.Response(
            200,
            json=[
                {
                    **event,
                    "bookmakers": {
                        "Novibet": [
                            {
                                "name": "Corners Totals",
                                "updatedAt": "2026-07-22T09:58:00Z",
                                "odds": odds,
                            }
                        ]
                    },
                }
            ],
        )

    with OddsApiIoClient(SECRET, transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(OddsApiIoError, match=message):
            client.collect_prematch_odds(observed_at=OBSERVED_AT)


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (
            _event_odds(prices={"home": "2.10", "away": "3.20"}),
            "incomplete match-result prices",
        ),
        (
            _event_odds(updated_at=None),
            "lacks an update timestamp",
        ),
        (
            _event_odds(updated_at="2026-07-25T15:00:00Z"),
            "invalid pre-match match-result timestamp",
        ),
    ],
)
def test_rejects_unsafe_match_result_snapshots(
    payload: dict[str, object],
    message: str,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/bookmakers/selected"):
            return httpx.Response(
                200,
                json={"bookmakers": ["Pamestoixima", "Novibet"], "count": 2},
            )
        if request.url.path.endswith("/events"):
            return httpx.Response(
                200,
                json=[_event()] if request.url.params["league"] == "england-premier-league" else [],
            )
        return httpx.Response(200, json=[payload])

    with OddsApiIoClient(SECRET, transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(OddsApiIoError, match=message):
            client.collect_prematch_odds(observed_at=OBSERVED_AT)


def test_collection_stops_before_events_when_a_target_is_not_selected() -> None:
    requested_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)
        return httpx.Response(
            200,
            json={"bookmakers": ["Pamestoixima"], "count": 1},
        )

    with OddsApiIoClient(SECRET, transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(OddsApiIoError, match="Novibet"):
            client.collect_prematch_odds(observed_at=OBSERVED_AT)

    assert requested_paths == ["/v3/bookmakers/selected"]
