# Quantitative Methodology

OddsQuant separates market measurement, statistical prediction, price comparison, arbitrage, and historical evaluation. A high decimal price is never evidence of value by itself, and demonstration data is never evidence of profitability.

The active research goal is match-result probability quality. Existing arbitrage behavior is maintenance-only. Probability validation and market/value validation are independent evidence tracks: passing chronological proper-score and recalibration gates may authorize probability research, but only a separately passing market-relative evaluation may authorize value signals. Neither status authorizes CLV, staking, ROI, or profitability claims without their own evidence.

## Odds And Market Probability

For decimal odds `o`, raw implied probability is `1 / o`. A complete mutually exclusive market has overround `sum(1 / o_i)` and bookmaker margin `overround - 1`.

The implemented comparison service reports two vig-removal estimates:

- Proportional: divide each raw implied probability by their sum.
- Power: solve for an exponent that makes the transformed probabilities sum to one.

Both are estimates of market consensus, not model predictions. OddsQuant retains the original offered price, bookmaker, timestamp, line, period, currency, and settlement rule alongside every calculation.

## Football Probability Model

The implemented baseline estimates league home/away goal rates plus venue-specific attack and defence ratios. Each ratio is shrunk toward the league average by a configurable prior-match count. Training selects only final results whose kickoff precedes the exclusive training cutoff and whose result observation and settlement timestamps are at or before that cutoff.

Expected goals combine the home team's home attack, the away team's away defence, the league home rate, and the corresponding away components. Rates are bounded to a documented numerical range before independent Poisson score probabilities are calculated. This remains the interpretable production baseline unless chronological non-demo evidence supports changing it.

Two independent benchmarks are replayed from the identical pre-forecast result window. The Elo benchmark uses a Davidson draw term, fixed home advantage, and ratings updated only when a result was observed. The Dixon–Coles benchmark jointly fits attack, defence, league intercept, home advantage, and a bounded low-score correlation parameter. Its likelihood weights older fixtures by `exp(-0.0018 * age_days)`. Both benchmark probability vectors are fingerprinted and scored separately; neither silently replaces the Poisson predictions or changes the promotion policy.

A scoreline matrix derives probabilities for match result, totals, both teams to score, double chance, supported team totals, and supported joint bet-builder outcomes. Player availability, expected and confirmed lineups, coach regimes, and tactical matchups remain distinct evidence classes so their incremental value can be tested without double counting.

Every stored prediction must identify its model version, prediction time, input cutoff, training interval, feature version, sample size, uncertainty interval, probability-calibration provenance, and evidence class. Missing or post-cutoff evidence cannot be silently substituted.

Current model versions estimate selection uncertainty through 400 deterministic chronological moving-block bootstrap refits. The block length is the rounded square root of the training sample with a minimum of two matches, and the seed is fingerprinted from the immutable training data, event, method, and version. Stored 95% selection intervals are quantiles of the refitted probability distribution. Legacy model versions retain their labelled Wilson training-sample proxy; the fallback is never presented as equivalent to refit uncertainty.

Evaluation replays events chronologically with an expanding window. For every event, the model is refitted from final results whose kickoff, settlement, and original observation timestamps all precede the prediction cutoff. Each replay row stores the result version, training fingerprint, prediction timestamp, full 1X2 vector, outcome, and proper scores.

Multiclass Brier score is the sum of squared error across HOME, DRAW, and AWAY, on the documented 02 scale. Log loss is the negative logarithm of the probability assigned to the realized outcome. Calibration uses fixed one-vs-rest probability buckets for all three outcomes, and ECE is weighted across every stored binary outcome forecast. These are proper probability scores consistent with the [scikit-learn model-evaluation guidance](https://scikit-learn.org/stable/modules/model_evaluation.html).

Promotion requires at least 200 non-demo observations, at least 90% replay coverage, and ECE no greater than 0.08. Poisson must beat the uniform benchmark on Brier score and log loss with the upper bounds of paired 95% moving-block-bootstrap loss differences below zero. Market-relative promotion separately requires at least 160 compatible observations, at least 80% coverage, and at least two bookmakers per event from complete de-vigged 1X2 snapshots no more than 24 hours old; both paired market loss upper bounds must also be below zero.

The same replay fits scalar temperature scaling only from earlier held-out forecasts and outcomes. Walk-forward recalibration starts after 60 historical forecasts and needs at least 100 subsequent held-out observations. The earlier half is a development partition that selects temperature scaling only when it materially improves Brier score and log loss without worsening ECE; otherwise it selects the identity transform. The selected method is then accepted only when it does not degrade Brier score, log loss, or ECE on the later untouched partition of at least 50 observations. This rule is fixed before a new replay and prevents an already-calibrated raw model from being forced through a harmful transform. The final calibrator is fingerprinted, fitted through the evaluation cutoff, and may be applied only to later predictions from the exact accepted non-demo evaluation. Raw scoreline probabilities remain available for unsupported markets, while calibrated 1X2 probabilities and their transformed bootstrap intervals retain the calibrator method, version, sample size, cutoff, fingerprint, and evaluation-run identifier.

These are explicit fail-closed policies, not claims that the thresholds are universally optimal. Demo-contaminated runs are always `demo_only`; absent market evidence, insufficient recalibration evidence, rejected recalibration, or other failed checks cannot unlock value signals.

Model and hyperparameter comparisons use a nested chronological selector. Each outer replay forecast first produces a fixed candidate grid of Poisson models with 3, 5, and 8 prior-match shrinkage strengths and Davidson Elo models with K-factors 10, 20, and 30 while retaining the model's other Elo settings. After at least 60 earlier held-out forecasts, the selector ranks candidates by mean log loss, then Brier score, then a deterministic candidate name tie-break. Only earlier held-out outcomes can select the candidate for the next event. The selected forecast, candidate counts, grid, and first/last history fingerprints are stored as the `nested_selected` research benchmark. It cannot promote a production model or authorize signals by itself.

A separate chronological ensemble blends Poisson, Elo, and Dixon–Coles 1X2 probabilities. Its pre-registered weight grid uses 0.25 increments, sums to one, and requires at least two models to have positive weight. For every forecast after 60 earlier held-out observations, weights are selected by prior mean log loss, then Brier score, then a deterministic weight tie-break. The next event alone receives those weights. Evaluation stores the complete grid, weight-selection counts, and first/last history fingerprints as the `chronological_ensemble` benchmark. Ensemble evidence remains a challenger comparison; it cannot alter production predictions or unlock signals without a separately trained, versioned, and validated model path.

## Value And Confidence

For model probability `p` and offered decimal odds `o`:

```text
model_fair_odds = 1 / p
expected_value = p * o - 1
probability_edge = p - market_fair_probability
```

Signal strength also depends on uncertainty, calibration, sample size, price movement, freshness, input completeness, and model regime. An estimated edge smaller than its uncertainty cannot produce a strong `VALUE` signal.

Signal generation is point-in-time and provenance-bound. It requires a non-demo `calibrated` evaluation whose test window ends no later than the prediction input cutoff, and the prediction must apply that exact evaluation's accepted pre-cutoff probability calibrator. For each exact market definition, it uses the latest complete non-demo snapshot per bookmaker, excludes stale bookmakers from consensus whenever fresh snapshots exist, averages proportional de-vig probabilities for market consensus, and selects the best offered price separately. Expected value is `model_probability * offered_odds - 1`; a strong signal also requires the same calculation to remain positive at the stored lower probability bound. Material price movement, stale odds, weak calibration, or inadequate venue history downgrades or blocks the classification.

## Arbitrage

For a verified exhaustive partition with best compatible prices `o_i`, gross theoretical arbitrage requires `sum(1 / o_i) < 1`. OddsQuant does not combine overlapping selections, mismatched lines, different periods, inconsistent currencies, or incompatible settlement rules.

The practical calculation applies configured stake taxes, winnings taxes, payout withholding, commissions, fixed fees, minimum and maximum stakes, stake increments, a total budget, and rounded dutching. Tax and constraint currencies must match the market; currency conversion costs and price haircuts are not inferred. Unknown or stale tax rules or stake limits, stale odds, demo provenance, and non-positive worst-case net profit block an executable classification. Profit is not described as guaranteed before every required leg is accepted and honoured under the assumed rules.

## Bet Builder Dependence

Correlated legs are not multiplied as if independent. Supported football combinations are evaluated by summing cells in the modelled scoreline distribution that satisfy every leg. Unsupported player or event combinations remain blocked until a defensible joint model exists.

## Backtesting

Backtests use chronological train, validation, and test windows with walk-forward prediction. Each observation links the exact prediction and odds snapshot available at that time. Final lineups, corrected results, later injury confirmation, closing prices, and other post-cutoff evidence cannot enter an earlier prediction.

Reported predictive metrics include Brier score, log loss, calibration error, and bucketed calibration. Strategy metrics include signal count, hit rate, ROI, yield, profit in units, closing-line value, maximum drawdown, and profit factor, split by league, bookmaker, market, odds range, and favorite/underdog status. Benchmarks include market vig-free probability and basic football models.

Synthetic runs validate software behavior only. They must be labelled and cannot be presented as real performance.
