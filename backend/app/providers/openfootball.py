from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import ValidationError

from app.schemas.results import ResultImportRow

OPENFOOTBALL_LICENSE_URL = "https://github.com/openfootball/football.json/blob/master/LICENSE.md"
_COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}")


class OpenFootballImportError(ValueError):
    pass


def normalize_openfootball_results(
    content: bytes,
    *,
    dataset_path: str,
    competition: str,
    country: str,
    season: str,
    timezone: str,
    source_commit: str,
    source_updated_at: datetime,
) -> list[ResultImportRow]:
    """Normalize one pinned OpenFootball JSON file without inventing result availability."""
    if not _COMMIT_PATTERN.fullmatch(source_commit):
        raise OpenFootballImportError("source_commit must be a full lowercase Git SHA-1")
    if source_updated_at.tzinfo is None or source_updated_at.utcoffset() is None:
        raise OpenFootballImportError("source_updated_at must include a UTC offset")
    try:
        local_timezone = ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise OpenFootballImportError(f"unknown IANA timezone: {timezone}") from exc
    try:
        payload = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OpenFootballImportError("source file must be valid UTF-8 JSON") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("matches"), list):
        raise OpenFootballImportError("source file must contain a matches array")

    observed_at = source_updated_at.astimezone(UTC)
    rows: list[ResultImportRow] = []
    identities: set[tuple[datetime, str, str]] = set()
    for index, match in enumerate(payload["matches"], start=1):
        if not isinstance(match, dict):
            raise OpenFootballImportError(f"match {index} must be an object")
        try:
            kickoff_local = datetime.strptime(
                f"{match['date']} {match['time']}", "%Y-%m-%d %H:%M"
            ).replace(tzinfo=local_timezone)
            home_team = _required_text(match, "team1")
            away_team = _required_text(match, "team2")
            score = match["score"]
            full_time = score.get("ft") if isinstance(score, dict) else score
            if (
                not isinstance(full_time, list)
                or len(full_time) != 2
                or any(type(goals) is not int or goals < 0 for goals in full_time)
            ):
                raise ValueError("score.ft must contain two non-negative integers")
        except (KeyError, TypeError, ValueError) as exc:
            raise OpenFootballImportError(f"match {index} is incomplete: {exc}") from exc
        kickoff_at = kickoff_local.astimezone(UTC)
        if observed_at < kickoff_at:
            raise OpenFootballImportError(
                f"match {index} was not available at the pinned source timestamp"
            )
        identity = (kickoff_at, home_team, away_team)
        if identity in identities:
            raise OpenFootballImportError(f"match {index} duplicates an earlier fixture")
        identities.add(identity)
        event_digest = hashlib.sha256(
            f"{dataset_path}|{kickoff_at.isoformat()}|{home_team}|{away_team}".encode()
        ).hexdigest()[:24]
        try:
            rows.append(
                ResultImportRow(
                    provider_event_key=f"openfootball:{event_digest}",
                    competition=competition,
                    country=country,
                    season=season,
                    kickoff_at=kickoff_at,
                    home_team=home_team,
                    away_team=away_team,
                    home_goals=full_time[0],
                    away_goals=full_time[1],
                    # The file commit is the first evidence asserted here. It is deliberately
                    # used for settlement and observation rather than guessing match-end times.
                    settled_at=observed_at,
                    observed_at=observed_at,
                    source_updated_at=observed_at,
                )
            )
        except ValidationError as exc:
            raise OpenFootballImportError(f"match {index} is invalid: {exc}") from exc
    if not rows:
        raise OpenFootballImportError("source file contains no matches")
    return rows


def _required_text(match: dict[str, object], key: str) -> str:
    value = match.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be non-empty text")
    return value.strip()
