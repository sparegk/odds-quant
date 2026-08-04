import json
import logging

from fastapi import APIRouter, Response, status

from app.schemas.telemetry import ClientTelemetryEvent

router = APIRouter(tags=["system"])
logger = logging.getLogger("oddsquant.frontend")


@router.post("/client-events", status_code=status.HTTP_204_NO_CONTENT)
def client_event(event: ClientTelemetryEvent) -> Response:
    logger.warning(
        json.dumps(
            {"event": "client_telemetry", **event.model_dump(exclude_none=True)},
            separators=(",", ":"),
        )
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
