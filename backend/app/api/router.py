from fastapi import APIRouter

from app.api.routes.catalog import router as catalog_router
from app.api.routes.imports import router as imports_router
from app.api.routes.models import router as models_router

router = APIRouter(prefix="/api/v1")
router.include_router(catalog_router)
router.include_router(imports_router)
router.include_router(models_router)


@router.get("/status", tags=["system"])
def project_status() -> dict[str, object]:
    return {
        "phase": "model_baseline",
        "sports": ["football"],
        "data_mode": "demo_or_user_supplied",
        "automated_betting": False,
    }
