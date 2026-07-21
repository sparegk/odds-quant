from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin_key
from app.db.session import get_db
from app.schemas.backtesting import (
    BankrollSimulationView,
    RunSignalBacktestRequest,
    SignalBacktestView,
    SimulateBankrollRequest,
)
from app.services.backtesting import (
    BacktestingError,
    get_signal_backtest,
    list_signal_backtests,
    run_signal_backtest,
    simulate_backtest_bankroll,
)

router = APIRouter()
Database = Annotated[Session, Depends(get_db)]


@router.post(
    "/backtests/signals",
    response_model=SignalBacktestView,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin_key)],
    tags=["backtesting"],
)
def create_signal_backtest(
    request: RunSignalBacktestRequest, database: Database
) -> SignalBacktestView:
    try:
        return run_signal_backtest(database, request)
    except BacktestingError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/backtests", response_model=list[SignalBacktestView], tags=["backtesting"])
def backtests(database: Database, model_id: int | None = None) -> list[SignalBacktestView]:
    return list_signal_backtests(database, model_id=model_id)


@router.get("/backtests/{run_id}", response_model=SignalBacktestView, tags=["backtesting"])
def backtest_detail(run_id: int, database: Database) -> SignalBacktestView:
    run = get_signal_backtest(database, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Signal backtest not found")
    return run


@router.post(
    "/bankroll/simulate",
    response_model=BankrollSimulationView,
    tags=["bankroll"],
)
def simulate_bankroll(
    request: SimulateBankrollRequest, database: Database
) -> BankrollSimulationView:
    try:
        return simulate_backtest_bankroll(database, request)
    except BacktestingError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
