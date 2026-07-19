from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class NormalizedOdds:
    event_key: str
    competition: str
    season: str
    kickoff_at: datetime
    home_team: str
    away_team: str
    bookmaker: str
    market_type: str
    selection: str
    decimal_odds: float
    captured_at: datetime
    line: float | None = None
    is_closing: bool = False


class OddsProvider(Protocol):
    slug: str
    is_demo: bool

    def collect_odds(self) -> Iterable[NormalizedOdds]: ...


SUPPORTED_PROVIDER_KINDS = {
    "licensed_api",
    "official_source",
    "csv_upload",
    "manual_entry",
    "demo_seed",
}
