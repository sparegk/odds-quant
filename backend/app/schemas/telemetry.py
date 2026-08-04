from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ClientTelemetryEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: Literal["frontend_error", "api_failure"]
    route: str = Field(min_length=1, max_length=160, pattern=r"^/[-A-Za-z0-9_/:.]*$")
    error_type: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    status: int | None = Field(default=None, ge=400, le=599)
    duration_ms: float | None = Field(default=None, ge=0, le=300000)
