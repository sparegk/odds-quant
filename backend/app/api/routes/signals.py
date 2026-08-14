from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin_key
from app.db.session import get_db
from app.schemas.recommendations import (
    CaptureRecommendationRequest,
    RecommendationSnapshotView,
    RefreshRecommendationRequest,
)
from app.schemas.signals import (
    GenerateSignalsRequest,
    ResearchValueCandidateView,
    SignalBatchView,
    ValueSignalView,
)
from app.services.recommendation_tracking import (
    RecommendationTrackingError,
    capture_recommendation,
    list_recommendation_snapshots,
    refresh_recommendation,
)
from app.services.signals import (
    SignalGenerationError,
    generate_value_signals,
    list_research_value_candidates,
    list_underdog_signals,
    list_value_signals,
)

router = APIRouter()
Database = Annotated[Session, Depends(get_db)]


@router.get(
    "/signals/research-candidates",
    response_model=list[ResearchValueCandidateView],
    tags=["signals"],
)
def research_candidates(
    database: Database,
    as_of: datetime | None = None,
    horizon_hours: Annotated[int, Query(ge=1, le=720)] = 168,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> list[ResearchValueCandidateView]:
    return list_research_value_candidates(
        database,
        as_of=as_of,
        horizon_hours=horizon_hours,
        limit=limit,
    )


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


@router.post(
    "/recommendations/capture",
    response_model=RecommendationSnapshotView,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin_key)],
    tags=["recommendations"],
)
def capture_tracked_recommendation(
    request: CaptureRecommendationRequest, database: Database
) -> RecommendationSnapshotView:
    try:
        return capture_recommendation(
            database,
            signal_id=request.signal_id,
            captured_at=request.captured_at,
        )
    except RecommendationTrackingError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@router.get(
    "/recommendations/tracked",
    response_model=list[RecommendationSnapshotView],
    tags=["recommendations"],
)
def tracked_recommendations(
    database: Database,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> list[RecommendationSnapshotView]:
    return list_recommendation_snapshots(database, limit=limit)


@router.post(
    "/recommendations/{recommendation_id}/refresh",
    response_model=RecommendationSnapshotView,
    dependencies=[Depends(require_admin_key)],
    tags=["recommendations"],
)
def refresh_tracked_recommendation(
    recommendation_id: int,
    request: RefreshRecommendationRequest,
    database: Database,
) -> RecommendationSnapshotView:
    try:
        return refresh_recommendation(
            database,
            recommendation_id=recommendation_id,
            as_of=request.as_of,
        )
    except RecommendationTrackingError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


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
