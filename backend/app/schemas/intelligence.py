from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Position = Literal["GK", "DF", "MF", "FW"]
AvailabilityStatus = Literal["available", "doubtful", "out", "injured", "suspended", "unknown"]
EvidenceClass = Literal["official", "licensed_provider", "manual", "correction"]
LineupType = Literal["expected", "confirmed"]


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PublishedEvidence(StrictInput):
    published_at: datetime
    observed_at: datetime

    @field_validator("published_at", "observed_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a UTC offset")
        return value

    @model_validator(mode="after")
    def validate_publication_order(self) -> PublishedEvidence:
        if self.published_at > self.observed_at:
            raise ValueError("published_at cannot be after observed_at")
        return self


class PlayerInput(StrictInput):
    provider_player_key: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=160)
    position: Position
    preferred_side: Literal["left", "right", "both"] | None = None
    birth_year: int | None = Field(default=None, ge=1900, le=2100)


class CoachInput(StrictInput):
    provider_coach_key: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=160)


class PlayerRegistrationInput(PublishedEvidence):
    provider_player_key: str = Field(min_length=1, max_length=120)
    team_id: int = Field(gt=0)
    competition_id: int | None = Field(default=None, gt=0)
    valid_from: datetime
    valid_to: datetime | None = None
    squad_number: int | None = Field(default=None, ge=1, le=99)

    @model_validator(mode="after")
    def validate_validity(self) -> PlayerRegistrationInput:
        if self.valid_to is not None and self.valid_to <= self.valid_from:
            raise ValueError("valid_to must be after valid_from")
        return self


class CoachTenureInput(PublishedEvidence):
    provider_coach_key: str = Field(min_length=1, max_length=120)
    team_id: int = Field(gt=0)
    valid_from: datetime
    valid_to: datetime | None = None

    @model_validator(mode="after")
    def validate_validity(self) -> CoachTenureInput:
        if self.valid_to is not None and self.valid_to <= self.valid_from:
            raise ValueError("valid_to must be after valid_from")
        return self


class PlayerAppearanceInput(PublishedEvidence):
    event_id: int = Field(gt=0)
    provider_player_key: str = Field(min_length=1, max_length=120)
    team_id: int = Field(gt=0)
    starter: bool
    minutes: int = Field(ge=0, le=130)
    position: Position
    role: str | None = Field(default=None, max_length=80)


class PlayerStatisticInput(PublishedEvidence):
    event_id: int = Field(gt=0)
    provider_player_key: str = Field(min_length=1, max_length=120)
    team_id: int = Field(gt=0)
    metric_schema_version: str = Field(min_length=1, max_length=60)
    minutes: int = Field(ge=0, le=130)
    metrics: dict[str, float] = Field(min_length=1, max_length=100)


class AvailabilityInput(PublishedEvidence):
    provider_player_key: str = Field(min_length=1, max_length=120)
    team_id: int = Field(gt=0)
    event_id: int | None = Field(default=None, gt=0)
    status: AvailabilityStatus
    reason: str | None = Field(default=None, max_length=255)
    evidence_class: EvidenceClass
    confidence: float = Field(ge=0, le=1)
    effective_from: datetime
    effective_to: datetime | None = None

    @model_validator(mode="after")
    def validate_validity(self) -> AvailabilityInput:
        if self.effective_to is not None and self.effective_to <= self.effective_from:
            raise ValueError("effective_to must be after effective_from")
        return self


class LineupMemberInput(StrictInput):
    provider_player_key: str = Field(min_length=1, max_length=120)
    starter: bool
    position: Position
    role: str | None = Field(default=None, max_length=80)
    expected_probability: float | None = Field(default=None, ge=0, le=1)


class LineupSnapshotInput(PublishedEvidence):
    event_id: int = Field(gt=0)
    team_id: int = Field(gt=0)
    provider_coach_key: str | None = Field(default=None, min_length=1, max_length=120)
    lineup_type: LineupType
    formation: str | None = Field(default=None, max_length=30)
    confidence: float = Field(ge=0, le=1)
    members: list[LineupMemberInput] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def validate_members(self) -> LineupSnapshotInput:
        keys = [member.provider_player_key for member in self.members]
        if len(keys) != len(set(keys)):
            raise ValueError("lineup contains duplicate player identities")
        starters = sum(member.starter for member in self.members)
        if starters > 11:
            raise ValueError("lineup cannot contain more than 11 starters")
        if self.lineup_type == "confirmed":
            if starters != 11:
                raise ValueError("confirmed lineup must contain exactly 11 starters")
            if self.confidence != 1:
                raise ValueError("confirmed lineup confidence must equal 1")
            if any(member.expected_probability is not None for member in self.members):
                raise ValueError("confirmed lineup members cannot carry expected probabilities")
        elif any(member.expected_probability is None for member in self.members):
            raise ValueError("expected lineup members require expected_probability")
        return self


class TacticalSnapshotInput(PublishedEvidence):
    event_id: int | None = Field(default=None, gt=0)
    team_id: int = Field(gt=0)
    provider_coach_key: str | None = Field(default=None, min_length=1, max_length=120)
    formation: str | None = Field(default=None, max_length=30)
    as_of: datetime
    metrics: dict[str, float] = Field(min_length=1, max_length=100)
    labels: list[str] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def validate_cutoff(self) -> TacticalSnapshotInput:
        if self.as_of > self.observed_at:
            raise ValueError("as_of cannot be after observed_at")
        if len(self.labels) != len(set(self.labels)):
            raise ValueError("tactical labels must be unique")
        return self


class IntelligenceImportRequest(StrictInput):
    source_key: str = Field(min_length=1, max_length=255)
    provider_slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=60)
    provider_name: str = Field(min_length=1, max_length=120)
    is_demo: bool = False
    players: list[PlayerInput] = Field(default_factory=list, max_length=5000)
    coaches: list[CoachInput] = Field(default_factory=list, max_length=1000)
    registrations: list[PlayerRegistrationInput] = Field(default_factory=list, max_length=10000)
    coach_tenures: list[CoachTenureInput] = Field(default_factory=list, max_length=5000)
    appearances: list[PlayerAppearanceInput] = Field(default_factory=list, max_length=50000)
    player_statistics: list[PlayerStatisticInput] = Field(default_factory=list, max_length=50000)
    availability: list[AvailabilityInput] = Field(default_factory=list, max_length=10000)
    lineups: list[LineupSnapshotInput] = Field(default_factory=list, max_length=5000)
    tactics: list[TacticalSnapshotInput] = Field(default_factory=list, max_length=10000)

    @model_validator(mode="after")
    def require_records(self) -> IntelligenceImportRequest:
        collections = (
            self.players,
            self.coaches,
            self.registrations,
            self.coach_tenures,
            self.appearances,
            self.player_statistics,
            self.availability,
            self.lineups,
            self.tactics,
        )
        if not any(collections):
            raise ValueError("intelligence import must contain at least one record")
        return self


class IntelligenceImportSummary(BaseModel):
    job_id: int
    status: str
    rows_received: int
    rows_imported: int
    created: dict[str, int]
    content_sha256: str


class IntelligenceCoverageView(BaseModel):
    event_id: int
    as_of: datetime
    historical_player_statistics: int
    availability_reports: int
    expected_lineups: int
    confirmed_lineups: int
    tactical_snapshots: int
    coach_tenures: int
    status: Literal["available", "partial", "missing"]
    missing_inputs: list[str]
