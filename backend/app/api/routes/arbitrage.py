from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin_key
from app.db.session import get_db
from app.schemas.arbitrage import (
    ArbitrageBatchView,
    ArbitrageOpportunityView,
    ArbitrageSettingsView,
    BookmakerConstraintView,
    CalculateArbitrageRequest,
    CreateBookmakerConstraintRequest,
    CreateTaxProfileRequest,
    TaxProfileView,
)
from app.services.arbitrage import (
    ArbitrageDiscoveryError,
    calculate_arbitrage,
    list_arbitrage_opportunities,
)
from app.services.arbitrage_settings import (
    ArbitrageSettingsError,
    create_bookmaker_constraint,
    create_tax_profile,
    list_arbitrage_settings,
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


@router.get("/arbitrage/settings", response_model=ArbitrageSettingsView, tags=["arbitrage"])
def settings(database: Database) -> ArbitrageSettingsView:
    return list_arbitrage_settings(database)


@router.post(
    "/arbitrage/settings/tax-profiles",
    response_model=TaxProfileView,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin_key)],
    tags=["arbitrage"],
)
def add_tax_profile(request: CreateTaxProfileRequest, database: Database) -> TaxProfileView:
    try:
        return create_tax_profile(database, request)
    except ArbitrageSettingsError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/arbitrage/settings/constraints",
    response_model=BookmakerConstraintView,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin_key)],
    tags=["arbitrage"],
)
def add_constraint(
    request: CreateBookmakerConstraintRequest, database: Database
) -> BookmakerConstraintView:
    try:
        return create_bookmaker_constraint(database, request)
    except ArbitrageSettingsError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
