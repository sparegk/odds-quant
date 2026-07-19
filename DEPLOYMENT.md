# Deployment

OddsQuant is configured as a four-service system: React dashboard, FastAPI backend, PostgreSQL database, and separate APScheduler worker. These files have been verified locally where noted; no live deployment is claimed.

## Docker Compose

Requirements: Docker Engine with Compose v2. From the repository root:

```bash
docker compose up --build
```

The API applies Alembic migrations, starts at `http://localhost:8000`, and exposes OpenAPI at `http://localhost:8000/docs`. The worker then loads clearly labelled demo data in development and polls the process-local provider registry. The frontend is served at `http://localhost:5173`. No external provider is registered by default and no protected bookmaker endpoint is scraped.

Local Compose defaults are development credentials only. Override them in an uncommitted `.env`:

```text
POSTGRES_DB=oddsquant
POSTGRES_USER=oddsquant
POSTGRES_PASSWORD=replace-with-a-random-local-password
ODDSQUANT_ADMIN_API_KEY=replace-with-a-random-import-key
ODDSQUANT_CORS_ORIGINS=http://localhost:5173
```

Stop services with `docker compose down`. Adding `--volumes` deletes the local PostgreSQL volume and all imported data, so use it only intentionally.

## SQLite Development

SQLite does not need Docker:

```bash
cd backend
python -m pip install -e ".[dev]"
python -m alembic upgrade head
python -m app.cli seed-demo
python -m app.cli seed-demo-results
python -m uvicorn app.main:app --reload
```

The two seed commands are separate and explicitly synthetic. Use `import-results`, `train-poisson`, and `predict-event` for the local model workflow; production disables scheduled demo seeding and should ingest only authorized, timestamped sources.

Run the scheduler separately with `python -m app.jobs.scheduler`. Production never seeds demo data, even if `ODDSQUANT_SEED_DEMO` is accidentally true.

Run the frontend separately with `npm ci` and `npm run dev` from `frontend`. Its public API origin is injected through `VITE_API_BASE_URL` at development or build time.

## Render Blueprint

`render.yaml` defines a static frontend, Docker API service, paid background worker, paid PostgreSQL instance, migrations through `preDeployCommand`, generated import key, and frontend/API origins that must be supplied during Blueprint creation. Review current Render pricing before applying the Blueprint; the file deliberately avoids pretending a free worker is available.

1. Connect `sparegk/odds-quant` to Render and create a Blueprint from `render.yaml`.
2. Set the frontend `VITE_API_BASE_URL` to the deployed API origin.
3. Set API `ODDSQUANT_CORS_ORIGINS` to the exact deployed frontend origin. Do not use `*` with privileged import routes.
4. Retain the generated `ODDSQUANT_ADMIN_API_KEY` as a secret and provide it only to trusted import clients through `X-Admin-Key`.
5. Confirm `/health` reports `status=ok` and `database=ready`, then load the dashboard.
6. Review migration and worker logs before enabling any licensed provider adapter.

Render's current Blueprint schema documents `runtime: docker`, `dockerCommand`, `preDeployCommand`, worker services, database references, and `checksPass` deploy triggers: <https://render.com/docs/blueprint-spec>.

## Production Controls

- Use PostgreSQL and a unique administrative API key.
- Restrict CORS to known HTTPS frontend origins.
- Keep `ODDSQUANT_ENVIRONMENT=production` and `ODDSQUANT_SEED_DEMO=false`.
- Store licensed-provider credentials only in the platform secret manager.
- Run one migration operation before rolling out API/worker code.
- Back up PostgreSQL and rehearse restore procedures before ingesting valuable history.
- Monitor provider rate limits, collection failures, odds freshness, and database growth.
- Do not register a provider without documented authorization and terms review.

The GitHub Actions workflow checks backend and frontend linting, formatting/type safety, tests, production builds, Alembic lifecycle, and both container images. Python checks follow GitHub's current setup guidance: <https://docs.github.com/en/actions/tutorials/build-and-test-code/python>.
