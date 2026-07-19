# OddsQuant Context

## Vision

OddsQuant is a portfolio-quality educational analytics platform for a statistics student learning quantitative modelling, data engineering, backtesting, and full-stack development. Football is the first sport, but sport and provider adapters must permit later extension.

## Quantitative Principles

Decimal odds imply probability through `1 / odds`. Complete mutually exclusive markets can be de-vigged proportionally or with the power method. Double-chance outcomes overlap and must instead be derived as unions of mutually exclusive 1X2 probabilities.

The first model is an interpretable Poisson goals baseline. Its scoreline distribution supports 1X2, totals, both-teams-to-score, double chance, team totals, and responsible joint bet-builder calculations. Model probabilities must never be copied from bookmaker prices.

Signals distinguish model edge, best-price improvement, and margin. Stale data, small samples, weak calibration, missing inputs, material price movement, or uncertainty wider than the estimated edge must prevent a strong `VALUE` classification.

## Data And Backtesting

Allowed inputs are licensed APIs, official sources, user CSVs, manual entries, and clearly labelled demo data. All observations are timestamped and linked to their provider. Historical evaluation uses chronological splits and walk-forward prediction with inputs strictly earlier than kickoff.

The first complete backtester will report predictive calibration and betting-strategy metrics, including Brier score, log loss, ECE, ROI, yield, profit in units, CLV, drawdown, and grouped performance. Synthetic results demonstrate software behavior only.

## Current Status

Phase 0 establishes project configuration, normalized persistence models, provider contracts, pure quantitative functions, a health API, and initial tests. Phase 1 will add migrations, deterministic demo seeding, CSV ingestion, model training, stored signals, backtesting, bankroll simulation, and the connected React dashboard.

