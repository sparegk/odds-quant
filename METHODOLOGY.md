# Quantitative Methodology

OddsQuant separates market measurement, statistical prediction, price comparison, arbitrage, and historical evaluation. A high decimal price is never evidence of value by itself, and demonstration data is never evidence of profitability.

## Odds And Market Probability

For decimal odds `o`, raw implied probability is `1 / o`. A complete mutually exclusive market has overround `sum(1 / o_i)` and bookmaker margin `overround - 1`.

The implemented comparison service reports two vig-removal estimates:

- Proportional: divide each raw implied probability by their sum.
- Power: solve for an exponent that makes the transformed probabilities sum to one.

Both are estimates of market consensus, not model predictions. OddsQuant retains the original offered price, bookmaker, timestamp, line, period, currency, and settlement rule alongside every calculation.

## Football Probability Model

The implemented baseline estimates league home/away goal rates plus venue-specific attack and defence ratios. Each ratio is shrunk toward the league average by a configurable prior-match count. Training selects only final results whose kickoff precedes the exclusive training cutoff and whose result observation and settlement timestamps are at or before that cutoff.

Expected goals combine the home team's home attack, the away team's away defence, the league home rate, and the corresponding away components. Rates are bounded to a documented numerical range before independent Poisson score probabilities are calculated. This is an interpretable baseline, not yet a calibrated production model; Dixon-Coles and other adjustments can be added only when walk-forward validation demonstrates an improvement.

A scoreline matrix derives probabilities for match result, totals, both teams to score, double chance, supported team totals, and supported joint bet-builder outcomes. Player availability, expected and confirmed lineups, coach regimes, and tactical matchups remain distinct evidence classes so their incremental value can be tested without double counting.

Every stored prediction must identify its model version, prediction time, input cutoff, training interval, feature version, sample size, uncertainty interval, and evidence class. Missing or post-cutoff evidence cannot be silently substituted.

The current selection intervals are Wilson sampling intervals based on the training-match count. They communicate limited sample reliability but do not capture all parameter, lineup, tactical, or regime uncertainty.

Evaluation replays events chronologically with an expanding window. For every event, the model is refitted from final results whose kickoff, settlement, and original observation timestamps all precede the prediction cutoff. Each replay row stores the result version, training fingerprint, prediction timestamp, full 1X2 vector, outcome, and proper scores.

Multiclass Brier score is the sum of squared error across HOME, DRAW, and AWAY, on the documented 02 scale. Log loss is the negative logarithm of the probability assigned to the realized outcome. Calibration uses fixed one-vs-rest probability buckets for all three outcomes, and ECE is weighted across every stored binary outcome forecast. These are proper probability scores consistent with the [scikit-learn model-evaluation guidance](https://scikit-learn.org/stable/modules/model_evaluation.html).

Promotion requires at least 200 non-demo observations, at least 90% replay coverage, ECE no greater than 0.08, and both Brier score and log loss better than a uniform 1X2 benchmark. These are an explicit initial policy, not a claim that the thresholds are universally optimal. Demo-contaminated runs are always `demo_only`; insufficient or failed runs cannot unlock value signals.

## Value And Confidence

For model probability `p` and offered decimal odds `o`:

```text
model_fair_odds = 1 / p
expected_value = p * o - 1
probability_edge = p - market_fair_probability
```

Signal strength also depends on uncertainty, calibration, sample size, price movement, freshness, input completeness, and model regime. An estimated edge smaller than its uncertainty cannot produce a strong `VALUE` signal.

Signal generation is point-in-time and provenance-bound. It requires a non-demo `calibrated` evaluation whose test window ends no later than the prediction input cutoff. For each exact market definition, it uses the latest complete non-demo snapshot per bookmaker, excludes stale bookmakers from consensus whenever fresh snapshots exist, averages proportional de-vig probabilities for market consensus, and selects the best offered price separately. Expected value is `model_probability * offered_odds - 1`; a strong signal also requires the same calculation to remain positive at the stored lower probability bound. Material price movement, stale odds, weak calibration, or inadequate venue history downgrades or blocks the classification.

## Arbitrage

For a verified exhaustive partition with best compatible prices `o_i`, gross theoretical arbitrage requires `sum(1 / o_i) < 1`. OddsQuant does not combine overlapping selections, mismatched lines, different periods, inconsistent currencies, or incompatible settlement rules.

The practical calculation applies taxes, fees, commissions, currency costs, minimum and maximum stakes, stake increments, conservative price haircuts, and rounded dutching. Unknown or stale tax rules block an executable ranking. Profit is not described as guaranteed before every required leg is accepted and honoured under the assumed rules.

## Bet Builder Dependence

Correlated legs are not multiplied as if independent. Supported football combinations are evaluated by summing cells in the modelled scoreline distribution that satisfy every leg. Unsupported player or event combinations remain blocked until a defensible joint model exists.

## Backtesting

Backtests use chronological train, validation, and test windows with walk-forward prediction. Each observation links the exact prediction and odds snapshot available at that time. Final lineups, corrected results, later injury confirmation, closing prices, and other post-cutoff evidence cannot enter an earlier prediction.

Reported predictive metrics include Brier score, log loss, calibration error, and bucketed calibration. Strategy metrics include signal count, hit rate, ROI, yield, profit in units, closing-line value, maximum drawdown, and profit factor, split by league, bookmaker, market, odds range, and favorite/underdog status. Benchmarks include market vig-free probability and basic football models.

Synthetic runs validate software behavior only. They must be labelled and cannot be presented as real performance.
