# Market edge validation

## Frozen decision

Contract cold-start-v2-market-edge-validation-v1 fixes the first independent market and value
test for the activated cold-start v2 method. It is bound to activated model 12 and uses only
full-time MATCH_RESULT evidence from the complete post-activation Premier League 2026/27 cohort.
The already-examined 2025/26 outcomes cannot be reused as untouched edge evidence.

This contract does not assert that a betting edge exists. Model 12 remains
insufficient_market_evidence, automatic value signals remain disabled, and no staking, ROI, or
profitability claim is authorized.

## Fixed sequence

- [x] Freeze the cohort, evidence contract, market benchmark, value policy, CLV/return gates, and
  authorization boundary before inspecting cohort outcomes or returns.
- [ ] Acquire permitted complete 1X2 snapshots with original pre-kickoff timestamps and stable
  identities. Explicit same-bookmaker closing prices, settlement, currency, tax, fee, and
  commission provenance are required for edge evaluation; unknown fields fail closed.
- [ ] After the fixed cohort is final, replay the activated method and fixed value policy with no
  post-kickoff inputs and one deterministic candidate per event.
- [ ] Apply the paired market-score, mean-CLV, and net-ROI confidence gates. Point estimates alone
  cannot pass, and an insufficient or failed result cannot be retuned or relabelled.
- [ ] Only after every prior gate passes, freeze and validate a separate staking policy. If any
  prerequisite fails, staking remains blocked.

## Evidence boundaries

Outcome-blind aggregate coverage audits may run while collection is in progress. Interim CLV,
return, threshold, team, bookmaker, or selection analysis is forbidden because it would create an
optional-stopping or cohort-selection path. Protected bookmaker services must not be scraped, and
closing status must never be inferred from proximity to kickoff.

The machine-readable source of truth is backend/config/market_edge_validation_v1.json. Its
deterministic tests bind the contract to the activation hashes and to the implemented
market-consensus and signal-policy constants.
