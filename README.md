# OddsQuant

OddsQuant is an educational full-stack sports-betting analytics project. It is designed to compare bookmaker implied probabilities, vig-free market probabilities, and transparent statistical-model probabilities without claiming guaranteed profit or placing bets automatically.

## Repository Status

This repository is in **Phase 0: foundation**. It currently contains:

- FastAPI configuration and health/status endpoints.
- SQLAlchemy models for events, markets, timestamped odds, predictions, signals, and backtests.
- Probability, de-vigging, Poisson scoreline, bet-builder, settlement, and signal-policy primitives.
- Provider-adapter contracts for licensed APIs, official sources, CSV uploads, manual entry, and labelled demo data.

The connected Phase 1 MVP, demo dataset, import UI, model training pipeline, backtester, and dashboard remain under active development. No performance results are claimed.

## Backend Setup

Requires Python 3.12 or newer.

```bash
cd backend
python -m venv .venv
python -m pip install -e ".[dev]"
python -m uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs` or check:

```bash
curl http://127.0.0.1:8000/health
```

Run the foundation tests with:

```bash
cd backend
python -m pytest
python -m ruff check .
python -m mypy app
```

## Responsible Use

No prediction guarantees profit. Statistical edges can disappear, odds change rapidly, and historical performance does not ensure future performance. Users must comply with local laws, age restrictions, and provider/bookmaker terms. OddsQuant is not affiliated with any bookmaker and does not place bets.

See [context.md](context.md), [ARCHITECTURE.md](ARCHITECTURE.md), and [ROADMAP.md](ROADMAP.md) for the implementation direction.

