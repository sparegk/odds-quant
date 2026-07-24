from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.matchday import MatchdayEventDetailView, MatchdayView
from app.services.matchday import MatchdayError, get_matchday_event_detail, list_matchday

router = APIRouter()
Database = Annotated[Session, Depends(get_db)]


def _validate_as_of(as_of: datetime | None) -> None:
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


@router.get("/matchdays", response_model=MatchdayView, tags=["matchday"])
def matchday(
    database: Database,
    match_date: Annotated[date | None, Query(alias="date")] = None,
    timezone: str | None = None,
    as_of: datetime | None = None,
) -> MatchdayView:
    _validate_as_of(as_of)
    settings = get_settings()
    try:
        return list_matchday(
            database,
            match_date=match_date,
            timezone_name=timezone or settings.matchday_timezone,
            as_of=as_of,
        )
    except MatchdayError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@router.get(
    "/matchdays/events/{event_id}",
    response_model=MatchdayEventDetailView,
    tags=["matchday"],
)
def matchday_event(
    event_id: int,
    database: Database,
    as_of: datetime | None = None,
    bookmakers: Annotated[
        list[Literal["allwyn", "novibet"]] | None,
        Query(),
    ] = None,
) -> MatchdayEventDetailView:
    _validate_as_of(as_of)
    settings = get_settings()
    detail = get_matchday_event_detail(
        database,
        event_id=event_id,
        as_of=as_of,
        stale_after_seconds=settings.odds_stale_after_seconds,
        form_matches=settings.matchday_form_matches,
        selected_bookmakers=set(bookmakers or ("allwyn", "novibet")),
    )
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return detail
