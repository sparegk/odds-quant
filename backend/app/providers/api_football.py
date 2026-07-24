from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Literal

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


class ApiFootballPlayerPerformance(BaseModel):
    player_id: int
    player_name: str
    team_id: int
    team_name: str
    position: Literal["GK", "DF", "MF", "FW"]
    starter: bool
    minutes: int = Field(ge=0, le=130)
    metrics: dict[str, float]


class ApiFootballPlayerSnapshot(BaseModel):
    fixture_id: int
    published_at: datetime
    observed_at: datetime
    performances: list[ApiFootballPlayerPerformance]


class ApiFootballLineupMember(BaseModel):
    player_id: int
    player_name: str
    position: Literal["GK", "DF", "MF", "FW"]
    starter: bool


class ApiFootballTeamLineup(BaseModel):
    team_id: int
    team_name: str
    formation: str | None
    coach_id: int | None
    coach_name: str | None
    members: list[ApiFootballLineupMember]


class ApiFootballLineupSnapshot(BaseModel):
    fixture_id: int
    published_at: datetime
    observed_at: datetime
    teams: list[ApiFootballTeamLineup]


class ApiFootballInjury(BaseModel):
    player_id: int
    player_name: str
    team_id: int
    team_name: str
    provider_status: str
    reason: str | None


class ApiFootballInjurySnapshot(BaseModel):
    fixture_id: int
    published_at: datetime
    observed_at: datetime
    injuries: list[ApiFootballInjury]


class ApiFootballFixture(BaseModel):
    fixture_id: int
    kickoff_at: datetime
    status: str
    league_id: int
    league_name: str
    season: int
    home_team_id: int
    home_team_name: str
    away_team_id: int
    away_team_name: str


class ApiFootballFixtureSnapshot(BaseModel):
    on_date: date
    published_at: datetime
    observed_at: datetime
    fixtures: list[ApiFootballFixture]


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


class _PlayerRef(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    name: str = Field(min_length=1)


class _TeamRef(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    name: str = Field(min_length=1)


class _Games(BaseModel):
    model_config = ConfigDict(extra="ignore")

    minutes: int | None = Field(default=None, ge=0, le=130)
    position: str | None = None
    rating: float | None = None
    captain: bool = False
    substitute: bool | None = None


class _PlayerStatistics(BaseModel):
    model_config = ConfigDict(extra="allow")

    games: _Games


class _PlayerPerformance(BaseModel):
    model_config = ConfigDict(extra="ignore")

    player: _PlayerRef
    statistics: list[_PlayerStatistics]


class _TeamPlayers(BaseModel):
    model_config = ConfigDict(extra="ignore")

    team: _TeamRef
    players: list[_PlayerPerformance]


class _LineupPlayer(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    name: str = Field(min_length=1)
    pos: str


class _LineupMember(BaseModel):
    model_config = ConfigDict(extra="ignore")

    player: _LineupPlayer


class _CoachRef(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int | None = None
    name: str | None = None


class _TeamLineup(BaseModel):
    model_config = ConfigDict(extra="ignore")

    team: _TeamRef
    formation: str | None = None
    coach: _CoachRef | None = None
    startXI: list[_LineupMember]
    substitutes: list[_LineupMember] = Field(default_factory=list)


class _InjuryPlayer(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    name: str = Field(min_length=1)
    type: str = Field(min_length=1)
    reason: str | None = None


class _InjuryFixture(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int


class _InjuryResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    player: _InjuryPlayer
    team: _TeamRef
    fixture: _InjuryFixture


class _FixtureStatus(BaseModel):
    model_config = ConfigDict(extra="ignore")

    short: str = Field(min_length=1)


class _CatalogFixture(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    date: datetime
    status: _FixtureStatus


class _CatalogLeague(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    name: str = Field(min_length=1)
    season: int


class _CatalogTeams(BaseModel):
    model_config = ConfigDict(extra="ignore")

    home: _TeamRef
    away: _TeamRef


class _CatalogResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    fixture: _CatalogFixture
    league: _CatalogLeague
    teams: _CatalogTeams


class ApiFootballClient:
    """Credentialed client with a hard daily quota reserve and sanitized failures."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://v3.football.api-sports.io",
        daily_request_reserve: int = 10,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if not api_key.strip():
            raise ApiFootballError("ODDSQUANT_API_FOOTBALL_KEY is not configured")
        if daily_request_reserve < 1:
            raise ValueError("daily request reserve must be positive")
        self._api_key = api_key
        self._daily_request_reserve = daily_request_reserve
        self._remaining: int | None = None
        self._clock = clock
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

    def fixture_player_snapshot(self, fixture_id: int) -> ApiFootballPlayerSnapshot:
        if fixture_id <= 0:
            raise ValueError("fixture id must be positive")
        payload, published_at = self._get_snapshot("/fixtures/players", fixture=str(fixture_id))
        if published_at is None:
            raise ApiFootballError(
                "API-Football omitted the publication timestamp for player statistics"
            )
        observed_at = _observed_at(self._clock(), published_at)
        try:
            teams = [_TeamPlayers.model_validate(item) for item in _response_list(payload)]
        except ValidationError as exc:
            raise ApiFootballError(
                "API-Football returned invalid fixture player statistics"
            ) from exc
        performances: list[ApiFootballPlayerPerformance] = []
        seen: set[int] = set()
        for team in teams:
            for player in team.players:
                if player.player.id in seen:
                    raise ApiFootballError("API-Football returned a duplicate fixture player")
                if not player.statistics:
                    continue
                statistics = player.statistics[0]
                games = statistics.games
                if games.position is None or games.substitute is None:
                    raise ApiFootballError(
                        "API-Football omitted player position or starter evidence"
                    )
                seen.add(player.player.id)
                performances.append(
                    ApiFootballPlayerPerformance(
                        player_id=player.player.id,
                        player_name=player.player.name,
                        team_id=team.team.id,
                        team_name=team.team.name,
                        position=_position(games.position),
                        starter=not games.substitute,
                        minutes=games.minutes or 0,
                        metrics=_numeric_metrics(statistics),
                    )
                )
        return ApiFootballPlayerSnapshot(
            fixture_id=fixture_id,
            published_at=published_at,
            observed_at=observed_at,
            performances=performances,
        )

    def fixture_catalog(self, on_date: date) -> ApiFootballFixtureSnapshot:
        payload, published_at = self._get_snapshot(
            "/fixtures", date=on_date.isoformat(), timezone="UTC"
        )
        if published_at is None:
            raise ApiFootballError(
                "API-Football omitted the publication timestamp for fixture catalog"
            )
        observed_at = _observed_at(self._clock(), published_at)
        try:
            rows = [_CatalogResponse.model_validate(item) for item in _response_list(payload)]
        except ValidationError as exc:
            raise ApiFootballError("API-Football returned invalid fixture catalog") from exc
        fixtures: list[ApiFootballFixture] = []
        seen: set[int] = set()
        for row in rows:
            if row.fixture.id in seen:
                raise ApiFootballError("API-Football returned a duplicate catalog fixture")
            seen.add(row.fixture.id)
            fixtures.append(
                ApiFootballFixture(
                    fixture_id=row.fixture.id,
                    kickoff_at=_aware_utc(row.fixture.date, "fixture kickoff"),
                    status=row.fixture.status.short,
                    league_id=row.league.id,
                    league_name=row.league.name,
                    season=row.league.season,
                    home_team_id=row.teams.home.id,
                    home_team_name=row.teams.home.name,
                    away_team_id=row.teams.away.id,
                    away_team_name=row.teams.away.name,
                )
            )
        return ApiFootballFixtureSnapshot(
            on_date=on_date,
            published_at=published_at,
            observed_at=observed_at,
            fixtures=fixtures,
        )

    def fixture_lineup_snapshot(self, fixture_id: int) -> ApiFootballLineupSnapshot:
        payload, published_at, observed_at = self._fixture_snapshot(
            fixture_id, "/fixtures/lineups", "lineups"
        )
        try:
            rows = [_TeamLineup.model_validate(item) for item in _response_list(payload)]
        except ValidationError as exc:
            raise ApiFootballError("API-Football returned invalid fixture lineups") from exc
        teams: list[ApiFootballTeamLineup] = []
        seen_players: set[int] = set()
        seen_teams: set[int] = set()
        for row in rows:
            if row.team.id in seen_teams:
                raise ApiFootballError("API-Football returned a duplicate lineup team")
            if len(row.startXI) != 11:
                raise ApiFootballError("API-Football confirmed lineup must contain 11 starters")
            seen_teams.add(row.team.id)
            members: list[ApiFootballLineupMember] = []
            for value, starter in (
                *((member, True) for member in row.startXI),
                *((member, False) for member in row.substitutes),
            ):
                if value.player.id in seen_players:
                    raise ApiFootballError("API-Football returned a duplicate lineup player")
                seen_players.add(value.player.id)
                members.append(
                    ApiFootballLineupMember(
                        player_id=value.player.id,
                        player_name=value.player.name,
                        position=_position(value.player.pos),
                        starter=starter,
                    )
                )
            coach_id = row.coach.id if row.coach is not None else None
            coach_name = row.coach.name if row.coach is not None else None
            if (coach_id is None) != (coach_name is None):
                raise ApiFootballError("API-Football returned an incomplete coach identity")
            teams.append(
                ApiFootballTeamLineup(
                    team_id=row.team.id,
                    team_name=row.team.name,
                    formation=row.formation,
                    coach_id=coach_id,
                    coach_name=coach_name,
                    members=members,
                )
            )
        return ApiFootballLineupSnapshot(
            fixture_id=fixture_id,
            published_at=published_at,
            observed_at=observed_at,
            teams=teams,
        )

    def fixture_injury_snapshot(self, fixture_id: int) -> ApiFootballInjurySnapshot:
        payload, published_at, observed_at = self._fixture_snapshot(
            fixture_id, "/injuries", "injuries"
        )
        try:
            rows = [_InjuryResponse.model_validate(item) for item in _response_list(payload)]
        except ValidationError as exc:
            raise ApiFootballError("API-Football returned invalid fixture injuries") from exc
        injuries: list[ApiFootballInjury] = []
        seen: set[tuple[int, int]] = set()
        for row in rows:
            if row.fixture.id != fixture_id:
                raise ApiFootballError("API-Football returned injuries for a different fixture")
            identity = (row.player.id, row.team.id)
            if identity in seen:
                raise ApiFootballError("API-Football returned a duplicate fixture injury")
            seen.add(identity)
            injuries.append(
                ApiFootballInjury(
                    player_id=row.player.id,
                    player_name=row.player.name,
                    team_id=row.team.id,
                    team_name=row.team.name,
                    provider_status=row.player.type,
                    reason=row.player.reason,
                )
            )
        return ApiFootballInjurySnapshot(
            fixture_id=fixture_id,
            published_at=published_at,
            observed_at=observed_at,
            injuries=injuries,
        )

    def _fixture_snapshot(
        self, fixture_id: int, path: str, label: str
    ) -> tuple[_Envelope, datetime, datetime]:
        if fixture_id <= 0:
            raise ValueError("fixture id must be positive")
        payload, published_at = self._get_snapshot(path, fixture=str(fixture_id))
        if published_at is None:
            raise ApiFootballError(f"API-Football omitted the publication timestamp for {label}")
        observed_at = _observed_at(self._clock(), published_at)
        return payload, published_at, observed_at

    def _get_envelope(self, path: str, **params: str) -> _Envelope:
        return self._get_snapshot(path, **params)[0]

    def _get_snapshot(self, path: str, **params: str) -> tuple[_Envelope, datetime | None]:
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
        return payload, _published_at(response)

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


def _published_at(response: httpx.Response) -> datetime | None:
    raw = response.headers.get("date")
    if raw is None:
        return None
    try:
        parsed = parsedate_to_datetime(raw)
    except (TypeError, ValueError) as exc:
        raise ApiFootballError("API-Football returned an invalid publication timestamp") from exc
    return _aware_utc(parsed, "publication timestamp")


def _aware_utc(value: datetime, label: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must include a UTC offset")
    return value.astimezone(UTC)


def _observed_at(local_time: datetime, published_at: datetime) -> datetime:
    observed_at = _aware_utc(local_time, "observation timestamp")
    if published_at <= observed_at:
        return observed_at
    if published_at - observed_at <= timedelta(minutes=5):
        return published_at
    raise ApiFootballError("API-Football publication timestamp is after observation")


def _position(value: str) -> str:
    positions = {"G": "GK", "D": "DF", "M": "MF", "F": "FW"}
    try:
        return positions[value.upper()]
    except KeyError as exc:
        raise ApiFootballError(f"unsupported API-Football player position: {value}") from exc


def _numeric_metrics(statistics: _PlayerStatistics) -> dict[str, float]:
    payload = statistics.model_dump(exclude_none=True)
    metrics: dict[str, float] = {}
    for group, values in payload.items():
        if group == "games" or not isinstance(values, dict):
            continue
        for name, value in values.items():
            if isinstance(value, bool) or not isinstance(value, int | float):
                continue
            metrics[f"{group}.{name}"] = float(value)
    if statistics.games.rating is not None:
        metrics["games.rating"] = statistics.games.rating
    return metrics
