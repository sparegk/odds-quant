from __future__ import annotations

from app.providers.api_football import (
    API_FOOTBALL_TERMS_URL,
    ApiFootballPlayerSnapshot,
)
from app.schemas.intelligence import (
    IntelligenceImportRequest,
    PlayerAppearanceInput,
    PlayerInput,
    PlayerStatisticInput,
)


class ApiFootballIntelligenceError(ValueError):
    pass


def build_player_intelligence_request(
    snapshot: ApiFootballPlayerSnapshot,
    *,
    event_id: int,
    local_team_ids: dict[int, int],
) -> IntelligenceImportRequest:
    if event_id <= 0:
        raise ValueError("event id must be positive")
    provider_team_ids = {item.team_id for item in snapshot.performances}
    missing = sorted(provider_team_ids - set(local_team_ids))
    if missing:
        raise ApiFootballIntelligenceError(
            "missing explicit local team mappings for API-Football team ids: "
            + ", ".join(str(value) for value in missing)
        )
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
        source_key=(
            f"api-football:fixture:{snapshot.fixture_id}:players:"
            f"{snapshot.published_at.isoformat()}"
        ),
        provider_slug="api-football",
        provider_name="API-Football",
        provider_kind="licensed_api",
        provider_terms_url=API_FOOTBALL_TERMS_URL,
        source_url=(
            f"https://v3.football.api-sports.io/fixtures/players?fixture={snapshot.fixture_id}"
        ),
        acquisition_method="licensed_api",
        usage_authorized=True,
        players=players,
        appearances=appearances,
        player_statistics=player_statistics,
    )
