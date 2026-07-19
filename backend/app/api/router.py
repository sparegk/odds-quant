from fastapi import APIRouter

router = APIRouter(prefix="/api/v1")


@router.get("/status", tags=["system"])
def project_status() -> dict[str, object]:
    return {
        "phase": "foundation",
        "sports": ["football"],
        "data_mode": "demo_or_user_supplied",
        "automated_betting": False,
    }
