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

## Family one receipt: Eredivisie

Atomic jobs `193` through `195` created 918/918 pinned results under competition IDs `29` through
`31`. Model 9, `pq1-c31-202409200000-4c7ae9e0`, trained on exactly 612 publication-safe results.
Immutable run 8 has fingerprint
`40d196d536580d5af7153af345aaf43d075760e817e16ddd41b4e24acc65e551`.

Strict Poisson evaluated only 96/263 candidates and failed observation, coverage, ECE, paired
uniform, and recalibration gates. The cold-start candidate evaluated 263/263, including 167
league-prior events. Its Brier score was `0.62764`, log loss `1.04458`, and ECE `0.04460`; paired
95% upper differences against uniform were `-0.00851` Brier and `-0.01218` log loss. Every frozen
family gate passed, so the family decision is `probability_validated_candidate`.

The combined decision remains pending Primeira Liga. Model 9 remains unvalidated; no automatic
promotion, market acquisition, signal, staking, or profitability work is authorized.

## Family two receipt: Primeira Liga

Atomic jobs `197`, `198`, and `200` created 918/918 pinned results under competition IDs `32`
through `34`. Model 10, `pq1-c34-202409200000-71feb737`, trained on exactly 612 publication-safe
results. Immutable run 9 has fingerprint
`353bc4310da6b91615e76265aefd25e290c9545fa1d6052aa99a2e6472565821`.

Strict Poisson evaluated only 78/261 candidates and failed the frozen primary gates. The cold-start
candidate evaluated 261/261, including 183 league-prior events. Its Brier score was `0.64654`, log
loss `1.07002`, and ECE `0.02759`; paired 95% upper differences against uniform were
`-0.000027` Brier and `-0.001642` log loss. The margins are narrow but strictly pass the rules
frozen before either replay. Every family gate passed.

## Combined decision

Both preselected families independently returned `probability_validated_candidate`, so deterministic
policy `cross-league-cold-start-confirmation-v1` returns `replicated_probability_candidate`. No
metrics were pooled and no family was substituted.

This classification validates the pre-registered cold-start candidate across the two-family
sequence. It does not rewrite the strict-primary run decisions or automatically promote stored
models 9 and 10, which remain unvalidated. It also does not authorize market acquisition, player
features, signals, staking, ROI, or profitability claims. A separately reviewed activation and a
new explicitly versioned model path are required next.
