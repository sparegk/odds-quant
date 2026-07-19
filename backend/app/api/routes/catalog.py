from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.api import (
    EventDetail,
    EventSummary,
    MarketComparison,
    ProviderJobView,
    ProviderSummary,
)
from app.services.catalog import (
    get_event,
    list_events,
    list_provider_jobs,
    list_providers,
    odds_comparison,
)

router = APIRouter()
Database = Annotated[Session, Depends(get_db)]


@router.get("/events", response_model=list[EventSummary], tags=["events"])
def events(
    database: Database,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    include_past: bool = False,
) -> list[EventSummary]:
    return list_events(database, offset=offset, limit=limit, include_past=include_past)


@router.get("/events/{event_id}", response_model=EventDetail, tags=["events"])
def event_detail(event_id: int, database: Database) -> EventDetail:
    event = get_event(database, event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    settings = get_settings()
    return EventDetail(
        event=event,
        markets=odds_comparison(
            database,
            event_id=event_id,
            stale_after_seconds=settings.odds_stale_after_seconds,
        ),
    )


@router.get("/providers", response_model=list[ProviderSummary], tags=["data"])
def providers(database: Database) -> list[ProviderSummary]:
    return list_providers(database)


@router.get("/jobs", response_model=list[ProviderJobView], tags=["data"])
def jobs(
    database: Database,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[ProviderJobView]:
    return list_provider_jobs(database, limit=limit)


@router.get(
    "/odds/comparison",
    response_model=list[MarketComparison],
    tags=["odds"],
)
def comparison(
    event_id: int,
    database: Database,
    as_of: datetime | None = None,
) -> list[MarketComparison]:
    if get_event(database, event_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    if as_of is not None and (as_of.tzinfo is None or as_of.utcoffset() is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="as_of must include a UTC offset",
        )
    if as_of is not None and as_of.astimezone(UTC) > datetime.now(UTC):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="as_of cannot be in the future",
        )
    return odds_comparison(
        database,
        event_id=event_id,
        as_of=as_of,
        stale_after_seconds=get_settings().odds_stale_after_seconds,
    )
