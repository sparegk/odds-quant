from __future__ import annotations

from app.providers.api_football import (
    API_FOOTBALL_TERMS_URL,
    ApiFootballInjurySnapshot,
    ApiFootballLineupSnapshot,
    ApiFootballPlayerSnapshot,
)
from app.schemas.intelligence import (
    AvailabilityInput,
    CoachInput,
    IntelligenceImportRequest,
    LineupMemberInput,
    LineupSnapshotInput,
    PlayerAppearanceInput,
    PlayerInput,
    PlayerStatisticInput,
)


class ApiFootballIntelligenceError(ValueError):
    pass


def build_lineup_intelligence_request(
    snapshot: ApiFootballLineupSnapshot,
    *,
    event_id: int,
    local_team_ids: dict[int, int],
) -> IntelligenceImportRequest:
    _require_event_id(event_id)
    if not snapshot.teams:
        raise ApiFootballIntelligenceError("API-Football has not published confirmed lineups")
    _require_team_mappings({team.team_id for team in snapshot.teams}, local_team_ids)
    players: list[PlayerInput] = []
    coaches: list[CoachInput] = []
    lineups: list[LineupSnapshotInput] = []
    for team in snapshot.teams:
        coach_key = str(team.coach_id) if team.coach_id is not None else None
        if coach_key is not None and team.coach_name is not None:
            coaches.append(CoachInput(provider_coach_key=coach_key, name=team.coach_name))
        members: list[LineupMemberInput] = []
        for member in team.members:
            player_key = str(member.player_id)
            players.append(
                PlayerInput(
                    provider_player_key=player_key,
                    name=member.player_name,
                    position=member.position,
                )
            )
            members.append(
                LineupMemberInput(
                    provider_player_key=player_key,
                    starter=member.starter,
                    position=member.position,
                )
            )
        lineups.append(
            LineupSnapshotInput(
                event_id=event_id,
                team_id=local_team_ids[team.team_id],
                provider_coach_key=coach_key,
                lineup_type="confirmed",
                formation=team.formation,
                confidence=1,
                members=members,
                published_at=snapshot.published_at,
                observed_at=snapshot.observed_at,
            )
        )
    return IntelligenceImportRequest(
        **_request_metadata(snapshot.fixture_id, "lineups", snapshot.published_at.isoformat()),
        players=players,
        coaches=coaches,
        lineups=lineups,
    )


def build_injury_intelligence_request(
    snapshot: ApiFootballInjurySnapshot,
    *,
    event_id: int,
    local_team_ids: dict[int, int],
) -> IntelligenceImportRequest:
    _require_event_id(event_id)
    if not snapshot.injuries:
        raise ApiFootballIntelligenceError("API-Football has no injury records for this fixture")
    _require_team_mappings({injury.team_id for injury in snapshot.injuries}, local_team_ids)
    availability: list[AvailabilityInput] = []
    for injury in snapshot.injuries:
        status, confidence = _availability_status(injury.provider_status)
        provider_detail = injury.provider_status
        reason = f"{provider_detail}: {injury.reason}" if injury.reason else provider_detail
        availability.append(
            AvailabilityInput(
                provider_player_key=str(injury.player_id),
                team_id=local_team_ids[injury.team_id],
                event_id=event_id,
                status=status,
                reason=reason,
                evidence_class="licensed_provider",
                confidence=confidence,
                effective_from=snapshot.published_at,
                published_at=snapshot.published_at,
                observed_at=snapshot.observed_at,
            )
        )
    return IntelligenceImportRequest(
        **_request_metadata(snapshot.fixture_id, "injuries", snapshot.published_at.isoformat()),
        availability=availability,
    )


def build_player_intelligence_request(
    snapshot: ApiFootballPlayerSnapshot,
    *,
    event_id: int,
    local_team_ids: dict[int, int],
) -> IntelligenceImportRequest:
    _require_event_id(event_id)
    provider_team_ids = {item.team_id for item in snapshot.performances}
    _require_team_mappings(provider_team_ids, local_team_ids)
    players: list[PlayerInput] = []
    appearances: list[PlayerAppearanceInput] = []
    player_statistics: list[PlayerStatisticInput] = []
    for performance in snapshot.performances:
        player_key = str(performance.player_id)
        local_team_id = local_team_ids[performance.team_id]
        players.append(
            PlayerInput(
                provider_player_key=player_key,
                name=performance.player_name,
                position=performance.position,
            )
        )
        appearances.append(
            PlayerAppearanceInput(
                event_id=event_id,
                provider_player_key=player_key,
                team_id=local_team_id,
                starter=performance.starter,
                minutes=performance.minutes,
                position=performance.position,
                published_at=snapshot.published_at,
                observed_at=snapshot.observed_at,
            )
        )
        if performance.metrics:
            player_statistics.append(
                PlayerStatisticInput(
                    event_id=event_id,
                    provider_player_key=player_key,
                    team_id=local_team_id,
                    metric_schema_version="api-football-fixture-player-v1",
                    minutes=performance.minutes,
                    metrics=performance.metrics,
                    published_at=snapshot.published_at,
                    observed_at=snapshot.observed_at,
                )
            )
    return IntelligenceImportRequest(
        **_request_metadata(snapshot.fixture_id, "players", snapshot.published_at.isoformat()),
        players=players,
        appearances=appearances,
        player_statistics=player_statistics,
    )


def _request_metadata(fixture_id: int, endpoint: str, version: str) -> dict[str, object]:
    paths = {
        "players": "fixtures/players",
        "lineups": "fixtures/lineups",
        "injuries": "injuries",
    }
    path = paths[endpoint]
    return {
        "source_key": f"api-football:fixture:{fixture_id}:{endpoint}:{version}",
        "provider_slug": "api-football",
        "provider_name": "API-Football",
        "provider_kind": "licensed_api",
        "provider_terms_url": API_FOOTBALL_TERMS_URL,
        "source_url": (f"https://v3.football.api-sports.io/{path}?fixture={fixture_id}"),
        "acquisition_method": "licensed_api",
        "usage_authorized": True,
    }


def _require_event_id(event_id: int) -> None:
    if event_id <= 0:
        raise ValueError("event id must be positive")


def _require_team_mappings(provider_team_ids: set[int], local_team_ids: dict[int, int]) -> None:
    missing = sorted(provider_team_ids - set(local_team_ids))
    if missing:
        raise ApiFootballIntelligenceError(
            "missing explicit local team mappings for API-Football team ids: "
            + ", ".join(str(value) for value in missing)
        )


def _availability_status(provider_status: str) -> tuple[str, float]:
    normalized = provider_status.casefold().strip()
    if normalized == "missing fixture":
        return "out", 1.0
    if normalized == "questionable":
        return "doubtful", 0.65
    return "unknown", 0.5
