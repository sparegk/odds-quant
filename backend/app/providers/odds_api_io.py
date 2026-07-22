from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.schemas.odds import MarketType, OddsImportRow

ODDS_API_IO_TERMS_URL = "https://odds-api.io/terms"
PREMIER_LEAGUE_SLUG = "england-premier-league"
COLLECTION_HORIZON = timedelta(days=7)
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


class _League(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = Field(min_length=1)
    slug: str = Field(min_length=1)


class _Sport(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = Field(min_length=1)
    slug: str = Field(min_length=1)


class _Event(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    home: str = Field(min_length=1)
    away: str = Field(min_length=1)
    date: datetime
    status: str = Field(min_length=1)
    league: _League
    sport: _Sport

    @field_validator("date")
    @classmethod
    def require_timestamp_offset(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("event date must include a UTC offset")
        return value


class _Market(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    name: str = Field(min_length=1)
    odds: list[dict[str, Any]]
    updated_at: datetime | None = Field(default=None, alias="updatedAt")

    @field_validator("updated_at")
    @classmethod
    def require_timestamp_offset(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("market update timestamp must include a UTC offset")
        return value


class _EventOdds(_Event):
    bookmakers: dict[str, list[_Market]]


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
        payload = self._get_json("/bookmakers/selected")
        if not isinstance(payload, dict):
            raise OddsApiIoError("odds provider returned an invalid selected bookmaker catalog")
        names = payload.get("bookmakers")
        count = payload.get("count")
        if (
            not isinstance(names, list)
            or not all(isinstance(name, str) for name in names)
            or not isinstance(count, int)
            or isinstance(count, bool)
            or count != len(names)
        ):
            raise OddsApiIoError("odds provider returned an invalid selected bookmaker catalog")
        selected_names = {name.casefold() for name in names}
        if len(selected_names) != len(names):
            raise OddsApiIoError("odds provider returned duplicate selected bookmakers")
        active_bookmakers = [
            label
            for label, provider_name in TARGET_BOOKMAKERS.items()
            if provider_name.casefold() in selected_names
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

    def collect_prematch_match_result(
        self,
        *,
        observed_at: datetime,
        horizon: timedelta = COLLECTION_HORIZON,
    ) -> list[OddsImportRow]:
        _require_aware(observed_at, "observation timestamp")
        if horizon <= timedelta(0):
            raise ValueError("collection horizon must be positive")
        probe = self.probe_target_bookmakers()
        if not probe.complete:
            missing = ", ".join(probe.missing_bookmakers)
            raise OddsApiIoError(f"required bookmakers are not selected: {missing}")
        events = self._events(observed_at, observed_at + horizon)
        rows: list[OddsImportRow] = []
        for offset in range(0, len(events), 10):
            batch = events[offset : offset + 10]
            event_ids = ",".join(str(event.id) for event in batch)
            payload = self._get_json(
                "/odds/multi",
                eventIds=event_ids,
                bookmakers=",".join(TARGET_BOOKMAKERS.values()),
            )
            odds_events = _validate_list(payload, _EventOdds, "event odds")
            rows.extend(_normalize_batch(batch, odds_events, observed_at))
        return rows

    def _events(self, start: datetime, end: datetime) -> list[_Event]:
        event_params: dict[str, str | int] = {
            "sport": "football",
            "league": PREMIER_LEAGUE_SLUG,
            "status": "pending",
            "from": _rfc3339(start),
            "to": _rfc3339(end),
            "limit": 500,
        }
        payload = self._get_json("/events", **event_params)
        events = _validate_list(payload, _Event, "event list")
        if len({event.id for event in events}) != len(events):
            raise OddsApiIoError("odds provider returned duplicate event identities")
        for event in events:
            if (
                event.sport.slug.casefold() != "football"
                or event.league.slug.casefold() != PREMIER_LEAGUE_SLUG
                or event.status.casefold() != "pending"
            ):
                raise OddsApiIoError("odds provider returned an event outside the requested scope")
        return [event for event in events if start < event.date <= end]

    def _get_json(
        self,
        path: str,
        **params: str | int | float | bool | None,
    ) -> object:
        request_params: dict[str, str | int | float | bool | None] = {
            "apiKey": self._api_key,
            **params,
        }
        try:
            response = self._client.get(path, params=request_params)
        except httpx.HTTPError:
            raise OddsApiIoError("odds provider request failed") from None
        if response.status_code != 200:
            raise OddsApiIoError(f"odds provider returned HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError:
            raise OddsApiIoError("odds provider returned invalid JSON") from None


class OddsApiIoProvider:
    slug = "odds-api-io"
    name = "Odds-API.io"
    kind = "licensed_api"
    is_demo = False
    terms_url: str | None = ODDS_API_IO_TERMS_URL

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.odds-api.io/v3",
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._transport = transport
        self._clock = clock

    def collect_odds(self) -> Iterable[OddsImportRow]:
        observed_at = self._clock()
        with OddsApiIoClient(
            self._api_key,
            base_url=self._base_url,
            transport=self._transport,
        ) as client:
            return client.collect_prematch_match_result(observed_at=observed_at)


def _validate_list[ModelT: BaseModel](
    payload: object,
    model: type[ModelT],
    label: str,
) -> list[ModelT]:
    if not isinstance(payload, list):
        raise OddsApiIoError(f"odds provider returned an invalid {label}")
    try:
        return [model.model_validate(item) for item in payload]
    except ValidationError:
        raise OddsApiIoError(f"odds provider returned an invalid {label}") from None


def _normalize_batch(
    requested: list[_Event],
    returned: list[_EventOdds],
    observed_at: datetime,
) -> list[OddsImportRow]:
    requested_by_id = {event.id: event for event in requested}
    if len({event.id for event in returned}) != len(returned):
        raise OddsApiIoError("odds provider returned duplicate event odds")
    rows: list[OddsImportRow] = []
    for event in returned:
        expected = requested_by_id.get(event.id)
        if expected is None:
            raise OddsApiIoError("odds provider returned unrequested event odds")
        _require_matching_identity(expected, event)
        if event.status.casefold() != "pending" or event.date <= observed_at:
            continue
        bookmaker_markets = _target_bookmaker_markets(event.bookmakers)
        for display_name, markets in bookmaker_markets.items():
            match_result = [market for market in markets if market.name.casefold() == "ml"]
            if not match_result:
                continue
            if len(match_result) != 1:
                raise OddsApiIoError("odds provider returned an ambiguous match-result market")
            market = match_result[0]
            if market.updated_at is None:
                raise OddsApiIoError("odds provider match-result market lacks an update timestamp")
            if market.updated_at > observed_at or market.updated_at >= event.date:
                raise OddsApiIoError("odds provider returned an invalid pre-match update timestamp")
            if len(market.odds) != 1:
                raise OddsApiIoError("odds provider returned ambiguous match-result prices")
            prices = market.odds[0]
            if set(("home", "draw", "away")) - prices.keys():
                raise OddsApiIoError("odds provider returned incomplete match-result prices")
            season = _football_season(event.date)
            for code, field, name in (
                ("HOME", "home", event.home),
                ("DRAW", "draw", "Draw"),
                ("AWAY", "away", event.away),
            ):
                try:
                    price = Decimal(str(prices[field]))
                    rows.append(
                        OddsImportRow(
                            provider_event_key=str(event.id),
                            competition=event.league.name,
                            country="England",
                            season=season,
                            kickoff_at=event.date,
                            home_team=event.home,
                            away_team=event.away,
                            bookmaker=display_name,
                            market_type=MarketType.MATCH_RESULT,
                            selection_code=code,
                            selection_name=name,
                            decimal_odds=price,
                            observed_at=observed_at,
                            source_updated_at=market.updated_at,
                            period="FULL_TIME",
                            currency="EUR",
                            settlement_rule_key="standard_90_minutes",
                            is_closing=False,
                        )
                    )
                except (ArithmeticError, ValueError, ValidationError):
                    raise OddsApiIoError(
                        "odds provider returned invalid match-result prices"
                    ) from None
    return rows


def _target_bookmaker_markets(
    bookmakers: Mapping[str, list[_Market]],
) -> dict[str, list[_Market]]:
    by_name: dict[str, list[_Market]] = {}
    for provider_name, markets in bookmakers.items():
        key = provider_name.casefold()
        if key in by_name:
            raise OddsApiIoError("odds provider returned duplicate bookmaker identities")
        by_name[key] = markets
    return {
        display_name: by_name[provider_name.casefold()]
        for display_name, provider_name in TARGET_BOOKMAKERS.items()
        if provider_name.casefold() in by_name
    }


def _require_matching_identity(expected: _Event, actual: _EventOdds) -> None:
    if (
        expected.home != actual.home
        or expected.away != actual.away
        or expected.date != actual.date
        or expected.league != actual.league
        or expected.sport != actual.sport
    ):
        raise OddsApiIoError("odds provider returned conflicting event identity")


def _football_season(kickoff: datetime) -> str:
    local_year = kickoff.year
    start_year = local_year if kickoff.month >= 7 else local_year - 1
    return f"{start_year}/{str(start_year + 1)[-2:]}"


def _rfc3339(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _require_aware(value: datetime, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must include a UTC offset")
