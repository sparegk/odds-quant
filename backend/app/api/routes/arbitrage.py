from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin_key
from app.db.session import get_db
from app.schemas.arbitrage import (
    ArbitrageBatchView,
    ArbitrageOpportunityView,
    CalculateArbitrageRequest,
)
from app.services.arbitrage import (
    ArbitrageDiscoveryError,
    calculate_arbitrage,
    list_arbitrage_opportunities,
)

router = APIRouter()
Database = Annotated[Session, Depends(get_db)]


@router.post(
    "/arbitrage/calculate",
    response_model=ArbitrageBatchView,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin_key)],
    tags=["arbitrage"],
)
def calculate(request: CalculateArbitrageRequest, database: Database) -> ArbitrageBatchView:
    try:
        return calculate_arbitrage(database, request)
    except ArbitrageDiscoveryError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@router.get(
    "/arbitrage/opportunities",
    response_model=list[ArbitrageOpportunityView],
    tags=["arbitrage"],
)
def opportunities(
    database: Database,
    event_id: Annotated[int | None, Query(gt=0)] = None,
) -> list[ArbitrageOpportunityView]:
    return list_arbitrage_opportunities(database, event_id=event_id)
