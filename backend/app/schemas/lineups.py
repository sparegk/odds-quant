from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class ProjectedLineupMemberView(BaseModel):
    player_id: int
    player: str
    position: Literal["GK", "DF", "MF", "FW"]
    role: str | None
    start_probability: float
    recent_appearances: int
    recent_starts: int
    recent_minutes: int
    availability_status: str


class ExpectedLineupScenarioView(BaseModel):
    event_id: int
    team_id: int
    team: str
    status: Literal["projected", "insufficient_data"]
    scenario_kind: Literal["availability_weighted", "doubtful_available"]
    formation: str
    as_of: datetime
    feature_version: str
    input_fingerprint: str
    historical_matches: int
    confidence: float
    uncertainty: float
    starters: list[ProjectedLineupMemberView]
    alternates: list[ProjectedLineupMemberView]
    warnings: list[str]
