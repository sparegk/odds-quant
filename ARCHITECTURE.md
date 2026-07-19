# Architecture

OddsQuant uses a React/Vite client and a versioned FastAPI API. SQLAlchemy provides a common persistence layer for SQLite development and PostgreSQL production. Alembic migrations, a separate APScheduler worker, and Docker Compose will be completed before Phase 1 is considered runnable.

The predictive data flow is: provider adapter -> normalized ingestion DTO -> timestamped event/market/odds tables -> leakage-safe model version -> selection predictions -> explainable signals -> immutable backtest evaluation -> API response.

The arbitrage path branches after normalized odds storage. It groups only compatible snapshots by canonical event, market, line, period, currency, and settlement rules; selects the best fresh price for each exhaustive outcome; applies explicit per-leg tax and fee profiles; optimizes rounded stakes for worst-case net payout; and returns ranked `THEORETICAL_ARBITRAGE` results. Unknown taxes, stale prices, incompatible rules, overlapping selections, or non-positive worst-case net profit prevent an executable classification.

Core quantitative functions remain independent of FastAPI and SQLAlchemy so formulas can be unit-tested and reused by collection jobs, API requests, and backtests.
