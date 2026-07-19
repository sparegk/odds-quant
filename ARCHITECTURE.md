# Architecture

OddsQuant uses a React/Vite client and a versioned FastAPI API. SQLAlchemy provides a common persistence layer for SQLite development and PostgreSQL production. Alembic migrations, a separate APScheduler worker, and Docker Compose will be completed before Phase 1 is considered runnable.

The data flow is: provider adapter -> normalized ingestion DTO -> timestamped event/market/odds tables -> leakage-safe model version -> selection predictions -> explainable signals -> immutable backtest evaluation -> API response.

Core quantitative functions remain independent of FastAPI and SQLAlchemy so formulas can be unit-tested and reused by collection jobs, API requests, and backtests.

