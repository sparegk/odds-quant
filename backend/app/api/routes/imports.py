from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin_key
from app.db.session import get_db
from app.schemas.api import ImportJobView, ProblemDetail
from app.schemas.intelligence import IntelligenceImportRequest, IntelligenceImportSummary
from app.schemas.odds import ImportSummary
from app.schemas.results import ResultImportSummary
from app.services.catalog import get_import_job, list_import_jobs
from app.services.intelligence_import import (
    MAX_INTELLIGENCE_CSV_BYTES,
    IntelligenceImportError,
    import_availability_csv,
    import_intelligence_bundle,
)
from app.services.odds_import import MAX_CSV_BYTES, OddsImportError, import_odds_csv
from app.services.results_import import (
    MAX_RESULTS_CSV_BYTES,
    ResultImportError,
    import_results_csv,
)

router = APIRouter()
Database = Annotated[Session, Depends(get_db)]


def _intelligence_problem(exc: IntelligenceImportError) -> HTTPException:
    problem = ProblemDetail(
        title="Football intelligence import rejected",
        status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="No player, lineup, availability, coach, or tactical records were imported",
        errors=exc.errors,
        import_job_id=exc.job_id,
    )
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=problem.model_dump(mode="json"),
    )


@router.post(
    "/imports/intelligence",
    response_model=IntelligenceImportSummary,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin_key)],
    tags=["data"],
)
def import_intelligence(
    request: IntelligenceImportRequest, database: Database
) -> IntelligenceImportSummary:
    try:
        return import_intelligence_bundle(database, request)
    except IntelligenceImportError as exc:
        raise _intelligence_problem(exc) from exc


@router.post(
    "/imports/intelligence/availability",
    response_model=IntelligenceImportSummary,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin_key)],
    tags=["data"],
)
async def upload_availability(
    file: Annotated[UploadFile, File()],
    database: Database,
    source_key: Annotated[str, Form(min_length=1, max_length=255)],
    provider_slug: Annotated[str, Form(min_length=1, max_length=60)],
    provider_name: Annotated[str, Form(min_length=1, max_length=120)],
) -> IntelligenceImportSummary:
    filename = file.filename or "availability.csv"
    if not filename.casefold().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Availability imports must use a .csv file",
        )
    content = await file.read(MAX_INTELLIGENCE_CSV_BYTES + 1)
    await file.close()
    try:
        return import_availability_csv(
            database,
            filename=filename,
            content=content,
            source_key=source_key,
            provider_slug=provider_slug,
            provider_name=provider_name,
        )
    except IntelligenceImportError as exc:
        raise _intelligence_problem(exc) from exc


@router.post(
    "/imports/odds",
    response_model=ImportSummary,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin_key)],
    tags=["data"],
)
async def upload_odds(file: Annotated[UploadFile, File()], database: Database) -> ImportSummary:
    filename = file.filename or "odds.csv"
    if not filename.casefold().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Odds imports must use a .csv file",
        )
    content = await file.read(MAX_CSV_BYTES + 1)
    await file.close()
    try:
        return import_odds_csv(database, filename=filename, content=content)
    except OddsImportError as exc:
        problem = ProblemDetail(
            title="Odds import rejected",
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No football or odds rows from this file were imported",
            errors=exc.errors,
            import_job_id=exc.job_id,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=problem.model_dump(mode="json"),
        ) from exc


@router.post(
    "/imports/results",
    response_model=ResultImportSummary,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin_key)],
    tags=["data"],
)
async def upload_results(
    file: Annotated[UploadFile, File()], database: Database
) -> ResultImportSummary:
    filename = file.filename or "results.csv"
    if not filename.casefold().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Result imports must use a .csv file",
        )
    content = await file.read(MAX_RESULTS_CSV_BYTES + 1)
    await file.close()
    try:
        return import_results_csv(database, filename=filename, content=content)
    except ResultImportError as exc:
        problem = ProblemDetail(
            title="Result import rejected",
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No football result rows from this file were imported",
            errors=exc.errors,
            import_job_id=exc.job_id,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=problem.model_dump(mode="json"),
        ) from exc


@router.get("/imports", response_model=list[ImportJobView], tags=["data"])
def imports(
    database: Database,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[ImportJobView]:
    return list_import_jobs(database, limit=limit)


@router.get("/imports/{job_id}", response_model=ImportJobView, tags=["data"])
def import_detail(job_id: int, database: Database) -> ImportJobView:
    job = get_import_job(database, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import job not found")
    return job
