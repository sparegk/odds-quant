# Cross-League Cold-Start Confirmation

## Frozen sequential policy

The league-prior cold-start Poisson v2 candidate must not be tested on competitions until one
passes. Exactly two genuinely untouched competition families must be selected, pinned, and placed
in a fixed execution order before either family produces a model score.

Each family must independently satisfy every existing candidate gate: non-demo provenance, at
least 200 observations, at least 90% coverage, ECE at most 0.08, identity-only calibration, and
paired 95% Brier and log-loss upper differences below zero against uniform. Metrics may not be
pooled across families to rescue a failed family.

The combined result is `replicated_probability_candidate` only if both families independently
return `probability_validated_candidate`. One failure fixes the combined result at
`replication_failed`. After the first replay is scored, a family cannot be replaced and a third
family cannot be added as a rescue attempt.

Even two passes do not automatically promote a stored model or authorize historical market
acquisition, player features, signals, staking, ROI, or profitability claims. A separate reviewed
activation and model version would still be required.

The machine-readable policy is `backend/config/cross_league_confirmation_policy_v1.json`. The
decision implementation is deterministic and bound to the unchanged candidate implementation
commit `f722ca1`.

## Frozen family selection

Both families were selected together before either produced a model score. Execution order is
fixed as:

1. `Eredivisie / Netherlands / 2024/25`: 612 complete prior results and 263 candidates from the
   locked `2024-09-20T00:00:00Z` boundary.
2. `Primeira Liga / Portugal / 2024/25`: 612 complete prior results and 261 candidates from the
   same boundary.

All six OpenFootball CC0 files contain 306/306 final scores. Training files are pinned to source
versions published before the boundary; holdout files are pinned to completed sources published
after their seasons. There were no existing competition, model, or evaluation records for either
family at selection time. Raw files remain temporary and uncommitted.

The commits, blobs, SHA-256 hashes, timezones, windows, hyperparameters, and fixed execution order
are registered in `backend/config/cross_league_confirmation_selection_v1.json`. After the
Eredivisie replay begins, neither family may be replaced.
