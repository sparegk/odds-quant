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
