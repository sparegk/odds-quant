# Cold-start v2 probability activation

## Decision

Contract `cold-start-v2-probability-activation-v1` approves one new, explicitly versioned
probability-only model path after the two preselected cross-league families independently passed.
It does not modify models 9 or 10 and does not reinterpret strict runs 8 or 9.

The evidence is receipt-bound to policy `cross-league-cold-start-confirmation-v1`, selection
`eredivisie-primeira-2024-25-cold-start-v2`, and the exact Eredivisie and Primeira Liga evaluation
fingerprints. Any evidence drift fails closed.

## Authorized path

The new row must use model kind `poisson_team_strength_cold_start_v2`, version prefix `pqc2`, and
feature version `final-score-home-away-v4-cold-start-v2`. Prediction behavior is pinned to the
validated v2 method: publication-safe Poisson training, fitted league priors for missing venue
strength, an eight-match venue-history reliability target, deterministic widening toward uniform,
and identity calibration after widening.

The new path may create pre-kickoff probability outputs. It starts with probability status
`probability_validated` and market status `insufficient_market_evidence`. This contract does not
authorize automatic value signals, market validation, player features, staking, ROI, or
profitability claims. Those remain separate gates.

Only `MATCH_RESULT` probabilities are persisted by this activated path because that is the target
validated by the two-family replay. Other score-matrix-derived markets do not inherit this
probability evidence.

## Immutability

Models 9 and 10 remain `unvalidated`; runs 8 and 9 remain `insufficient_evidence` under the strict
primary path. The two holdouts cannot be reused for retuning, and the frozen v2 math cannot be
changed under this contract. A behavior change requires a new version and new chronological
evidence.

## Execution receipt

The legacy live source model 2 failed closed because it used feature version v2. A fresh strict
source, model 11 (`pq1-c5-202606020000-af71f829`), was trained with the identical publication-safe
window and hyperparameters under current feature version v3. It remains unvalidated.

Model 12 (`pqc2-c5-202606020000-7917411c`) is the resulting activated probability-only row. Live
output 232 for Arsenal FC v Coventry City verified the intended promoted-team path before kickoff:
Coventry had zero away-history, league-prior uncertainty was recorded, reliability was `0.5`, all
400 bootstrap refits succeeded, identity calibration was applied, and only `MATCH_RESULT`
probabilities were persisted. No value signal was created.

Final verification passed 302 backend tests and 78 frontend tests plus all lint, formatting,
typing, and production-build gates. Collection monitoring remained healthy with no alerts.
