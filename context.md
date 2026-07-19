# OddsQuant Context

## Vision

OddsQuant is a portfolio-quality educational analytics platform for a statistics student learning quantitative modelling, data engineering, backtesting, and full-stack development. Football is the first sport, but sport and provider adapters must permit later extension.

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

Phase 0 establishes project configuration, normalized persistence models, provider contracts, pure quantitative functions, a health API, and initial tests. Phase 1 will add migrations, deterministic demo seeding, team/player/lineup data contracts, CSV ingestion, model training, stored signals, a tax-aware football arbitrage scanner, backtesting, bankroll simulation, and the connected React dashboard.
