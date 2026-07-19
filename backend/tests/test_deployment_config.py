from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def _yaml(path: str) -> dict[str, object]:
    parsed = yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))
    assert isinstance(parsed, dict)
    return parsed


def test_compose_orders_database_api_and_worker() -> None:
    compose = _yaml("docker-compose.yml")
    services = compose["services"]
    assert isinstance(services, dict)
    database = services["db"]
    api = services["api"]
    worker = services["worker"]
    assert database["image"] == "postgres:17-alpine"
    assert api["depends_on"]["db"]["condition"] == "service_healthy"
    assert worker["depends_on"]["api"]["condition"] == "service_healthy"
    assert "alembic upgrade head" in api["command"]
    assert worker["environment"]["ODDSQUANT_SEED_DEMO"] == "true"


def test_render_is_production_safe_and_migrates_before_deploy() -> None:
    blueprint = _yaml("render.yaml")
    services = blueprint["services"]
    assert isinstance(services, list)
    web = next(service for service in services if service["type"] == "web")
    worker = next(service for service in services if service["type"] == "worker")
    assert web["preDeployCommand"] == "python -m alembic upgrade head"
    assert web["autoDeployTrigger"] == "checksPass"
    web_environment = {item["key"]: item for item in web["envVars"]}
    worker_environment = {item["key"]: item for item in worker["envVars"]}
    assert web_environment["ODDSQUANT_ENVIRONMENT"]["value"] == "production"
    assert web_environment["ODDSQUANT_SEED_DEMO"]["value"] == "false"
    assert web_environment["ODDSQUANT_ADMIN_API_KEY"]["generateValue"] is True
    assert worker_environment["ODDSQUANT_SEED_DEMO"]["value"] == "false"


def test_backend_image_runs_as_non_root_without_embedded_secrets() -> None:
    dockerfile = (ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")
    assert dockerfile.startswith("FROM python:3.12-slim")
    assert "USER oddsquant" in dockerfile
    assert dockerfile.index("USER oddsquant") < dockerfile.index("CMD [")
    assert "ADMIN_API_KEY" not in dockerfile
    assert "PASSWORD=" not in dockerfile


def test_ci_checks_migrations_and_builds_backend_image() -> None:
    _yaml(".github/workflows/ci.yml")
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "actions/checkout@v6" in workflow
    assert "python -m alembic check" in workflow
    assert "python -m pytest -q" in workflow
    assert "docker build --tag oddsquant-api:ci backend" in workflow
