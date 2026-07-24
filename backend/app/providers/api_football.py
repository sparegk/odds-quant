from __future__ import annotations

from collections.abc import Mapping

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

API_FOOTBALL_TERMS_URL = "https://www.api-football.com/terms"

TARGET_LEAGUES: Mapping[int, tuple[str, str]] = {
    39: ("Premier League", "England"),
    2: ("UEFA Champions League", "World"),
    3: ("UEFA Europa League", "World"),
    848: ("UEFA Conference League", "World"),
    140: ("La Liga", "Spain"),
    78: ("Bundesliga", "Germany"),
    61: ("Ligue 1", "France"),
}


class ApiFootballError(RuntimeError):
    pass


class ApiFootballAccountProbe(BaseModel):
    provider: str = "API-Football"
    plan: str
    active: bool
    requests_used: int = Field(ge=0)
    requests_limit: int = Field(gt=0)
    requests_remaining: int = Field(ge=0)


class ApiFootballLeagueCoverage(BaseModel):
    league_id: int
    name: str
    country: str
    season: int | None
    current: bool
    fixtures: bool
    lineups: bool
    player_statistics: bool
    players: bool
    injuries: bool


class ApiFootballCoverageProbe(BaseModel):
    provider: str = "API-Football"
    leagues: list[ApiFootballLeagueCoverage]
    missing_league_ids: list[int]


class _Subscription(BaseModel):
    model_config = ConfigDict(extra="ignore")

    plan: str = Field(min_length=1)
    active: bool


class _Requests(BaseModel):
    model_config = ConfigDict(extra="ignore")

    current: int = Field(ge=0)
    limit_day: int = Field(gt=0)


class _StatusResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    subscription: _Subscription
    requests: _Requests


class _FixtureCoverage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    events: bool = False
    lineups: bool = False
    statistics_fixtures: bool = False
    statistics_players: bool = False


class _Coverage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    fixtures: _FixtureCoverage
    players: bool = False
    injuries: bool = False


class _Season(BaseModel):
    model_config = ConfigDict(extra="ignore")

    year: int
    current: bool
    coverage: _Coverage


class _League(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    name: str = Field(min_length=1)


class _Country(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = Field(min_length=1)


class _LeagueResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    league: _League
    country: _Country
    seasons: list[_Season]


class _Envelope(BaseModel):
    model_config = ConfigDict(extra="ignore")

    errors: list[object] | dict[str, object]
    results: int = Field(ge=0)
    response: object


class ApiFootballClient:
    """Credentialed client with a hard daily quota reserve and sanitized failures."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://v3.football.api-sports.io",
        daily_request_reserve: int = 10,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not api_key.strip():
            raise ApiFootballError("ODDSQUANT_API_FOOTBALL_KEY is not configured")
        if daily_request_reserve < 1:
            raise ValueError("daily request reserve must be positive")
        self._api_key = api_key
        self._daily_request_reserve = daily_request_reserve
        self._remaining: int | None = None
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"x-apisports-key": api_key},
            timeout=20,
            transport=transport,
        )

    def __enter__(self) -> ApiFootballClient:
        return self

    def __exit__(self, *_: object) -> None:
        self._client.close()

    @property
    def requests_remaining(self) -> int | None:
        return self._remaining

    def account_probe(self) -> ApiFootballAccountProbe:
        payload = self._get_envelope("/status")
        try:
            response = _StatusResponse.model_validate(payload.response)
        except ValidationError as exc:
            raise ApiFootballError("API-Football returned an invalid account status") from exc
        remaining = max(response.requests.limit_day - response.requests.current, 0)
        if self._remaining is None:
            self._remaining = remaining
        else:
            self._remaining = min(self._remaining, remaining)
        return ApiFootballAccountProbe(
            plan=response.subscription.plan,
            active=response.subscription.active,
            requests_used=response.requests.current,
            requests_limit=response.requests.limit_day,
            requests_remaining=remaining,
        )

    def target_coverage(self) -> ApiFootballCoverageProbe:
        payload = self._get_envelope("/leagues", current="true")
        try:
            rows = [_LeagueResponse.model_validate(item) for item in _response_list(payload)]
        except ValidationError as exc:
            raise ApiFootballError("API-Football returned invalid league coverage") from exc
        by_identity = {(row.league.id, row.league.name, row.country.name): row for row in rows}
        coverage: list[ApiFootballLeagueCoverage] = []
        missing: list[int] = []
        for league_id, (name, country) in TARGET_LEAGUES.items():
            row = by_identity.get((league_id, name, country))
            if row is None:
                missing.append(league_id)
                continue
            current = [season for season in row.seasons if season.current]
            season = max(current, key=lambda value: value.year) if current else None
            coverage.append(
                ApiFootballLeagueCoverage(
                    league_id=league_id,
                    name=name,
                    country=country,
                    season=season.year if season is not None else None,
                    current=season is not None,
                    fixtures=season is not None,
                    lineups=season.coverage.fixtures.lineups if season is not None else False,
                    player_statistics=(
                        season.coverage.fixtures.statistics_players if season is not None else False
                    ),
                    players=season.coverage.players if season is not None else False,
                    injuries=season.coverage.injuries if season is not None else False,
                )
            )
        return ApiFootballCoverageProbe(
            leagues=coverage,
            missing_league_ids=missing,
        )

    def _get_envelope(self, path: str, **params: str) -> _Envelope:
        if self._remaining is not None and self._remaining <= self._daily_request_reserve:
            raise ApiFootballError("API-Football daily request reserve reached")
        try:
            response = self._client.get(path, params=params)
        except httpx.HTTPError as exc:
            raise ApiFootballError("API-Football request failed") from exc
        self._update_remaining(response)
        if response.status_code != 200:
            raise ApiFootballError(f"API-Football request failed with HTTP {response.status_code}")
        try:
            payload = _Envelope.model_validate(response.json())
        except (ValueError, ValidationError) as exc:
            raise ApiFootballError("API-Football returned an invalid response envelope") from exc
        if payload.errors:
            raise ApiFootballError("API-Football rejected the request")
        return payload

    def _update_remaining(self, response: httpx.Response) -> None:
        raw = response.headers.get("x-ratelimit-requests-remaining")
        if raw is None:
            return
        try:
            parsed = int(raw)
        except ValueError as exc:
            raise ApiFootballError("API-Football returned an invalid quota header") from exc
        if parsed < 0:
            raise ApiFootballError("API-Football returned an invalid quota header")
        self._remaining = parsed


def _response_list(payload: _Envelope) -> list[object]:
    if not isinstance(payload.response, list) or payload.results != len(payload.response):
        raise ApiFootballError("API-Football response count does not match its payload")
    return payload.response
