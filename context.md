# OddsQuant Context

## Vision

OddsQuant is a portfolio-grade quantitative sports intelligence platform designed for practical football market research and decision support. Its purpose is to turn permitted, timestamped odds and match data into reproducible probability estimates, price comparisons, explainable signals, arbitrage analysis, and leakage-safe historical evaluation. It is also intended to demonstrate professional capability across quantitative modelling, statistics, data engineering, machine learning, backtesting, backend architecture, and full-stack development. Football is the first sport, while sport-specific and provider adapters preserve a path to later expansion.

The target user is a quantitatively minded analyst who wants to inspect how a conclusion was produced, distinguish model edge from line shopping and bookmaker margin, understand uncertainty and execution risk, and reproduce an analysis from its original data and model version. OddsQuant should support credible real-world research without presenting unverified outputs as profitable or automating bet placement.

## Quantitative Principles

Decimal odds imply probability through `1 / odds`. Complete mutually exclusive markets can be de-vigged proportionally or with the power method. Double-chance outcomes overlap and must instead be derived as unions of mutually exclusive 1X2 probabilities.

The first model is an interpretable Poisson goals baseline. Its scoreline distribution supports 1X2, totals, both-teams-to-score, double chance, team totals, and responsible joint bet-builder calculations. Model probabilities must never be copied from bookmaker prices.

Signals distinguish model edge, best-price improvement, and margin. Stale data, small samples, weak calibration, missing inputs, material price movement, or uncertainty wider than the estimated edge must prevent a strong `VALUE` classification.

## Recent Football Intelligence

Team form alone is insufficient for maximum practical accuracy. OddsQuant will collect timestamped team, player, coach, lineup, formation, availability, and tactical evidence from permitted sources. Match-level models can then account for which players are likely to play, their current roles and minutes, how a coach deploys them, and whether one side's documented style creates a measurable matchup advantage.

Player data includes stable identity, registration, position and role, starts, minutes, substitutions, recent and long-run position-specific statistics, injury or suspension status, and expected versus confirmed lineup evidence. Per-90 statistics require minimum minutes, recency weighting, opponent and competition adjustment, and shrinkage toward appropriate priors.

Coach and tactical data includes tenure, formation usage, pressing, defensive block and line height, width, build-up, directness, transitions, set pieces, and substitution patterns where these are supported by reproducible event data. A coach change creates a high-uncertainty regime; it is not automatically a positive or negative signal.

Matchup features represent interactions such as press versus build-up resistance, pace versus a high line, aerial attack versus aerial defense, set pieces, flank overloads, and transition attack versus rest defense. A single player can materially change a matchup, but football roles are dynamic. Direct player-versus-player history is used only with adequate comparable minutes; otherwise role-versus-system features are preferred.

These adjustments are added after the team-level Poisson baseline and must improve out-of-sample calibration in chronological ablation tests. The model must avoid double counting player effects already embedded in team form. It produces separate expected-lineup scenarios and confirmed-lineup predictions, and widens uncertainty or blocks strong signals when player availability or tactical roles are unresolved.

## Cross-Bookmaker Arbitrage

Arbitrage is separate from statistical value and does not require a model probability. For a complete set of mutually exclusive outcomes, OddsQuant selects the best decimal price for each outcome across bookmakers and calculates `inverse_sum = sum(1 / odds_i)`. A gross theoretical arbitrage exists only when the inverse sum is below one.

For total budget `B`, the pre-tax dutching allocation is `B * (1 / odds_i) / inverse_sum`, targeting common gross payout `B / inverse_sum`. Calculations retain full precision internally and round stakes only at the bookmaker currency increment. Rounding remainders are allocated conservatively so minimum payout is never overstated.

The football scanner initially supports:

- Match result using the complete home/draw/away partition.
- Over/under only when both sides use the identical line and period.
- Both teams to score when yes/no settlement definitions match.
- Other markets only when selections form a verified exhaustive partition.

Double-chance selections overlap and must not be treated as a three-outcome arbitrage market. Markets from different matches, periods, handicap lines, currencies, overtime rules, or settlement definitions must never be combined.

### Tax- and Fee-Aware Profit

Tax treatment is bookmaker- and jurisdiction-specific. Each leg can carry an explicit tax/fee profile with:

- Stake levy rate and whether it is included in the displayed stake.
- Tax on gross payout, winnings, or profit, with its threshold and rounding rule.
- Withholding rate, exchange commission, fixed fee, and currency-conversion cost.
- Effective dates, jurisdiction, source URL or manual evidence, and confidence status.

The engine computes each outcome's net payout through that leg's configured settlement function, rather than assuming taxes can always be represented by adjusted odds. It then solves for stakes that maximize the minimum net profit subject to currency increments, maximum accepted stakes, and total budget. Net arbitrage exists only when:

```text
min(net_payout_for_each_outcome) - total_cash_outlay > 0
```

Both gross and net results are shown. `TAX_UNKNOWN`, `TAX_STALE`, or conflicting profiles block an executable ranking and instead display a scenario analysis. Tax information may come only from a permitted provider field, an official published rule, or an explicit user entry; OddsQuant will not scrape a betting app to infer it. Users remain responsible for verifying personal tax obligations.

The ranking prioritizes conservative net ROI after taxes, fees, configurable odds haircut, freshness, complete bookmaker coverage, settlement compatibility, tax confidence, and estimated executable stake. It shows every bookmaker/selection/price, required stake, cash outlay, gross payout, tax/fees, minimum net payout, net profit, timestamps, and risks.

The phrase "guaranteed profit" applies only to the mathematical payoff after every required leg has been accepted at the quoted price and all legs are honoured and taxed under the configured rules. Before that point, the app uses `THEORETICAL_ARBITRAGE` and warns about odds movement, rejected or limited stakes, palpable-error rules, account restrictions, asymmetric voids, commissions, currency conversion, taxes, and data latency. OddsQuant does not automate execution or provide tax advice.

## Data And Backtesting

Allowed inputs are licensed APIs, official sources, user CSVs, manual entries, and clearly labelled demo data. All observations are timestamped and linked to their provider. Historical evaluation uses chronological splits and walk-forward prediction with inputs strictly earlier than kickoff.

Historical player, injury, lineup, and coach features require their original publication timestamps. A backtest cannot treat the final starting lineup or later-confirmed injury outcome as known at an earlier prediction time. Full source, freshness, feature, and quality rules are defined in `DATA_SOURCES.md`.

The first complete backtester will report predictive calibration and betting-strategy metrics, including Brier score, log loss, ECE, ROI, yield, profit in units, CLV, drawdown, and grouped performance. Synthetic results demonstrate software behavior only.

## Current Status

The data-foundation and initial model-baseline portions of Phase 1 are operational. Alembic creates and evolves the point-in-time schema. The backend has strict odds and historical-result CSV contracts, atomic ingestion, immutable raw import records, rejected-job audits, timestamped result corrections, and deterministic current-anchor synthetic odds and history seeds.

Versioned routes now expose events, event detail, providers, import jobs, multipart odds import, and stored odds comparison. Comparison responses calculate raw implied probability, bookmaker overround and margin, proportional and power de-vig probabilities, corresponding fair odds, freshness, and best available price from each bookmaker's latest coherent snapshot as of the requested time.

The backend now trains a shrunk venue-specific Poisson team-strength baseline using only final result observations available by the requested cutoff. Each immutable model version stores its training window, input fingerprint, feature version, parameters, sample size, and `unvalidated` evaluation status. Pre-kickoff predictions persist expected goals, the score matrix, canonical derived markets, selection probabilities, sampling intervals, and exact input timestamp. The dashboard lists real stored model versions but continues to block value and performance claims.

The backend now performs expanding-window held-out replay with exact per-event training fingerprints, proper 1X2 scores, calibration buckets, eligibility coverage, uniform and compatible point-in-time market benchmarks, and an explicit non-demo promotion policy. The dashboard exposes these runs without converting synthetic results into evidence.

Market calculations are deliberately not labelled `VALUE`: a model must pass the stored calibration policy on adequate permitted history before its independently generated prediction can be joined to a fresh compatible price. Signals, underdogs, arbitrage, and strategy backtesting remain unimplemented. Synthetic history validates software behavior only and no model performance or profitability result is claimed.

The operational baseline includes non-root backend and frontend images, a PostgreSQL/API/worker/frontend Compose stack, a Render Blueprint, Vercel configuration, and full-stack GitHub Actions checks. The separate APScheduler worker accepts only explicitly registered licensed, official, or demo adapters, requires a terms/source URL for external adapters, stores redacted provider-job outcomes, and reuses atomic ingestion. No external adapter is registered by default. Production blocks demo seeding regardless of the seed flag.
