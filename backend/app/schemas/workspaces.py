from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=160)
    eventId: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=240)
    subtitle: str = Field(max_length=240)
    kind: Literal["match", "qualified_signal", "research_candidate"]
    offeredOdds: float | None = Field(default=None, gt=1)
    modelProbability: float | None = Field(default=None, ge=0, le=1)
    marketProbability: float | None = Field(default=None, ge=0, le=1)
    edge: float | None = None
    evidenceId: str = Field(min_length=1, max_length=240)
    note: str = Field(default="", max_length=2000)
    savedAt: datetime


class WorkspaceWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120, pattern=r"^[^/\\]+$")
    items: list[WorkspaceItem] = Field(default_factory=list, max_length=500)


class WorkspaceView(WorkspaceWrite):
    id: int
    created_at: datetime
    updated_at: datetime
