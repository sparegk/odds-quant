from fastapi import APIRouter

from app.api.routes.arbitrage import router as arbitrage_router
from app.api.routes.backtesting import router as backtesting_router
from app.api.routes.builder import router as builder_router
from app.api.routes.catalog import router as catalog_router
from app.api.routes.imports import router as imports_router
from app.api.routes.matchday import router as matchday_router
from app.api.routes.models import router as models_router
from app.api.routes.signals import router as signals_router

router = APIRouter(prefix="/api/v1")
router.include_router(catalog_router)
router.include_router(arbitrage_router)
router.include_router(builder_router)
router.include_router(backtesting_router)
router.include_router(imports_router)
router.include_router(matchday_router)
router.include_router(models_router)
router.include_router(signals_router)


@router.get("/status", tags=["system"])
def project_status() -> dict[str, object]:
    return {
        "phase": "model_baseline",
        "sports": ["football"],
        "data_mode": "demo_or_user_supplied",
        "automated_betting": False,
    }
