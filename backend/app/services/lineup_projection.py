from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import AvailabilityReport, Event, Player, PlayerAppearance, Team
from app.schemas.lineups import ExpectedLineupScenarioView, ProjectedLineupMemberView

FEATURE_VERSION = "expected-lineup-v1"
FORMATION = "4-3-3"
POSITION_QUOTAS = {"GK": 1, "DF": 4, "MF": 3, "FW": 3}
RECENCY_DECAY = 0.82


@dataclass
class _Candidate:
    player: Player
    role: str | None
    recent_appearances: int = 0
    recent_starts: int = 0
    recent_minutes: int = 0
    weighted_starts: float = 0
    weighted_minutes: float = 0
    weighted_competition_starts: float = 0
    availability_status: str = "unknown"
    availability_id: int | None = None


def project_expected_lineups(
    session: Session,
    *,
    event_id: int,
    as_of: datetime | None = None,
    history_matches: int = 8,
) -> list[ExpectedLineupScenarioView]:
    if history_matches < 1 or history_matches > 20:
        raise ValueError("history_matches must be between 1 and 20")
    target = session.get(Event, event_id)
    if target is None:
        raise ValueError("event not found")
    reference = _utc(as_of or datetime.now(UTC))
    cutoff = min(reference, _utc(target.kickoff_at))
    return [
        scenario
        for team_id in (target.home_team_id, target.away_team_id)
        for scenario in _team_scenarios(
            session,
            target=target,
            team_id=team_id,
            cutoff=cutoff,
            history_matches=history_matches,
        )
    ]


def _team_scenarios(
    session: Session,
    *,
    target: Event,
    team_id: int,
    cutoff: datetime,
    history_matches: int,
) -> list[ExpectedLineupScenarioView]:
    team = session.get_one(Team, team_id)
    event_rows = session.execute(
        select(Event.id, Event.kickoff_at, Event.competition_id)
        .join(PlayerAppearance, PlayerAppearance.event_id == Event.id)
        .where(
            PlayerAppearance.team_id == team_id,
            Event.kickoff_at < target.kickoff_at,
            PlayerAppearance.observed_at <= cutoff,
            PlayerAppearance.source_updated_at.is_not(None),
            PlayerAppearance.source_updated_at <= cutoff,
        )
        .distinct()
        .order_by(Event.kickoff_at.desc(), Event.id.desc())
        .limit(history_matches)
    ).all()
    event_ids = [row.id for row in event_rows]
    if not event_ids:
        return [
            _empty_scenario(
                target=target,
                team=team,
                cutoff=cutoff,
                history_matches=0,
                warning="No timestamp-valid prior appearances are stored for this team.",
            )
        ]

    rank = {row.id: index for index, row in enumerate(event_rows)}
    weights = {event_id: RECENCY_DECAY**event_rank for event_id, event_rank in rank.items()}
    total_weight = sum(weights.values())
    competition_weight = sum(
        weights[row.id] for row in event_rows if row.competition_id == target.competition_id
    )
    rows = session.execute(
        select(PlayerAppearance, Player)
        .join(Player, Player.id == PlayerAppearance.player_id)
        .where(
            PlayerAppearance.team_id == team_id,
            PlayerAppearance.event_id.in_(event_ids),
            PlayerAppearance.observed_at <= cutoff,
            PlayerAppearance.source_updated_at.is_not(None),
            PlayerAppearance.source_updated_at <= cutoff,
        )
        .order_by(
            PlayerAppearance.event_id,
            PlayerAppearance.player_id,
            PlayerAppearance.observed_at.desc(),
            PlayerAppearance.id.desc(),
        )
    ).all()
    canonical: dict[tuple[int, int], tuple[PlayerAppearance, Player]] = {}
    for appearance, player in rows:
        canonical.setdefault((appearance.event_id, player.id), (appearance, player))

    candidates: dict[int, _Candidate] = {}
    evidence_rows: list[dict[str, object]] = []
    event_competitions = {row.id: row.competition_id for row in event_rows}
    for appearance, player in canonical.values():
        candidate = candidates.setdefault(
            player.id, _Candidate(player=player, role=appearance.role)
        )
        weight = weights[appearance.event_id]
        candidate.recent_appearances += 1
        candidate.recent_starts += int(appearance.starter)
        candidate.recent_minutes += appearance.minutes
        candidate.weighted_starts += weight * int(appearance.starter)
        candidate.weighted_minutes += weight * min(appearance.minutes, 90) / 90
        if event_competitions[appearance.event_id] == target.competition_id:
            candidate.weighted_competition_starts += weight * int(appearance.starter)
        evidence_rows.append(
            {
                "appearance_id": appearance.id,
                "event_id": appearance.event_id,
                "player_id": player.id,
                "starter": appearance.starter,
                "minutes": appearance.minutes,
                "position": appearance.position,
                "observed_at": _utc(appearance.observed_at).isoformat(),
                "published_at": _utc(cast(datetime, appearance.source_updated_at)).isoformat(),
            }
        )

    availability_rows = session.scalars(
        select(AvailabilityReport)
        .where(
            AvailabilityReport.team_id == team_id,
            or_(AvailabilityReport.event_id.is_(None), AvailabilityReport.event_id == target.id),
            AvailabilityReport.observed_at <= cutoff,
            AvailabilityReport.source_updated_at.is_not(None),
            AvailabilityReport.source_updated_at <= cutoff,
            AvailabilityReport.effective_from <= cutoff,
            or_(
                AvailabilityReport.effective_to.is_(None),
                AvailabilityReport.effective_to > cutoff,
            ),
        )
        .order_by(
            AvailabilityReport.player_id,
            AvailabilityReport.observed_at.desc(),
            AvailabilityReport.id.desc(),
        )
    ).all()
    latest_availability: dict[int, AvailabilityReport] = {}
    for report in availability_rows:
        latest_availability.setdefault(report.player_id, report)
    for player_id, report in latest_availability.items():
        report_candidate = candidates.get(player_id)
        if report_candidate is not None:
            report_candidate.availability_status = report.status
            report_candidate.availability_id = report.id

    fingerprint = _fingerprint(
        target=target,
        team_id=team_id,
        cutoff=cutoff,
        evidence_rows=evidence_rows,
        availability=latest_availability,
    )
    scenarios = [
        _build_scenario(
            target=target,
            team=team,
            cutoff=cutoff,
            history_matches=len(event_rows),
            requested_history=history_matches,
            candidates=candidates,
            total_weight=total_weight,
            competition_weight=competition_weight,
            fingerprint=fingerprint,
            scenario_kind="availability_weighted",
        )
    ]
    if any(value.availability_status == "doubtful" for value in candidates.values()):
        scenarios.append(
            _build_scenario(
                target=target,
                team=team,
                cutoff=cutoff,
                history_matches=len(event_rows),
                requested_history=history_matches,
                candidates=candidates,
                total_weight=total_weight,
                competition_weight=competition_weight,
                fingerprint=fingerprint,
                scenario_kind="doubtful_available",
            )
        )
    return scenarios


def _build_scenario(
    *,
    target: Event,
    team: Team,
    cutoff: datetime,
    history_matches: int,
    requested_history: int,
    candidates: dict[int, _Candidate],
    total_weight: float,
    competition_weight: float,
    fingerprint: str,
    scenario_kind: str,
) -> ExpectedLineupScenarioView:
    probabilities = {
        player_id: _probability(
            candidate,
            total_weight=total_weight,
            competition_weight=competition_weight,
            doubtful_available=scenario_kind == "doubtful_available",
        )
        for player_id, candidate in candidates.items()
    }
    by_position: dict[str, list[_Candidate]] = defaultdict(list)
    for candidate in candidates.values():
        by_position[candidate.player.position].append(candidate)
    selected: list[_Candidate] = []
    warnings: list[str] = []
    for position, quota in POSITION_QUOTAS.items():
        ranked = sorted(
            by_position[position],
            key=lambda item: (
                -probabilities[item.player.id],
                -item.recent_starts,
                -item.recent_minutes,
                item.player.id,
            ),
        )
        selected.extend(ranked[:quota])
        if len(ranked) < quota:
            warnings.append(
                f"Only {len(ranked)} of {quota} required {position} candidates are stored."
            )
    selected_ids = {candidate.player.id for candidate in selected}
    alternates = sorted(
        (candidate for candidate in candidates.values() if candidate.player.id not in selected_ids),
        key=lambda item: (-probabilities[item.player.id], item.player.id),
    )[:5]
    if history_matches < requested_history:
        warnings.append(
            f"Only {history_matches} timestamp-valid matches are stored "
            f"(target {requested_history})."
        )
    unresolved = sum(
        candidate.availability_status in {"doubtful", "unknown"} for candidate in selected
    )
    coverage = min(1.0, history_matches / requested_history)
    mean_probability = (
        sum(probabilities[item.player.id] for item in selected) / len(selected) if selected else 0
    )
    confidence = round(mean_probability * coverage * (1 - 0.15 * unresolved / 11), 3)
    status = (
        "projected"
        if len(selected) == 11 and not any("required" in w for w in warnings)
        else "insufficient_data"
    )
    if status == "insufficient_data":
        warnings.append("A complete position-valid XI cannot be projected from stored evidence.")
    return ExpectedLineupScenarioView(
        event_id=target.id,
        team_id=team.id,
        team=team.name,
        status=status,
        scenario_kind=scenario_kind,
        formation=FORMATION,
        as_of=cutoff,
        feature_version=FEATURE_VERSION,
        input_fingerprint=fingerprint,
        historical_matches=history_matches,
        confidence=confidence,
        uncertainty=round(1 - confidence, 3),
        starters=[_member(item, probabilities[item.player.id]) for item in selected],
        alternates=[_member(item, probabilities[item.player.id]) for item in alternates],
        warnings=warnings,
    )


def _probability(
    candidate: _Candidate,
    *,
    total_weight: float,
    competition_weight: float,
    doubtful_available: bool,
) -> float:
    start_rate = (candidate.weighted_starts + 0.5) / (total_weight + 1)
    minute_rate = (candidate.weighted_minutes + 0.5) / (total_weight + 1)
    competition_rate = (
        (candidate.weighted_competition_starts + 0.5) / (competition_weight + 1)
        if competition_weight
        else start_rate
    )
    base = 0.55 * start_rate + 0.30 * minute_rate + 0.15 * competition_rate
    multiplier = {
        "available": 1.0,
        "doubtful": 0.90 if doubtful_available else 0.45,
        "unknown": 0.80,
        "out": 0.0,
        "injured": 0.0,
        "suspended": 0.0,
    }.get(candidate.availability_status, 0.80)
    return round(max(0.0, min(0.98, base * multiplier)), 4)


def _member(candidate: _Candidate, probability: float) -> ProjectedLineupMemberView:
    return ProjectedLineupMemberView(
        player_id=candidate.player.id,
        player=candidate.player.name,
        position=candidate.player.position,
        role=candidate.role,
        start_probability=probability,
        recent_appearances=candidate.recent_appearances,
        recent_starts=candidate.recent_starts,
        recent_minutes=candidate.recent_minutes,
        availability_status=candidate.availability_status,
    )


def _empty_scenario(
    *,
    target: Event,
    team: Team,
    cutoff: datetime,
    history_matches: int,
    warning: str,
) -> ExpectedLineupScenarioView:
    fingerprint = hashlib.sha256(
        f"{FEATURE_VERSION}:{target.id}:{team.id}:{cutoff.isoformat()}:empty".encode()
    ).hexdigest()
    return ExpectedLineupScenarioView(
        event_id=target.id,
        team_id=team.id,
        team=team.name,
        status="insufficient_data",
        scenario_kind="availability_weighted",
        formation=FORMATION,
        as_of=cutoff,
        feature_version=FEATURE_VERSION,
        input_fingerprint=fingerprint,
        historical_matches=history_matches,
        confidence=0,
        uncertainty=1,
        starters=[],
        alternates=[],
        warnings=[
            warning,
            "A complete position-valid XI cannot be projected from stored evidence.",
        ],
    )


def _fingerprint(
    *,
    target: Event,
    team_id: int,
    cutoff: datetime,
    evidence_rows: list[dict[str, object]],
    availability: dict[int, AvailabilityReport],
) -> str:
    payload = {
        "feature_version": FEATURE_VERSION,
        "event_id": target.id,
        "team_id": team_id,
        "cutoff": cutoff.isoformat(),
        "appearances": sorted(evidence_rows, key=lambda row: str(row["appearance_id"])),
        "availability": [
            {
                "id": report.id,
                "player_id": report.player_id,
                "status": report.status,
                "observed_at": _utc(report.observed_at).isoformat(),
                "published_at": _utc(cast(datetime, report.source_updated_at)).isoformat(),
            }
            for report in sorted(availability.values(), key=lambda item: item.id)
        ],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
