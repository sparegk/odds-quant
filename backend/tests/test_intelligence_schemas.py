from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.schemas.intelligence import IntelligenceImportRequest

NOW = datetime(2026, 7, 21, 12, 0, tzinfo=UTC)


def _base_request() -> dict[str, object]:
    return {
        "source_key": "official:event-42:lineups:v1",
        "provider_slug": "official-club",
        "provider_name": "Official club publication",
        "players": [
            {
                "provider_player_key": f"player-{index}",
                "name": f"Player {index}",
                "position": "GK" if index == 1 else "DF",
            }
            for index in range(1, 12)
        ],
    }


def test_intelligence_contract_separates_expected_and_confirmed_lineups() -> None:
    request = _base_request()
    request["lineups"] = [
        {
            "event_id": 42,
            "team_id": 7,
            "lineup_type": "confirmed",
            "formation": "4-3-3",
            "confidence": 1,
            "published_at": NOW - timedelta(minutes=65),
            "observed_at": NOW - timedelta(minutes=64),
            "members": [
                {
                    "provider_player_key": f"player-{index}",
                    "starter": True,
                    "position": "GK" if index == 1 else "DF",
                }
                for index in range(1, 12)
            ],
        }
    ]

    parsed = IntelligenceImportRequest.model_validate(request)

    assert parsed.lineups[0].lineup_type == "confirmed"
    assert len(parsed.lineups[0].members) == 11


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (
            {"confidence": 0.9},
            "confirmed lineup confidence must equal 1",
        ),
        (
            {"members": []},
            "List should have at least 1 item",
        ),
    ],
)
def test_confirmed_lineup_contract_fails_closed(change: dict[str, object], message: str) -> None:
    request = _base_request()
    lineup: dict[str, object] = {
        "event_id": 42,
        "team_id": 7,
        "lineup_type": "confirmed",
        "confidence": 1,
        "published_at": NOW,
        "observed_at": NOW,
        "members": [
            {
                "provider_player_key": f"player-{index}",
                "starter": True,
                "position": "GK" if index == 1 else "DF",
            }
            for index in range(1, 12)
        ],
    }
    lineup.update(change)
    request["lineups"] = [lineup]

    with pytest.raises(ValidationError, match=message):
        IntelligenceImportRequest.model_validate(request)


def test_expected_lineup_requires_explicit_player_probabilities() -> None:
    request = _base_request()
    request["lineups"] = [
        {
            "event_id": 42,
            "team_id": 7,
            "lineup_type": "expected",
            "confidence": 0.7,
            "published_at": NOW,
            "observed_at": NOW,
            "members": [
                {
                    "provider_player_key": "player-1",
                    "starter": True,
                    "position": "GK",
                }
            ],
        }
    ]

    with pytest.raises(ValidationError, match="require expected_probability"):
        IntelligenceImportRequest.model_validate(request)


def test_intelligence_evidence_requires_original_publication_chronology() -> None:
    request = _base_request()
    request["availability"] = [
        {
            "provider_player_key": "player-1",
            "team_id": 7,
            "status": "out",
            "evidence_class": "official",
            "confidence": 1,
            "effective_from": NOW,
            "published_at": NOW + timedelta(minutes=1),
            "observed_at": NOW,
        }
    ]

    with pytest.raises(ValidationError, match="published_at cannot be after observed_at"):
        IntelligenceImportRequest.model_validate(request)


def test_intelligence_import_rejects_empty_or_unknown_payloads() -> None:
    with pytest.raises(ValidationError, match="at least one record"):
        IntelligenceImportRequest.model_validate(
            {
                "source_key": "empty",
                "provider_slug": "manual-research",
                "provider_name": "Manual research",
            }
        )
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        IntelligenceImportRequest.model_validate(
            {
                "source_key": "unknown",
                "provider_slug": "manual-research",
                "provider_name": "Manual research",
                "players": [
                    {
                        "provider_player_key": "player-1",
                        "name": "Player 1",
                        "position": "GK",
                        "rating": 9.9,
                    }
                ],
            }
        )
