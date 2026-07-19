# Architecture

OddsQuant uses a React/Vite client and a versioned FastAPI API. SQLAlchemy provides a common persistence layer for SQLite development and PostgreSQL production. Alembic migrations, a separate APScheduler worker, and Docker Compose will be completed before Phase 1 is considered runnable.

The predictive data flow is: provider adapter -> normalized ingestion DTO -> immutable raw snapshot -> timestamped football and odds tables -> point-in-time feature snapshot -> leakage-safe model version -> selection predictions -> explainable signals -> immutable backtest evaluation -> API response.

The planned football schema extends the existing foundation with players, coaches, registrations, player appearances, player statistics, availability reports, lineup snapshots and members, formations, tactical snapshots, and matchup feature snapshots. Every mutable fact is append-only or versioned with source, observation, ingestion, effective, and supersession timestamps. Expected and confirmed lineups are separate evidence classes.

Feature generation joins only records whose evidence timestamp precedes the prediction cutoff. Team, player, coach, and tactical feature families remain separable so ablation tests can measure incremental calibration and detect double counting. Expected-lineup scenarios and confirmed-lineup reruns create distinct prediction records rather than overwriting each other.

The arbitrage path branches after normalized odds storage. It groups only compatible snapshots by canonical event, market, line, period, currency, and settlement rules; selects the best fresh price for each exhaustive outcome; applies explicit per-leg tax and fee profiles; optimizes rounded stakes for worst-case net payout; and returns ranked `THEORETICAL_ARBITRAGE` results. Unknown taxes, stale prices, incompatible rules, overlapping selections, or non-positive worst-case net profit prevent an executable classification.

Core quantitative functions remain independent of FastAPI and SQLAlchemy so formulas can be unit-tested and reused by collection jobs, API requests, and backtests.
