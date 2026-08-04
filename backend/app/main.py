from __future__ import annotations

import json
import logging
import re
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.router import router
from app.core.config import get_settings
from app.db.session import SessionLocal

settings = get_settings()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Educational sports-odds analytics. No prediction guarantees profit.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Admin-Key", "X-Request-ID"],
)
app.include_router(router)


@app.middleware("http")
async def request_context(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    supplied_request_id = request.headers.get("X-Request-ID", "")
    request_id = (
        supplied_request_id
        if re.fullmatch(r"[A-Za-z0-9._-]{1,80}", supplied_request_id)
        else str(uuid.uuid4())
    )
    started_at = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        route = getattr(request.scope.get("route"), "path", "unmatched")
        logging.getLogger("oddsquant.api").exception(
            json.dumps(
                {
                    "event": "http_request",
                    "request_id": request_id,
                    "method": request.method,
                    "route": route,
                    "status": 500,
                    "status_class": "5xx",
                    "duration_ms": duration_ms,
                    "slow": duration_ms >= settings.slow_request_ms,
                },
                separators=(",", ":"),
            )
        )
        return JSONResponse(
            status_code=500,
            content={
                "type": "about:blank",
                "title": "Internal server error",
                "status": 500,
                "request_id": request_id,
            },
            headers={"X-Request-ID": request_id},
        )
    duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
    route = getattr(request.scope.get("route"), "path", "unmatched")
    logging.getLogger("oddsquant.api").info(
        json.dumps(
            {
                "event": "http_request",
                "request_id": request_id,
                "method": request.method,
                "route": route,
                "status": response.status_code,
                "status_class": f"{response.status_code // 100}xx",
                "duration_ms": duration_ms,
                "slow": duration_ms >= settings.slow_request_ms,
            },
            separators=(",", ":"),
        )
    )
    response.headers["X-Request-ID"] = request_id
    response.headers["Server-Timing"] = f"app;dur={duration_ms}"
    return response


@app.get("/health", tags=["system"])
def health() -> dict[str, object]:
    database = "ready"
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
    except Exception:
        database = "unavailable"
    return {
        "status": "ok" if database == "ready" else "degraded",
        "database": database,
        "environment": settings.environment,
    }
