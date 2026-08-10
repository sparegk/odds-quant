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

## Immutability

Models 9 and 10 remain `unvalidated`; runs 8 and 9 remain `insufficient_evidence` under the strict
primary path. The two holdouts cannot be reused for retuning, and the frozen v2 math cannot be
changed under this contract. A behavior change requires a new version and new chronological
evidence.
