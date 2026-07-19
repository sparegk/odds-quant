# AGENTS.md

## Structure

- `backend/app/api`: versioned FastAPI routes.
- `backend/app/db`: SQLAlchemy models and sessions.
- `backend/app/providers`: legal data-source adapters.
- `backend/app/schemas`: strict ingestion and API data contracts.
- `backend/app/services`: transactional imports and application workflows.
- `backend/app/quant`: pure probability and settlement logic.
- `backend/app/signals`: explainable signal policy.
- `backend/tests`: deterministic backend tests.

## Commands

From `backend`:

```bash
python -m pip install -e ".[dev]"
python -m alembic upgrade head
python -m app.cli seed-demo
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy app tests
python -m uvicorn app.main:app --reload
```

Import user-supplied odds with `python -m app.cli import-odds path/to/odds.csv`. CSV
imports are atomic: never weaken completeness, timestamp, identity, or market-settlement
validation to accept a partial feed.

Multipart imports use `POST /api/v1/imports/odds`. Local development may omit an admin
key; production must set `ODDSQUANT_ADMIN_API_KEY` and send `X-Admin-Key`.

## Non-Negotiable Rules

- Use only information available before an event kickoff; tests must reject look-ahead leakage.
- Historical player availability, expected/confirmed lineups, injuries, coach decisions, and corrections require original publication timestamps; final lineups cannot be backfilled into earlier predictions.
- Keep expected-lineup scenarios separate from confirmed-lineup predictions and widen uncertainty when availability is unresolved.
- Player and tactical features require position-appropriate metrics, minimum minutes, recency and opponent adjustment, shrinkage, and chronological ablation evidence.
- Prevent double counting between team form, player strength, coach effects, and tactical matchup features.
- Timestamp odds, inputs, predictions, signals, and model versions.
- Never fabricate profitable results or present demo results as real evidence.
- Never scrape protected bookmaker services or assume a public bookmaker API exists.
- Never commit secrets, credentials, cookies, proprietary raw data, local databases, or model binaries.
- Keep model, market, line-shopping, and bookmaker-margin effects separate.
- Keep arbitrage separate from model value: use only complete, mutually exclusive, exhaustive outcomes with identical event, line, period, currency, and settlement rules.
- Rank arbitrage by worst-case net profit after explicit taxes, fees, commissions, currency costs, stake limits, and rounding; unknown or stale tax rules must block an executable result.
- Never call an arbitrage opportunity guaranteed before all legs are accepted and honoured under the configured settlement and tax rules.
- Add deterministic tests for every quantitative behavior change.
- Do not add player props until player-level targets and settlement are independently validated.
