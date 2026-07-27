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
    frontend = services["frontend"]
    assert database["image"] == "postgres:17-alpine"
    assert api["depends_on"]["db"]["condition"] == "service_healthy"
    assert worker["depends_on"]["api"]["condition"] == "service_healthy"
    assert "alembic upgrade head" in api["command"]
    assert api["environment"]["ODDSQUANT_MATCHDAY_TIMEZONE"] == (
        "${ODDSQUANT_MATCHDAY_TIMEZONE:-Europe/Athens}"
    )
    assert api["environment"]["ODDSQUANT_MATCHDAY_FORM_MATCHES"] == (
        "${ODDSQUANT_MATCHDAY_FORM_MATCHES:-5}"
    )
    assert worker["environment"]["ODDSQUANT_SEED_DEMO"] == "true"
    assert frontend["depends_on"]["api"]["condition"] == "service_healthy"
    assert frontend["ports"] == ["${ODDSQUANT_FRONTEND_PORT:-5173}:8080"]


def test_free_tunnel_starts_a_hardened_loopback_backend() -> None:
    script = (ROOT / "scripts" / "start-free-site-tunnel.ps1").read_text(encoding="utf-8")
    assert "python -m alembic upgrade head" not in script
    assert 'py -m alembic upgrade head' in script
    assert '$env:ODDSQUANT_ENVIRONMENT = "production"' in script
    assert '$env:ODDSQUANT_SEED_DEMO = "false"' in script
    assert '"--host", "127.0.0.1"' in script
    assert '"-m", "app.jobs.scheduler"' in script
    assert '"tunnel", "--url", $apiUrl' in script
    assert "ODDSQUANT_ODDS_API_IO_KEY=" not in script
    assert "ODDSQUANT_API_FOOTBALL_KEY=" not in script


def test_backend_image_runs_as_non_root_without_embedded_secrets() -> None:
    dockerfile = (ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")
    assert dockerfile.startswith("FROM python:3.12-slim")
    assert "USER oddsquant" in dockerfile
    assert dockerfile.index("USER oddsquant") < dockerfile.index("CMD [")
    assert "ADMIN_API_KEY" not in dockerfile
    assert "PASSWORD=" not in dockerfile

    frontend = (ROOT / "frontend" / "Dockerfile").read_text(encoding="utf-8")
    assert frontend.startswith("FROM node:24-alpine AS build")
    assert "nginxinc/nginx-unprivileged" in frontend
    assert "COPY --from=build /app/dist" in frontend


def test_ci_checks_migrations_and_builds_backend_image() -> None:
    _yaml(".github/workflows/ci.yml")
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "actions/checkout@v6" in workflow
    assert "python -m alembic check" in workflow
    assert "python -m pytest -q" in workflow
    assert "docker build --tag oddsquant-api:ci backend" in workflow
    assert "npm run test" in workflow
    assert "npm run build" in workflow
    assert "docker build --tag oddsquant-web:ci frontend" in workflow
