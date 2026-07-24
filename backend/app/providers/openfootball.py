from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import ValidationError

from app.schemas.results import ResultImportRow

OPENFOOTBALL_LICENSE_URL = "https://github.com/openfootball/football.json/blob/master/LICENSE.md"
OPENFOOTBALL_CHAMPIONS_LICENSE_URL = (
    "https://github.com/openfootball/champions-league/blob/master/LICENSE.md"
)
OPENFOOTBALL_EUROPE_LICENSE_URL = "https://github.com/openfootball/europe/blob/master/LICENSE.md"
_COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}")
_TEXT_DATE_PATTERN = re.compile(
    r"^\s*(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+([A-Z][a-z]{2})\s+(\d{1,2})(?:\s+(\d{4}))?\s*$"
)
_TEXT_MATCH_PATTERN = re.compile(
    r"^\s*(\d{1,2}:\d{2})\s+(.+?)(?:\s+\([A-Z]{3}\))?\s+v\s+"
    r"(.+?)(?:\s+\([A-Z]{3}\))?\s+(\d+)-(\d+)(?:\s+\(\d+-\d+\))?\s*$"
)


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


def normalize_openfootball_text_results(
    content: bytes,
    *,
    dataset_path: str,
    competition: str,
    country: str,
    season: str,
    timezone: str,
    source_commit: str,
    source_updated_at: datetime,
    team_aliases: Mapping[str, str] | None = None,
) -> list[ResultImportRow]:
    """Normalize unambiguous completed Football.TXT rows from one pinned CC0 file."""
    if not _COMMIT_PATTERN.fullmatch(source_commit):
        raise OpenFootballImportError("source_commit must be a full lowercase Git SHA-1")
    if source_updated_at.tzinfo is None or source_updated_at.utcoffset() is None:
        raise OpenFootballImportError("source_updated_at must include a UTC offset")
    try:
        local_timezone = ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise OpenFootballImportError(f"unknown IANA timezone: {timezone}") from exc
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise OpenFootballImportError("source file must be valid UTF-8 Football.TXT") from exc
    aliases = dict(team_aliases or {})
    if any(not key.strip() or not value.strip() for key, value in aliases.items()):
        raise OpenFootballImportError("team aliases must map non-empty names")
    observed_at = source_updated_at.astimezone(UTC)
    current_date: datetime | None = None
    current_year: int | None = None
    rows: list[ResultImportRow] = []
    identities: set[tuple[datetime, str, str]] = set()
    for line_number, line in enumerate(text.splitlines(), start=1):
        date_match = _TEXT_DATE_PATTERN.match(line)
        if date_match:
            month, day, explicit_year = date_match.groups()
            if explicit_year is not None:
                current_year = int(explicit_year)
            if current_year is None:
                raise OpenFootballImportError(f"line {line_number} date omits the initial year")
            try:
                current_date = datetime.strptime(f"{current_year} {month} {day}", "%Y %b %d")
            except ValueError as exc:
                raise OpenFootballImportError(
                    f"line {line_number} contains an invalid date"
                ) from exc
            continue
        if " v " not in line or not re.search(r"\d+-\d+", line):
            continue
        if " pen." in line or " a.e.t." in line or "[awarded]" in line:
            continue
        match = _TEXT_MATCH_PATTERN.match(line)
        if match is None:
            # Rows without a published kickoff time cannot safely become event identities.
            if not re.match(r"^\s*\d{1,2}:\d{2}", line):
                continue
            raise OpenFootballImportError(
                f"line {line_number} is not an unambiguous completed match"
            )
        if current_date is None:
            raise OpenFootballImportError(
                f"line {line_number} match appears before a dated section"
            )
        kickoff_text, source_home, source_away, home_goals, away_goals = match.groups()
        hour, minute = (int(part) for part in kickoff_text.split(":"))
        try:
            kickoff_local = current_date.replace(hour=hour, minute=minute, tzinfo=local_timezone)
        except ValueError as exc:
            raise OpenFootballImportError(
                f"line {line_number} contains an invalid kickoff time"
            ) from exc
        kickoff_at = kickoff_local.astimezone(UTC)
        if observed_at < kickoff_at:
            raise OpenFootballImportError(
                f"line {line_number} was not available at the pinned source timestamp"
            )
        home_team = aliases.get(source_home, source_home).strip()
        away_team = aliases.get(source_away, source_away).strip()
        identity = (kickoff_at, home_team, away_team)
        if identity in identities:
            raise OpenFootballImportError(f"line {line_number} duplicates an earlier fixture")
        identities.add(identity)
        digest = hashlib.sha256(
            f"{dataset_path}|{kickoff_at.isoformat()}|{source_home}|{source_away}".encode()
        ).hexdigest()[:24]
        rows.append(
            ResultImportRow(
                provider_event_key=f"openfootball-champions:{digest}",
                competition=competition,
                country=country,
                season=season,
                kickoff_at=kickoff_at,
                home_team=home_team,
                away_team=away_team,
                home_goals=int(home_goals),
                away_goals=int(away_goals),
                # The pinned file commit is the first publication evidence asserted here.
                settled_at=observed_at,
                observed_at=observed_at,
                source_updated_at=observed_at,
            )
        )
    if not rows:
        raise OpenFootballImportError(
            "source file contains no unambiguous completed matches with kickoff times"
        )
    return rows


def _required_text(match: dict[str, object], key: str) -> str:
    value = match.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be non-empty text")
    return value.strip()
