from __future__ import annotations

import csv
import io
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.schemas.odds import ImportSummary
from app.schemas.results import ResultImportRow, ResultImportSummary
from app.services.odds_import import import_odds_csv
from app.services.results_import import import_results_csv, serialize_result_rows_csv

DEMO_TEAMS = (
    "Northbridge FC",
    "Riverside Athletic",
    "Harbour City",
    "Kingsport United",
    "Easton Rovers",
    "Vale Town",
    "Redwood Albion",
    "Metro Wanderers",
)


def build_demo_odds_csv(as_of: datetime) -> bytes:
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of must include a UTC offset")
    anchor = as_of.astimezone(UTC).replace(second=0, microsecond=0)
    events = [
        ("Northbridge FC", "Riverside Athletic", 24, (2.18, 3.35, 3.42), (2.24, 3.25, 3.36)),
        ("Harbour City", "Kingsport United", 28, (1.72, 3.85, 4.95), (1.76, 3.75, 4.75)),
        ("Easton Rovers", "Vale Town", 48, (3.70, 3.30, 2.05), (3.82, 3.25, 2.00)),
        ("Redwood Albion", "Metro Wanderers", 52, (2.62, 3.15, 2.82), (2.68, 3.10, 2.76)),
    ]
    fieldnames = [
        "provider_event_key",
        "competition",
        "country",
        "season",
        "kickoff_at",
        "home_team",
        "away_team",
        "bookmaker",
        "market_type",
        "line",
        "selection_code",
        "selection_name",
        "decimal_odds",
        "observed_at",
        "source_updated_at",
        "period",
        "currency",
        "settlement_rule_key",
        "is_closing",
    ]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    codes = (("HOME", "Home win"), ("DRAW", "Draw"), ("AWAY", "Away win"))
    for index, (home, away, hours, atlas_prices, beacon_prices) in enumerate(events, start=1):
        kickoff = anchor + timedelta(hours=hours)
        event_key = f"demo-{anchor:%Y%m%d}-{index}"
        for bookmaker, prices in (
            ("Demo Atlas Sports", atlas_prices),
            ("Demo Beacon Bet", beacon_prices),
        ):
            for (selection_code, selection_name), price in zip(codes, prices, strict=True):
                writer.writerow(
                    {
                        "provider_event_key": event_key,
                        "competition": "Synthetic Premier Division",
                        "country": "Demo Republic",
                        "season": f"{anchor.year}/{anchor.year + 1}",
                        "kickoff_at": kickoff.isoformat(),
                        "home_team": home,
                        "away_team": away,
                        "bookmaker": bookmaker,
                        "market_type": "MATCH_RESULT",
                        "line": "",
                        "selection_code": selection_code,
                        "selection_name": selection_name,
                        "decimal_odds": f"{price:.2f}",
                        "observed_at": anchor.isoformat(),
                        "source_updated_at": anchor.isoformat(),
                        "period": "FULL_TIME",
                        "currency": "EUR",
                        "settlement_rule_key": "standard_90_minutes",
                        "is_closing": "false",
                    }
                )
    return stream.getvalue().encode("utf-8")


def build_demo_results_csv(as_of: datetime) -> bytes:
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of must include a UTC offset")
    anchor = as_of.astimezone(UTC).replace(second=0, microsecond=0)
    rows: list[ResultImportRow] = []
    for index in range(32):
        home_index = index % len(DEMO_TEAMS)
        away_index = (index * 3 + 1) % len(DEMO_TEAMS)
        kickoff = anchor - timedelta(days=110 - index * 3)
        settled_at = kickoff + timedelta(hours=2)
        observed_at = settled_at + timedelta(hours=1)
        rows.append(
            ResultImportRow(
                provider_event_key=f"demo-history-{anchor:%Y%m%d}-{index + 1}",
                competition="Synthetic Premier Division",
                country="Demo Republic",
                season=f"{anchor.year}/{anchor.year + 1}",
                kickoff_at=kickoff,
                home_team=DEMO_TEAMS[home_index],
                away_team=DEMO_TEAMS[away_index],
                home_goals=(index * 2 + home_index) % 4,
                away_goals=(index + away_index) % 3,
                settled_at=settled_at,
                observed_at=observed_at,
                source_updated_at=observed_at,
            )
        )
    return serialize_result_rows_csv(rows)


def seed_demo_data(
    session: Session,
    *,
    as_of: datetime | None = None,
    ingested_at: datetime | None = None,
) -> ImportSummary:
    anchor = as_of or datetime.now(UTC)
    return import_odds_csv(
        session,
        filename=f"DEMO_odds_{anchor.astimezone(UTC):%Y%m%d_%H%M}.csv",
        content=build_demo_odds_csv(anchor),
        provider_slug="demo-seed-v1",
        provider_name="OddsQuant synthetic demonstration provider",
        is_demo=True,
        now=ingested_at or datetime.now(UTC),
    )


def seed_demo_results(
    session: Session,
    *,
    as_of: datetime | None = None,
    ingested_at: datetime | None = None,
) -> ResultImportSummary:
    anchor = as_of or datetime.now(UTC)
    return import_results_csv(
        session,
        filename=f"DEMO_results_{anchor.astimezone(UTC):%Y%m%d_%H%M}.csv",
        content=build_demo_results_csv(anchor),
        provider_slug="demo-results-v1",
        provider_name="OddsQuant synthetic historical results provider",
        is_demo=True,
        now=ingested_at or datetime.now(UTC),
    )
