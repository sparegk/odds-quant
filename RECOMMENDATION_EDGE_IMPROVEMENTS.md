# Recommendation and edge improvements

Each box is implemented, fully verified, committed, and pushed separately. Recommendations remain
conditional decisions from timestamp-valid evidence, never guarantees.

- [x] Require exact fresh quote identity, sourced costs, valid rounded stakes, and positive lower
  net EV before a candidate can appear as an executable recommendation.
- [ ] Add an actionable minimum-odds threshold after costs so users can reject a moved price.
- [ ] Add a decomposed recommendation-quality score that keeps probability reliability, market
  disagreement, price freshness, and net economics separate.
- [ ] Add prospective recommendation tracking with immutable decision-time snapshots and explicit
  closing-line and settlement status.

## Executable recommendation rule

A single-selection recommendation must retain the exact stored VALUE signal snapshot as the current
fresh quote. Its market currency must be known, its tax and stake evidence must pass the existing
source/cutoff/freshness gates, and the reference stake must satisfy minimum, maximum, and increment
rules. Ranking uses lower net EV per cash-outlay unit multiplied by the independently calculated
confidence score. Missing costs or lower net EV at or below zero suppress the recommendation even
when pre-cost EV is positive.

Builder quotes remain visible for research but cannot be recommendations until their exact quote,
bookmaker identity, currency, settlement, and cost evidence can be joined and validated.
