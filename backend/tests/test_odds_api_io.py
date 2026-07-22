from __future__ import annotations

import httpx
import pytest

from app.providers.odds_api_io import OddsApiIoClient, OddsApiIoError

SECRET = "test-secret-that-must-not-escape"


def test_probe_requires_all_three_target_bookmakers() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["apiKey"] == SECRET
        return httpx.Response(
            200,
            json=[
                {"name": "Pamestoixima", "active": True},
                {"name": "Novibet", "active": True},
                {"name": "Bet365", "active": True},
                {"name": "Another Book", "active": True},
            ],
        )

    with OddsApiIoClient(SECRET, transport=httpx.MockTransport(handler)) as client:
        probe = client.probe_target_bookmakers()

    assert probe.complete is True
    assert probe.active_bookmakers == ["Allwyn / Pamestoixima", "Novibet", "bet365"]
    assert probe.missing_bookmakers == []


def test_probe_fails_closed_when_a_target_is_inactive() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {"name": "Pamestoixima", "active": True},
                {"name": "Novibet", "active": False},
                {"name": "Bet365", "active": True},
            ],
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
