from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from app.schemas.odds import OddsImportRow

type NormalizedOdds = OddsImportRow


class OddsProvider(Protocol):
    slug: str
    name: str
    kind: str
    is_demo: bool
    terms_url: str | None

    def collect_odds(self) -> Iterable[NormalizedOdds]: ...


SUPPORTED_PROVIDER_KINDS = {
    "licensed_api",
    "official_source",
    "csv_upload",
    "manual_entry",
    "open_data",
    "demo_seed",
}
