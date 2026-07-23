from __future__ import annotations

import random
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.schemas.fixtures import FixtureImportRow
from app.schemas.odds import MarketType, OddsImportRow

ODDS_API_IO_TERMS_URL = "https://odds-api.io/terms"
COLLECTION_HORIZON = timedelta(days=35)
MAX_EVENTS_PER_LEAGUE = 30
MAX_RATE_LIMIT_RETRIES = 3
MAX_RETRY_DELAY_SECONDS = 30.0
LEAGUE_COUNTRIES: Mapping[str, str] = {
    "england-premier-league": "England",
    "international-clubs-uefa-champions-league": "International",
    "international-clubs-uefa-champions-league-qualification": "International",
    "international-clubs-uefa-conference-league": "International",
    "international-clubs-uefa-conference-league-qualification": "International",
}
LEAGUE_COMPETITION_NAMES: Mapping[str, str] = {
    "england-premier-league": "Premier League",
    "international-clubs-uefa-champions-league": "UEFA Champions League",
    "international-clubs-uefa-champions-league-qualification": (
        "UEFA Champions League Qualification"
    ),
    "international-clubs-uefa-conference-league": "UEFA Conference League",
    "international-clubs-uefa-conference-league-qualification": (
        "UEFA Conference League Qualification"
    ),
}
TARGET_BOOKMAKERS: Mapping[str, str] = {
    "Allwyn / Pamestoixima": "Pamestoixima",
    "Novibet": "Novibet",
}


class OddsApiIoError(RuntimeError):
    pass


class TargetBookmakerProbe(BaseModel):
    provider: str
    required_bookmakers: list[str]
    active_bookmakers: list[str]
    missing_bookmakers: list[str]
    complete: bool


class MarketDiscoverySummary(BaseModel):
    bookmaker: str
    market_name: str
    event_markets: int
    timestamped_event_markets: int
    outcome_entries: int
    labeled_outcome_entries: int
    field_names: list[str]
    ingestion_status: str
    blockers: list[str]


class BetBuilderMarketProbe(BaseModel):
    provider: str
    observed_at: datetime
    competition_slugs: list[str]
    events_checked: int
    markets: list[MarketDiscoverySummary]
    player_props_ingestion_enabled: bool = False
    raw_values_included: bool = False


@dataclass
class _DiscoveryAccumulator:
    event_markets: int = 0
    timestamped_event_markets: int = 0
    outcome_entries: int = 0
    labeled_outcome_entries: int = 0
    field_names: set[str] = dataclass_field(default_factory=set)


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
        sleep: Callable[[float], None] = time.sleep,
        jitter: Callable[[], float] = random.random,
    ) -> None:
        if not api_key.strip():
            raise OddsApiIoError("ODDSQUANT_ODDS_API_IO_KEY is not configured")
        self._api_key = api_key
        self._sleep = sleep
        self._jitter = jitter
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

    def collect_prematch_odds(
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
        events = self._pending_events(observed_at, horizon)
        return self._collect_event_odds(events, observed_at)

    def collect_prematch_batch(
        self,
        *,
        observed_at: datetime,
        horizon: timedelta = COLLECTION_HORIZON,
    ) -> tuple[list[FixtureImportRow], list[OddsImportRow]]:
        _require_aware(observed_at, "observation timestamp")
        if horizon <= timedelta(0):
            raise ValueError("collection horizon must be positive")
        probe = self.probe_target_bookmakers()
        if not probe.complete:
            missing = ", ".join(probe.missing_bookmakers)
            raise OddsApiIoError(f"required bookmakers are not selected: {missing}")
        events = self._pending_events(observed_at, horizon)
        fixtures = [_fixture_row(event, observed_at) for event in events]
        return fixtures, self._collect_event_odds(events, observed_at)

    def _collect_event_odds(
        self,
        events: list[_Event],
        observed_at: datetime,
    ) -> list[OddsImportRow]:
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

    def collect_fixtures(
        self,
        *,
        observed_at: datetime,
        horizon: timedelta = COLLECTION_HORIZON,
    ) -> list[FixtureImportRow]:
        _require_aware(observed_at, "observation timestamp")
        if horizon <= timedelta(0):
            raise ValueError("collection horizon must be positive")
        return [
            _fixture_row(event, observed_at) for event in self._pending_events(observed_at, horizon)
        ]

    def probe_bet_builder_markets(
        self,
        *,
        observed_at: datetime,
        horizon: timedelta = COLLECTION_HORIZON,
    ) -> BetBuilderMarketProbe:
        _require_aware(observed_at, "observation timestamp")
        if horizon <= timedelta(0):
            raise ValueError("collection horizon must be positive")
        probe = self.probe_target_bookmakers()
        if not probe.complete:
            missing = ", ".join(probe.missing_bookmakers)
            raise OddsApiIoError(f"required bookmakers are not selected: {missing}")
        events = self._pending_events(observed_at, horizon)
        discovered: dict[tuple[str, str], _DiscoveryAccumulator] = {}
        for offset in range(0, len(events), 10):
            batch = events[offset : offset + 10]
            payload = self._get_json(
                "/odds/multi",
                eventIds=",".join(str(event.id) for event in batch),
                bookmakers=",".join(TARGET_BOOKMAKERS.values()),
            )
            returned = _validate_list(payload, _EventOdds, "event odds")
            _validate_returned_events(batch, returned)
            for event in returned:
                if event.status.casefold() != "pending" or event.date <= observed_at:
                    continue
                for bookmaker, markets in _target_bookmaker_markets(event.bookmakers).items():
                    for market in markets:
                        if not _is_bet_builder_market(market.name):
                            continue
                        key = (bookmaker, market.name)
                        aggregate = discovered.setdefault(key, _DiscoveryAccumulator())
                        aggregate.event_markets += 1
                        if (
                            market.updated_at is not None
                            and market.updated_at <= observed_at
                            and market.updated_at < event.date
                        ):
                            aggregate.timestamped_event_markets += 1
                        aggregate.outcome_entries += len(market.odds)
                        aggregate.labeled_outcome_entries += sum(
                            1 for outcome in market.odds if "label" in outcome
                        )
                        for outcome in market.odds:
                            aggregate.field_names.update(outcome)
        summaries = [
            _market_discovery_summary(bookmaker, market_name, aggregate)
            for (bookmaker, market_name), aggregate in sorted(discovered.items())
        ]
        return BetBuilderMarketProbe(
            provider="Odds-API.io",
            observed_at=observed_at,
            competition_slugs=list(LEAGUE_COUNTRIES),
            events_checked=len(events),
            markets=summaries,
        )

    def _pending_events(self, observed_at: datetime, horizon: timedelta) -> list[_Event]:
        events: list[_Event] = []
        for league_slug in LEAGUE_COUNTRIES:
            events.extend(self._events(observed_at, observed_at + horizon, league_slug))
        if len({event.id for event in events}) != len(events):
            raise OddsApiIoError("odds provider returned duplicate cross-competition events")
        events.sort(key=lambda event: (event.date, event.id))
        return events

    def _events(self, start: datetime, end: datetime, league_slug: str) -> list[_Event]:
        event_params: dict[str, str | int] = {
            "sport": "football",
            "league": league_slug,
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
                or event.league.slug.casefold() != league_slug
                or event.status.casefold() != "pending"
            ):
                raise OddsApiIoError("odds provider returned an event outside the requested scope")
        eligible = [event for event in events if start < event.date <= end]
        eligible.sort(key=lambda event: (event.date, event.id))
        return eligible[:MAX_EVENTS_PER_LEAGUE]

    def _get_json(
        self,
        path: str,
        **params: str | int | float | bool | None,
    ) -> object:
        request_params: dict[str, str | int | float | bool | None] = {
            "apiKey": self._api_key,
            **params,
        }
        response: httpx.Response | None = None
        for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
            try:
                response = self._client.get(path, params=request_params)
            except httpx.HTTPError:
                raise OddsApiIoError("odds provider request failed") from None
            if response.status_code != 429 or attempt == MAX_RATE_LIMIT_RETRIES:
                break
            self._sleep(_rate_limit_delay(response, attempt, self._jitter()))
        if response is None:
            raise OddsApiIoError("odds provider request failed")
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
        self._cached_batch: tuple[list[FixtureImportRow], list[OddsImportRow]] | None = None

    def collect_fixtures(self) -> Iterable[FixtureImportRow]:
        self._cached_batch = self._collect_batch()
        return self._cached_batch[0]

    def collect_odds(self) -> Iterable[OddsImportRow]:
        if self._cached_batch is not None:
            _, rows = self._cached_batch
            self._cached_batch = None
            return rows
        _, rows = self._collect_batch()
        return rows

    def _collect_batch(self) -> tuple[list[FixtureImportRow], list[OddsImportRow]]:
        observed_at = self._clock()
        with OddsApiIoClient(
            self._api_key,
            base_url=self._base_url,
            transport=self._transport,
        ) as client:
            return client.collect_prematch_batch(observed_at=observed_at)


def _rate_limit_delay(response: httpx.Response, attempt: int, jitter: float) -> float:
    retry_after = response.headers.get("Retry-After", "")
    try:
        provider_delay = max(0.0, float(retry_after))
    except ValueError:
        provider_delay = 0.0
    exponential_delay = float(2**attempt)
    return min(MAX_RETRY_DELAY_SECONDS, max(exponential_delay, provider_delay) + max(0.0, jitter))


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
    _validate_returned_events(requested, returned)
    rows: list[OddsImportRow] = []
    for event in returned:
        if event.status.casefold() != "pending" or event.date <= observed_at:
            continue
        bookmaker_markets = _target_bookmaker_markets(event.bookmakers)
        for display_name, markets in bookmaker_markets.items():
            rows.extend(_normalize_match_result(event, display_name, markets, observed_at))
            if display_name == "Novibet":
                rows.extend(_normalize_corner_totals(event, display_name, markets, observed_at))
    return rows


def _validate_returned_events(requested: list[_Event], returned: list[_EventOdds]) -> None:
    requested_by_id = {event.id: event for event in requested}
    if len({event.id for event in returned}) != len(returned):
        raise OddsApiIoError("odds provider returned duplicate event odds")
    for event in returned:
        expected = requested_by_id.get(event.id)
        if expected is None:
            raise OddsApiIoError("odds provider returned unrequested event odds")
        _require_matching_identity(expected, event)


def _is_bet_builder_market(name: str) -> bool:
    normalized = name.casefold()
    return any(term in normalized for term in ("corner", "player", "shot"))


def _market_discovery_summary(
    bookmaker: str,
    market_name: str,
    aggregate: _DiscoveryAccumulator,
) -> MarketDiscoverySummary:
    normalized = market_name.casefold()
    implemented = bookmaker == "Novibet" and normalized == "corners totals"
    if implemented:
        blockers: list[str] = []
        ingestion_status = "implemented"
    elif "player" in normalized or aggregate.labeled_outcome_entries:
        blockers = [
            "stable player identity is not validated",
            "player-level target and settlement are not independently validated",
            "outcome completeness is not validated",
        ]
        ingestion_status = "discovery_only"
    else:
        blockers = ["market target and settlement are not independently validated"]
        ingestion_status = "discovery_only"
    return MarketDiscoverySummary(
        bookmaker=bookmaker,
        market_name=market_name,
        event_markets=aggregate.event_markets,
        timestamped_event_markets=aggregate.timestamped_event_markets,
        outcome_entries=aggregate.outcome_entries,
        labeled_outcome_entries=aggregate.labeled_outcome_entries,
        field_names=sorted(aggregate.field_names),
        ingestion_status=ingestion_status,
        blockers=blockers,
    )


def _normalize_match_result(
    event: _EventOdds,
    bookmaker: str,
    markets: list[_Market],
    observed_at: datetime,
) -> list[OddsImportRow]:
    match_result = [market for market in markets if market.name.casefold() == "ml"]
    if not match_result:
        return []
    if len(match_result) != 1:
        raise OddsApiIoError("odds provider returned an ambiguous match-result market")
    market = match_result[0]
    _require_prematch_market_timestamp(market, event, observed_at, "match-result")
    if len(market.odds) != 1:
        raise OddsApiIoError("odds provider returned ambiguous match-result prices")
    prices = market.odds[0]
    if set(("home", "draw", "away")) - prices.keys():
        raise OddsApiIoError("odds provider returned incomplete match-result prices")
    rows: list[OddsImportRow] = []
    for code, field, name in (
        ("HOME", "home", event.home),
        ("DRAW", "draw", "Draw"),
        ("AWAY", "away", event.away),
    ):
        rows.append(
            _odds_row(
                event,
                bookmaker,
                MarketType.MATCH_RESULT,
                code,
                name,
                prices[field],
                observed_at,
                market.updated_at,
                settlement_rule_key="standard_90_minutes",
            )
        )
    return rows


def _normalize_corner_totals(
    event: _EventOdds,
    bookmaker: str,
    markets: list[_Market],
    observed_at: datetime,
) -> list[OddsImportRow]:
    corner_markets = [market for market in markets if market.name.casefold() == "corners totals"]
    if not corner_markets:
        return []
    if len(corner_markets) != 1:
        raise OddsApiIoError("odds provider returned an ambiguous corners-total market")
    market = corner_markets[0]
    _require_prematch_market_timestamp(market, event, observed_at, "corners-total")
    if not market.odds:
        raise OddsApiIoError("odds provider returned empty corners-total prices")
    rows: list[OddsImportRow] = []
    seen_lines: set[Decimal] = set()
    for prices in market.odds:
        if set(("hdp", "over", "under")) - prices.keys():
            raise OddsApiIoError("odds provider returned incomplete corners-total prices")
        try:
            line = Decimal(str(prices["hdp"]))
        except (ArithmeticError, ValueError):
            raise OddsApiIoError("odds provider returned invalid corners-total prices") from None
        if not line.is_finite() or line <= 0:
            raise OddsApiIoError("odds provider returned invalid corners-total prices")
        if line in seen_lines:
            raise OddsApiIoError("odds provider returned duplicate corners-total lines")
        seen_lines.add(line)
        for code, field in (("OVER", "over"), ("UNDER", "under")):
            rows.append(
                _odds_row(
                    event,
                    bookmaker,
                    MarketType.TOTAL_CORNERS,
                    code,
                    f"{code.title()} {line.normalize()} corners",
                    prices[field],
                    observed_at,
                    market.updated_at,
                    line=line,
                    settlement_rule_key="novibet_total_corners_regulation_time",
                )
            )
    return rows


def _fixture_row(event: _Event, observed_at: datetime) -> FixtureImportRow:
    competition, country = _competition_identity(event.league.slug)
    try:
        return FixtureImportRow(
            provider_event_key=str(event.id),
            competition=competition,
            country=country,
            season=_football_season(event.date),
            kickoff_at=event.date,
            home_team=event.home,
            away_team=event.away,
            status="scheduled",
            observed_at=observed_at,
        )
    except ValidationError:
        raise OddsApiIoError("odds provider returned an invalid fixture") from None


def _odds_row(
    event: _EventOdds,
    bookmaker: str,
    market_type: MarketType,
    selection_code: str,
    selection_name: str,
    price: object,
    observed_at: datetime,
    source_updated_at: datetime | None,
    *,
    line: Decimal | None = None,
    settlement_rule_key: str,
) -> OddsImportRow:
    competition, country = _competition_identity(event.league.slug)
    try:
        return OddsImportRow(
            provider_event_key=str(event.id),
            competition=competition,
            country=country,
            season=_football_season(event.date),
            kickoff_at=event.date,
            home_team=event.home,
            away_team=event.away,
            bookmaker=bookmaker,
            market_type=market_type,
            line=line,
            selection_code=selection_code,
            selection_name=selection_name,
            decimal_odds=Decimal(str(price)),
            observed_at=observed_at,
            source_updated_at=source_updated_at,
            period="FULL_TIME",
            currency="EUR",
            settlement_rule_key=settlement_rule_key,
            is_closing=False,
        )
    except (ArithmeticError, ValueError, ValidationError):
        raise OddsApiIoError(f"odds provider returned invalid {market_type} prices") from None


def _competition_identity(league_slug: str) -> tuple[str, str]:
    normalized = league_slug.casefold()
    competition = LEAGUE_COMPETITION_NAMES.get(normalized)
    country = LEAGUE_COUNTRIES.get(normalized)
    if competition is None or country is None:
        raise OddsApiIoError("odds provider returned an unsupported competition")
    return competition, country


def _require_prematch_market_timestamp(
    market: _Market,
    event: _EventOdds,
    observed_at: datetime,
    label: str,
) -> None:
    if market.updated_at is None:
        raise OddsApiIoError(f"odds provider {label} market lacks an update timestamp")
    if market.updated_at > observed_at or market.updated_at >= event.date:
        raise OddsApiIoError(f"odds provider returned an invalid pre-match {label} timestamp")


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
