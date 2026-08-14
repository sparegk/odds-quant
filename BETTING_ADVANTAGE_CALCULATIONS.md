# Betting advantage calculation details

This track improves the explanation and robustness of descriptive betting calculations without
changing the frozen `explainable-value-v1` policy or authorizing a recommendation. Every value
remains conditional on timestamp-valid pre-kickoff model and market evidence.

## Calculation sequence

- [x] Expose the pre-cost advantage decomposition: best-price break-even probability, model and
  conservative fair odds, model-versus-market edge, model-versus-offered-price edge, model and
  market uncertainty widths, EV per unit, and whether both conservative uncertainty tests pass.
- [ ] Add net EV after sourced currency, settlement, tax, fee, commission, stake-limit, and
  rounding rules. Missing or stale cost evidence must return unavailable, never zero cost.
- [ ] Add calibration reliability details using chronological out-of-sample evidence. Keep
  probability calibration separate from market-edge and return validation.
- [ ] Add pre-registered de-vig sensitivity views. The frozen Pamestoixima replay retains its
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
- The pre-cost uncertainty test passes only when conservative market edge and lower pre-cost EV
  are both strictly positive. It is descriptive and never substitutes for costs, closing-line
  evidence, calibration, or prospective validation.
