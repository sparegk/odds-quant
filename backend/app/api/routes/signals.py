from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin_key
from app.db.session import get_db
from app.schemas.signals import GenerateSignalsRequest, SignalBatchView, ValueSignalView
from app.services.signals import (
    SignalGenerationError,
    generate_value_signals,
    list_underdog_signals,
    list_value_signals,
)

router = APIRouter()
Database = Annotated[Session, Depends(get_db)]


@router.post(
    "/signals/generate",
    response_model=SignalBatchView,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin_key)],
    tags=["signals"],
)
def generate_signals(request: GenerateSignalsRequest, database: Database) -> SignalBatchView:
    try:
        return generate_value_signals(database, request)
    except SignalGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@router.get("/signals", response_model=list[ValueSignalView], tags=["signals"])
def signals(
    database: Database,
    event_id: int | None = None,
    output_id: int | None = None,
    signal_type: str | None = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> list[ValueSignalView]:
    return list_value_signals(
        database,
        event_id=event_id,
        output_id=output_id,
        signal_type=signal_type,
        limit=limit,
    )


@router.get(
    "/recommendations",
    response_model=list[ValueSignalView],
    tags=["recommendations"],
)
def recommendations(
    database: Database,
    event_id: int | None = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> list[ValueSignalView]:
    """Return immutable VALUE decisions, independent of whether the user placed them."""
    return list_value_signals(
        database,
        event_id=event_id,
        signal_type="VALUE",
        limit=limit,
    )


@router.get(
    "/signals/underdogs",
    response_model=list[ValueSignalView],
    tags=["signals"],
)
def underdog_signals(
    database: Database,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[ValueSignalView]:
    return list_underdog_signals(database, limit=limit)
