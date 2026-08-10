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
