from __future__ import annotations

from collections.abc import Mapping

import httpx
from pydantic import BaseModel

ODDS_API_IO_TERMS_URL = "https://odds-api.io/terms"
TARGET_BOOKMAKERS: Mapping[str, str] = {
    "Allwyn / Pamestoixima": "Pamestoixima",
    "Novibet": "Novibet",
    "bet365": "Bet365",
}


class OddsApiIoError(RuntimeError):
    pass


class TargetBookmakerProbe(BaseModel):
    provider: str
    required_bookmakers: list[str]
    active_bookmakers: list[str]
    missing_bookmakers: list[str]
    complete: bool


class OddsApiIoClient:
    """Small credentialed client whose errors never include the API key or request URL."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.odds-api.io/v3",
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not api_key.strip():
            raise OddsApiIoError("ODDSQUANT_ODDS_API_IO_KEY is not configured")
        self._api_key = api_key
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=20,
            transport=transport,
        )

    def __enter__(self) -> OddsApiIoClient:
        return self

    def __exit__(self, *_: object) -> None:
        self._client.close()

    def probe_target_bookmakers(self) -> TargetBookmakerProbe:
        try:
            response = self._client.get("/bookmakers", params={"apiKey": self._api_key})
        except httpx.HTTPError:
            raise OddsApiIoError("odds provider request failed") from None
        if response.status_code != 200:
            raise OddsApiIoError(f"odds provider returned HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError:
            raise OddsApiIoError("odds provider returned invalid JSON") from None
        if not isinstance(payload, list):
            raise OddsApiIoError("odds provider returned an invalid bookmaker catalog")

        active_names: set[str] = set()
        for item in payload:
            if not isinstance(item, dict):
                raise OddsApiIoError("odds provider returned an invalid bookmaker catalog")
            name = item.get("name")
            active = item.get("active")
            if not isinstance(name, str) or not isinstance(active, bool):
                raise OddsApiIoError("odds provider returned an invalid bookmaker catalog")
            if active:
                active_names.add(name.casefold())
        active_bookmakers = [
            label
            for label, provider_name in TARGET_BOOKMAKERS.items()
            if provider_name.casefold() in active_names
        ]
        missing_bookmakers = [
            label for label in TARGET_BOOKMAKERS if label not in active_bookmakers
        ]
        return TargetBookmakerProbe(
            provider="Odds-API.io",
            required_bookmakers=list(TARGET_BOOKMAKERS),
            active_bookmakers=active_bookmakers,
            missing_bookmakers=missing_bookmakers,
            complete=not missing_bookmakers,
        )
