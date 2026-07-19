# OddsQuant

OddsQuant is an educational full-stack sports-betting analytics project. It is designed to compare bookmaker implied probabilities, vig-free market probabilities, transparent statistical-model probabilities, and cross-bookmaker arbitrage prices without claiming unconditional guaranteed profit or placing bets automatically.

## Football Arbitrage

OddsQuant will include a dedicated football arbitrage scanner. It will take the best available price for every mutually exclusive and collectively exhaustive outcome in the same market, then test:

```text
inverse_sum = sum(1 / best_decimal_odds_for_outcome)
```

When `inverse_sum < 1`, dutching stakes across all outcomes produces the same theoretical gross payout regardless of the result. For total stake budget `B`, outcome `i` receives `B * (1 / odds_i) / inverse_sum`; theoretical gross ROI is `1 / inverse_sum - 1`.

Gross arbitrage is not enough. The scanner will calculate a net outcome payout using explicit bookmaker and jurisdiction settings for stake taxes, winnings/profit taxes, payout withholding, exchange commission, fixed fees, currency conversion, and currency rounding. An opportunity is ranked as net arbitrage only when the minimum net payout across every outcome remains above the total cash outlay. If the applicable tax basis is unknown, the result is labelled `TAX_UNKNOWN` and is not presented as executable profit.

The scanner will initially cover complete football 1X2 markets and compatible two-way markets such as over/under and both teams to score. Every leg must refer to the same event, market, line, period, currency, and settlement rules. The dashboard will rank opportunities by conservative net ROI, price freshness, bookmaker coverage, settlement compatibility, tax confidence, and estimated executable stake.

An arbitrage calculation is not an unconditional profit guarantee. Odds can move before every leg is accepted, bookmakers can reject or limit stakes, tax treatment can change, and void or settlement rules can differ. The product will therefore label results as **theoretical arbitrage opportunities**, show every required leg, tax/fee assumption, and risk, and never automate bet placement.

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

No prediction or displayed arbitrage guarantees profit in practice. Statistical edges can disappear, odds change rapidly, and historical performance does not ensure future performance. Cross-book arbitrage remains exposed to execution, stake-limit, account, void, settlement, commission, currency, tax, and data-latency risk. Users must verify their own applicable tax treatment and comply with local laws, age restrictions, and provider/bookmaker terms. OddsQuant is not affiliated with any bookmaker, does not provide tax advice, and does not place bets.

See [context.md](context.md), [ARCHITECTURE.md](ARCHITECTURE.md), and [ROADMAP.md](ROADMAP.md) for the implementation direction.
