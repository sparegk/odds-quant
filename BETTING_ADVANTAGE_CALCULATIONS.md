# Betting advantage calculation details

This track improves the explanation and robustness of descriptive betting calculations without
changing the frozen `explainable-value-v1` policy or authorizing a recommendation. Every value
remains conditional on timestamp-valid pre-kickoff model and market evidence.

## Calculation sequence

- [x] Expose the pre-cost advantage decomposition: best-price break-even probability, model and
  conservative fair odds, model-versus-market edge, model-versus-offered-price edge, model and
  market uncertainty widths, EV per unit, and whether both conservative uncertainty tests pass.
- [x] Add net EV after sourced currency, settlement, tax, fee, commission, stake-limit, and
  rounding rules. Missing or stale cost evidence must return unavailable, never zero cost.
- [x] Add calibration reliability details using chronological out-of-sample evidence. Keep
  probability calibration separate from market-edge and return validation.
- [x] Add pre-registered de-vig sensitivity views. The frozen Pamestoixima replay retains its
  proportional method; robustness views cannot rewrite that primary result.

## Definitions

- Break-even probability is `1 / offered decimal odds`.
- Market edge is model probability minus the equal-bookmaker consensus after proportional and
  power de-vigging.
- Conservative market edge is the model lower probability bound minus the highest eligible
  market estimate across bookmakers and de-vig methods.
- Price edge is model probability minus the raw break-even probability of the offered price. It
  includes price and margin effects and therefore must not be called pure model edge.
- Pre-cost EV per unit is `model probability * offered decimal odds - 1`.
- Lower pre-cost EV substitutes the model lower probability bound.
- Cost-adjusted EV is expected net profit divided by cash outlay at a displayed, valid reference
  stake. Cash outlay includes the stake, stake tax, and fixed fee; winning payout deducts winnings
  tax, payout withholding, and commission. The lower value substitutes the model lower bound.
- The reference stake targets 100 currency units, rounds to the configured stake increment, and
  respects the sourced minimum and maximum. Showing the stake is mandatory because fixed fees make
  net ROI stake-dependent.
- Currency and settlement identity come from the exact stored market. Tax mappings must be active,
  verified before the calculation cutoff, effective for that currency, sourced, and no more than
  365 days old. Stake constraints must be sourced before the cutoff and no more than 1,440 minutes
  old. Any failed gate returns unavailable values and explicit blockers; it never assumes zero cost.
- The pre-cost uncertainty test passes only when conservative market edge and lower pre-cost EV
  are both strictly positive. It is descriptive and never substitutes for costs, closing-line
  evidence, calibration, or prospective validation.
- The cost-adjusted uncertainty test passes only when conservative market edge and lower net EV
  are both strictly positive. It remains research-only and cannot create or modify a VALUE signal.
- Calibration reliability is read only from the evaluation run explicitly referenced by the stored
  prediction. The run must belong to the same model version, be completed, non-demo, probability-
  validated, and end before the prediction input cutoff; the calibrator fit cutoff must also predate
  that input cutoff.
- Expected calibration error, Brier score, and log loss come from the run's overall temperature-
  scaled out-of-sample result. Missing or invalid metrics block reliability instead of being
  replaced with optimistic defaults.
- Calibration reliability describes probability quality only. Its response explicitly excludes
  market-edge evidence and betting-return evidence, which remain independently gated.
- De-vig sensitivity is pre-registered to exactly two methods in fixed order: proportional and
  power. Each method reports its equal-bookmaker consensus, range, central model edge, and
  conservative lower-bound edge.
- The sensitivity conclusion is stable only when both the central-edge sign and conservative-edge
  sign agree across the two methods. A disagreement is displayed as method-sensitive rather than
  selecting the more favorable result.
- Proportional remains labeled as the frozen replay primary and power remains sensitivity-only.
  These views cannot rewrite the replay, historical results, or VALUE signals.
