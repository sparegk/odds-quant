# AGENTS.md

## Structure

- `backend/app/api`: versioned FastAPI routes.
- `backend/app/db`: SQLAlchemy models and sessions.
- `backend/app/providers`: legal data-source adapters.
- `backend/app/quant`: pure probability and settlement logic.
- `backend/app/signals`: explainable signal policy.
- `backend/tests`: deterministic backend tests.

## Commands

From `backend`:

```bash
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy app
python -m uvicorn app.main:app --reload
```

## Non-Negotiable Rules

- Use only information available before an event kickoff; tests must reject look-ahead leakage.
- Timestamp odds, inputs, predictions, signals, and model versions.
- Never fabricate profitable results or present demo results as real evidence.
- Never scrape protected bookmaker services or assume a public bookmaker API exists.
- Never commit secrets, credentials, cookies, proprietary raw data, local databases, or model binaries.
- Keep model, market, line-shopping, and bookmaker-margin effects separate.
- Keep arbitrage separate from model value: use only complete, mutually exclusive, exhaustive outcomes with identical event, line, period, currency, and settlement rules.
- Rank arbitrage by worst-case net profit after explicit taxes, fees, commissions, currency costs, stake limits, and rounding; unknown or stale tax rules must block an executable result.
- Never call an arbitrage opportunity guaranteed before all legs are accepted and honoured under the configured settlement and tax rules.
- Add deterministic tests for every quantitative behavior change.
