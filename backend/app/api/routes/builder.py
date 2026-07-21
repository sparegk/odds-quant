from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin_key
from app.db.session import get_db
from app.schemas.builder import BetBuilderQuoteView, CreateBetBuilderQuoteRequest
from app.services.builder import (
    BetBuilderError,
    create_bet_builder_quote,
    list_bet_builder_quotes,
)

router = APIRouter()
Database = Annotated[Session, Depends(get_db)]


@router.post(
    "/bet-builder/quotes",
    response_model=BetBuilderQuoteView,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin_key)],
    tags=["bet-builder"],
)
def create_quote(request: CreateBetBuilderQuoteRequest, database: Database) -> BetBuilderQuoteView:
    try:
        return create_bet_builder_quote(database, request)
    except BetBuilderError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@router.get(
    "/bet-builder/quotes",
    response_model=list[BetBuilderQuoteView],
    tags=["bet-builder"],
)
def quotes(
    database: Database,
    event_id: Annotated[int | None, Query(gt=0)] = None,
) -> list[BetBuilderQuoteView]:
    return list_bet_builder_quotes(database, event_id=event_id)
