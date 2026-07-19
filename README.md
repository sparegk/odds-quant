# OddsQuant

OddsQuant is a quantitative sports-betting analytics project for football. The goal is to collect timestamped odds, compare bookmaker prices with vig-free market and statistical-model probabilities, identify explainable value or arbitrage candidates, and test whether those methods hold up historically.

This is not a betting-tips website or an automated betting system. It is an educational project for studying probability, statistics, data engineering, modelling, backtesting, and full-stack software development.

## Project Goals

- Track football events and bookmaker odds over time.
- Compare raw implied, vig-free market, and independent model probabilities.
- Find the best available price for each selection across bookmakers.
- Detect cross-bookmaker arbitrage after taxes, fees, and execution constraints.
- Generate explainable `VALUE`, `WATCH`, `PASS`, and risk signals.
- Analyze underdogs without treating high odds as evidence of value.
- Evaluate correlated bet-builder combinations from scoreline probabilities.
- Backtest every method with chronological, leakage-safe data.
- Present calibration, uncertainty, freshness, and limitations clearly.

## Main Features

### Football And Odds Data Collection

The system will store recurring, timestamped snapshots for:

- Football events, competitions, teams, and kickoff times.
- Match-result, totals, both-teams-to-score, double-chance, and supported team-total markets.
- Bookmakers, selections, decimal prices, opening prices, and closing prices.
- Provider, import-job, source-quality, and data-freshness metadata.
- Team form, opponent-adjusted strength, home/away splits, rest, travel, and schedule congestion.
- Player rosters, positions, minutes, recent performance, injuries, suspensions, and availability.
- Timestamped expected and confirmed lineups, formations, coaches, and tactical roles.
- Matchup evidence such as pressing versus build-up, aerial strength, set pieces, flank usage, defensive line, and transition style.

Odds will come only from licensed APIs, official sources, user-uploaded CSV files, manual entry, or clearly labelled demo data. OddsQuant will not bypass bookmaker protections or assume that a bookmaker has a public API.

Every football observation will retain its source, provider update time, collection time, effective period, and reliability status. Recent data is not automatically valid: inconsistent event identities, missing minutes, incompatible metric definitions, unconfirmed availability, or information published after the prediction cutoff must be rejected or downgraded.

### Odds And Probability Analysis

For every complete market, OddsQuant will calculate:

- Raw implied probability using `1 / decimal_odds`.
- Market overround and bookmaker margin.
- Proportional and power-method vig-free probabilities.
- Fair odds and differences between bookmakers.
- Best available price and price improvement.

Double-chance outcomes overlap, so they will be derived from a valid 1X2 distribution rather than incorrectly de-vigged as three exclusive outcomes.

### Football Probability Model

The first transparent baseline will model home and away goals with Poisson methods and team-strength features. It will establish a leakage-safe benchmark before player and tactical adjustments are added. A scoreline probability matrix will derive probabilities for:

- Home win, draw, and away win.
- Over/under goal lines.
- Both teams to score.
- Double chance.
- Supported team totals and joint outcomes.

Predictions must use only information available before kickoff. Model versions, input cutoffs, uncertainty, sample size, and calibration will be stored so results remain reproducible.

Later match-level models will adjust the baseline using player availability, expected or confirmed lineups, coach and formation changes, and validated tactical interactions. They will use recency weighting, opponent adjustment, position-specific metrics, minimum-minute thresholds, and shrinkage so a small number of matches cannot dominate a prediction. Expected-lineup scenarios and confirmed-lineup predictions will remain separate.

Player-versus-player and tactical matchup features will be learned and backtested rather than asserted from narrative alone. For example, the system may test whether a high press disrupts a particular build-up structure or whether aerial and set-piece strengths exploit a documented weakness. It must avoid double-counting effects already present in team form and widen uncertainty when lineup or role information is incomplete.

### Value Signal Engine

Each selection will compare the model probability with the vig-free market probability and actual offered odds:

```text
model_fair_odds = 1 / model_probability
expected_value = model_probability * decimal_odds - 1
probability_edge = model_probability - market_fair_probability
```

Example signals include:

- `VALUE`
- `WATCH`
- `PASS`
- `OVERPRICED_FAVORITE`
- `INSUFFICIENT_DATA`

A strong signal will be blocked when data is stale, inputs are missing, sample size is inadequate, calibration is weak, odds moved materially, or uncertainty is wider than the estimated edge.

Signals will also be blocked or downgraded when important player availability is unresolved, only an expected lineup is available, a recent coaching change has too little evidence, or the edge disappears under reasonable lineup scenarios.

### Football Arbitrage Scanner

The arbitrage scanner will compare the best price for every mutually exclusive and exhaustive outcome in the same football market:

```text
inverse_sum = sum(1 / best_decimal_odds_for_outcome)
```

A gross theoretical arbitrage exists when `inverse_sum < 1`. The scanner will support complete 1X2 markets and compatible two-way markets such as over/under and both teams to score. It will never combine different events, periods, lines, currencies, or settlement rules.

Gross margin is not enough. Ranking will use the worst-case net payout after:

- Stake, winnings, profit, or payout taxes.
- Exchange commission and fixed fees.
- Currency conversion and stake rounding.
- Maximum accepted stakes and total budget.
- A configurable odds-movement safety haircut.

Unknown, stale, or conflicting tax rules will produce `TAX_UNKNOWN` or `TAX_STALE`, not an executable profit claim. Every result will show the required bookmaker legs, stakes, total cash outlay, gross payout, taxes and fees, minimum net payout, net profit, freshness, and execution risks.

### Underdog Scanner

The underdog view will rank team outcomes using positive expected value, model-versus-market edge, best odds, confidence, calibration, movement, and freshness. It will also explain false-value risks. A large possible payout is not automatically positive expected value.

### Bet Builder Laboratory

Supported combinations will be evaluated by summing matching cells in the model scoreline distribution. Correlated leg probabilities will not be naively multiplied. The laboratory will show marginal probabilities, modelled joint probability, fair combined odds, optional offered odds, expected value, uncertainty, and dependence warnings.

### Backtesting

Every historical prediction and signal will be stored with the odds and information available at that time. Backtests will use chronological splits and walk-forward evaluation, never random time-dependent splits.

Planned metrics include:

- Bet count, hit rate, ROI, yield, and profit in units.
- Average expected value and closing-line value.
- Brier score, log loss, calibration error, and probability buckets.
- Maximum drawdown and profit factor.
- Results by league, bookmaker, market, odds range, and favorite/underdog.
- Comparisons with market probability, favorite, Elo, and basic Poisson benchmarks.

Demo or synthetic results will always be labelled and will never be presented as proof of profitability.

### Bankroll Research

The research simulator will support flat staking, percentage staking, capped fractional Kelly, daily exposure limits, and drawdown simulations. Kelly staking will be disabled by default for low-confidence predictions. This is statistical risk analysis, not financial advice.

### Dashboard

The planned React dashboard will include:

- Overview and data-freshness status.
- Value opportunities and underdog analysis.
- Football arbitrage opportunities and stake allocation.
- Event, market, and bookmaker price comparison.
- Bet Builder Laboratory.
- Model calibration and performance.
- Lineup status, player availability, tactical context, and matchup sensitivity.
- Backtesting and bankroll simulation.
- CSV imports, providers, jobs, methodology, and disclaimers.

## Planned Tech Stack

- Python 3.12+
- FastAPI and Pydantic
- SQLAlchemy and Alembic
- PostgreSQL in production and SQLite for simple local development
- pandas, NumPy, SciPy, and scikit-learn
- APScheduler
- pytest, Ruff, and mypy
- React, TypeScript, Vite, and Tailwind CSS
- Recharts, Vitest, and Testing Library
- Docker Compose and GitHub Actions

## Build Plan

1. Finalize configuration, database sessions, and the initial Alembic migration.
2. Add deterministic, clearly labelled football demo data.
3. Add normalized team, player, coach, roster, appearance, availability, lineup, and tactical data contracts.
4. Build atomic CSV and manual import workflows for football data and odds.
5. Store coherent timestamped market snapshots and closing prices.
6. Complete odds conversion and de-vigging services and tests.
7. Train and version the leakage-safe Poisson baseline.
8. Add lineup, player-strength, coach, and validated tactical-matchup adjustments.
9. Generate explainable value and underdog signals.
10. Add the tax-aware football arbitrage engine.
11. Add scoreline-based bet-builder evaluation.
12. Build walk-forward backtesting and bankroll research.
13. Connect the React dashboard to versioned API endpoints.
14. Complete Docker, CI, deployment, documentation, and end-to-end verification.

## Current Implementation

The repository is currently at **Phase 0: foundation**. It includes:

- FastAPI application configuration and CORS handling.
- `GET /health` and `GET /api/v1/status`.
- SQLAlchemy models for sports, events, markets, odds, results, model versions, predictions, signals, bet-builder quotes, backtests, imports, and provider jobs.
- Provider-adapter contracts for legal and explicitly configured data sources.
- Pure functions for decimal-odds conversion, market overround, proportional and power de-vigging, fair odds, EV, and closing-line value.
- Poisson scoreline and joint bet-builder probability primitives.
- Settlement and explainable signal-policy primitives.
- Initial API tests and project documentation.

The connected Phase 1 data pipeline, demo seed, migrations, arbitrage service, model training workflow, backtester, and frontend are not implemented yet. No real or synthetic performance result is currently claimed.

## Repository Structure

```text
backend/
  app/
    api/         Versioned FastAPI routes
    core/        Runtime configuration
    db/          SQLAlchemy models and sessions
    providers/   Data-provider contracts
    quant/       Pure probability and odds calculations
    signals/     Explainable signal policy
  tests/         Backend tests
```

Additional backend modules and the `frontend` application will be added during Phase 1.

## Local Backend Setup

```bash
cd backend
python -m venv .venv
python -m pip install -e ".[dev]"
python -m uvicorn app.main:app --reload
```

Open the API documentation at `http://127.0.0.1:8000/docs` or check:

```bash
curl http://127.0.0.1:8000/health
```

Run the available checks from `backend`:

```bash
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy app
```

Copy `.env.example` to `.env` for local configuration. Never commit API keys, tokens, bookmaker credentials, cookies, or proprietary data.

## Project Status

OddsQuant has a documented architecture, normalized persistence model, provider boundary, quantitative foundations, and a minimal FastAPI service. The next milestone is a runnable vertical slice with Alembic migrations, labelled demo data, CSV import, stored odds, and the first connected analysis endpoint.

See [context.md](context.md), [ARCHITECTURE.md](ARCHITECTURE.md), [ROADMAP.md](ROADMAP.md), and [AGENTS.md](AGENTS.md) for detailed decisions and operating rules.

Data-source, freshness, lineup, player, and tactical requirements are documented in [DATA_SOURCES.md](DATA_SOURCES.md).

## Disclaimer

OddsQuant is an educational analytics project. It is not affiliated with, endorsed by, or sponsored by any bookmaker. It does not place bets and does not provide financial, gambling, legal, or tax advice.

No prediction or displayed arbitrage guarantees profit in practice. Odds can change before all legs are accepted; stakes may be limited or rejected; and void, settlement, commission, currency, and tax rules can remove an apparent edge. Users must verify current prices and rules, follow local laws and age restrictions, set strict financial limits, and avoid chasing losses.
