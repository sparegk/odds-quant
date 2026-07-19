# Architecture

OddsQuant uses a React/Vite/Tailwind dashboard and a versioned FastAPI API. SQLAlchemy provides a common persistence layer for SQLite development and PostgreSQL production. Alembic owns schema changes; Docker Compose runs PostgreSQL, the API, a separate APScheduler worker, and the frontend.

The frontend consumes only versioned API responses through a typed client. It displays stored market comparisons, data operations, and the model registry. Value-dependent pages remain blocked until chronological evaluation records exist. Static frontend deployment injects the public API origin at build time through `VITE_API_BASE_URL`.

External adapters register through the process-local collector registry. The worker converts their validated normalized DTOs into the same atomic import path used by CSV uploads and records each scheduled attempt in `provider_jobs`. No external adapter is enabled by default. Development may seed labelled synthetic odds; production blocks demo seeding.

The predictive data flow is: permitted source or user CSV -> normalized ingestion DTO -> immutable raw snapshot -> timestamped result and odds tables -> cutoff-filtered training rows -> fingerprinted Poisson model version -> pre-kickoff score matrix and selection predictions. Explainable signals and immutable walk-forward evaluation are the next layer and are not inferred from training-descriptive metrics.

The planned football schema extends the existing foundation with players, coaches, registrations, player appearances, player statistics, availability reports, lineup snapshots and members, formations, tactical snapshots, and matchup feature snapshots. Every mutable fact is append-only or versioned with source, observation, ingestion, effective, and supersession timestamps. Expected and confirmed lineups are separate evidence classes.

Feature generation joins only records whose evidence timestamp precedes the prediction cutoff. Team, player, coach, and tactical feature families remain separable so ablation tests can measure incremental calibration and detect double counting. Expected-lineup scenarios and confirmed-lineup reruns create distinct prediction records rather than overwriting each other.

The arbitrage path branches after normalized odds storage. It groups only compatible snapshots by canonical event, market, line, period, currency, and settlement rules; selects the best fresh price for each exhaustive outcome; applies explicit per-leg tax and fee profiles; optimizes rounded stakes for worst-case net payout; and returns ranked `THEORETICAL_ARBITRAGE` results. Unknown taxes, stale prices, incompatible rules, overlapping selections, or non-positive worst-case net profit prevent an executable classification.

Core quantitative functions remain independent of FastAPI and SQLAlchemy so formulas can be unit-tested and reused by collection jobs, API requests, and backtests.
