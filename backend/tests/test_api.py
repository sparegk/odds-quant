import logging

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] in {"ok", "degraded"}
    assert response.headers["X-Request-ID"]


def test_versioned_status_is_responsible() -> None:
    response = client.get("/api/v1/status")
    assert response.status_code == 200
    assert response.json()["automated_betting"] is False


def test_request_observability_uses_route_templates_without_sensitive_values(caplog) -> None:
    caplog.set_level(logging.INFO, logger="oddsquant.api")
    response = client.get(
        "/api/v1/status?note=private-value",
        headers={"X-Admin-Key": "private-key", "X-Request-ID": "acceptance-123"},
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "acceptance-123"
    assert response.headers["Server-Timing"].startswith("app;dur=")
    message = next(
        record.message for record in caplog.records if '"event":"http_request"' in record.message
    )
    assert '"route":"/api/v1/status"' in message
    assert "private-value" not in message
    assert "private-key" not in message


def test_client_telemetry_contract_rejects_content_fields() -> None:
    accepted = client.post(
        "/api/v1/client-events",
        json={
            "event": "api_failure",
            "route": "/matches/:id",
            "error_type": "HttpError",
            "status": 503,
            "duration_ms": 12.4,
        },
    )
    rejected = client.post(
        "/api/v1/client-events",
        json={
            "event": "frontend_error",
            "route": "/research/workspace",
            "error_type": "TypeError",
            "message": "private note",
        },
    )

    assert accepted.status_code == 204
    assert rejected.status_code == 422
