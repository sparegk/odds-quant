from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from app.providers.odds_api_io import OddsApiIoClient, OddsApiIoError

SECRET = "test-secret-that-must-not-escape"
OBSERVED_AT = datetime(2026, 7, 22, 10, 0, tzinfo=UTC)


def _event(event_id: int = 123) -> dict[str, object]:
    return {
        "id": event_id,
        "home": "Arsenal",
        "away": "Liverpool",
        "date": "2026-07-25T15:00:00Z",
        "status": "pending",
        "league": {"name": "Premier League", "slug": "england-premier-league"},
        "sport": {"name": "Football", "slug": "football"},
    }


def _event_odds(
    *,
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
        **_event(),
        "bookmakers": {
            "Pamestoixima": [market],
            "Novibet": [market],
            "Bet365": [market],
        },
    }


def test_probe_requires_all_three_target_bookmakers() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["apiKey"] == SECRET
        return httpx.Response(
            200,
            json={
                "bookmakers": ["Pamestoixima", "Novibet", "Bet365", "Another Book"],
                "count": 4,
            },
        )

    with OddsApiIoClient(SECRET, transport=httpx.MockTransport(handler)) as client:
        probe = client.probe_target_bookmakers()

    assert probe.complete is True
    assert probe.active_bookmakers == ["Allwyn / Pamestoixima", "Novibet", "bet365"]
    assert probe.missing_bookmakers == []


def test_probe_fails_closed_when_a_target_is_not_selected() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"bookmakers": ["Pamestoixima", "Bet365"], "count": 2},
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
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["apiKey"] == SECRET
        if request.url.path.endswith("/bookmakers/selected"):
            return httpx.Response(
                200,
                json={"bookmakers": ["Pamestoixima", "Novibet", "Bet365"], "count": 3},
            )
        if request.url.path.endswith("/events"):
            assert request.url.params["league"] == "england-premier-league"
            assert request.url.params["status"] == "pending"
            return httpx.Response(200, json=[_event()])
        assert request.url.path.endswith("/odds/multi")
        assert request.url.params["eventIds"] == "123"
        assert request.url.params["bookmakers"] == "Pamestoixima,Novibet,Bet365"
        return httpx.Response(200, json=[_event_odds()])

    with OddsApiIoClient(SECRET, transport=httpx.MockTransport(handler)) as client:
        rows = client.collect_prematch_match_result(observed_at=OBSERVED_AT)

    assert len(rows) == 9
    assert {row.bookmaker for row in rows} == {
        "Allwyn / Pamestoixima",
        "Novibet",
        "bet365",
    }
    assert {row.selection_code for row in rows} == {"HOME", "DRAW", "AWAY"}
    assert {row.provider_event_key for row in rows} == {"123"}
    assert {row.season for row in rows} == {"2026/27"}
    assert {row.observed_at for row in rows} == {OBSERVED_AT}
    assert {row.source_updated_at for row in rows} == {datetime(2026, 7, 22, 9, 59, tzinfo=UTC)}
    assert all(row.is_closing is False for row in rows)


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
            "invalid pre-match update timestamp",
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
                json={"bookmakers": ["Pamestoixima", "Novibet", "Bet365"], "count": 3},
            )
        if request.url.path.endswith("/events"):
            return httpx.Response(200, json=[_event()])
        return httpx.Response(200, json=[payload])

    with OddsApiIoClient(SECRET, transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(OddsApiIoError, match=message):
            client.collect_prematch_match_result(observed_at=OBSERVED_AT)


def test_collection_stops_before_events_when_a_target_is_not_selected() -> None:
    requested_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)
        return httpx.Response(
            200,
            json={"bookmakers": ["Pamestoixima", "Novibet"], "count": 2},
        )

    with OddsApiIoClient(SECRET, transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(OddsApiIoError, match="bet365"):
            client.collect_prematch_match_result(observed_at=OBSERVED_AT)

    assert requested_paths == ["/v3/bookmakers/selected"]
