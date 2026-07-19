from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin_key
from app.db.session import get_db
from app.schemas.models import (
    EvaluateModelRequest,
    EvaluationRunView,
    ModelOutputView,
    ModelVersionView,
    PredictEventRequest,
    TrainPoissonRequest,
)
from app.services.catalog import get_event
from app.services.evaluation import (
    EvaluationError,
    evaluate_model,
    get_evaluation,
    list_evaluations,
)
from app.services.modeling import (
    ModelingError,
    get_model,
    list_event_predictions,
    list_models,
    predict_event,
    train_poisson_model,
)

router = APIRouter()
Database = Annotated[Session, Depends(get_db)]


@router.get("/models", response_model=list[ModelVersionView], tags=["models"])
def models(database: Database) -> list[ModelVersionView]:
    return list_models(database)


@router.post(
    "/models/train",
    response_model=ModelVersionView,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin_key)],
    tags=["models"],
)
def train_model(request: TrainPoissonRequest, database: Database) -> ModelVersionView:
    try:
        return train_poisson_model(database, request)
    except ModelingError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get("/models/{model_id}", response_model=ModelVersionView, tags=["models"])
def model_detail(model_id: int, database: Database) -> ModelVersionView:
    model = get_model(database, model_id)
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")
    return model


@router.post(
    "/models/{model_id}/evaluate",
    response_model=EvaluationRunView,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin_key)],
    tags=["models"],
)
def create_evaluation(
    model_id: int,
    request: EvaluateModelRequest,
    database: Database,
) -> EvaluationRunView:
    try:
        return evaluate_model(database, model_id, request)
    except EvaluationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get("/evaluations", response_model=list[EvaluationRunView], tags=["models"])
def evaluations(database: Database, model_id: int | None = None) -> list[EvaluationRunView]:
    return list_evaluations(database, model_id=model_id)


@router.get(
    "/evaluations/{run_id}",
    response_model=EvaluationRunView,
    tags=["models"],
)
def evaluation_detail(run_id: int, database: Database) -> EvaluationRunView:
    run = get_evaluation(database, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation not found")
    return run


@router.post(
    "/models/{model_id}/predict",
    response_model=ModelOutputView,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin_key)],
    tags=["models"],
)
def create_prediction(
    model_id: int,
    request: PredictEventRequest,
    database: Database,
) -> ModelOutputView:
    try:
        return predict_event(database, model_id, request)
    except ModelingError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get(
    "/events/{event_id}/predictions",
    response_model=list[ModelOutputView],
    tags=["models"],
)
def event_predictions(event_id: int, database: Database) -> list[ModelOutputView]:
    if get_event(database, event_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return list_event_predictions(database, event_id)
