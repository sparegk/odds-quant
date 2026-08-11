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

## Acquisition checkpoint: 2026-08-11

- [x] Restore prospective collection at the configured cadence without an ad hoc provider probe.
  Scheduler PID 2820 completed Odds job 309 and football-data job 310 with no monitoring alerts.
  Job 309 atomically accepted 326 prices across 69 fixtures; its Premier League slice contained
  30 complete Pamestoixima prices. Permitted Premier League snapshots increased to 1,660.
- [x] Re-audit available official historical contracts without making a paid request. The
  configured Odds-API.io finished-event response labels values as closing but lacks an original
  timestamp for each price. The separate paid Odds API provides timestamp-addressed snapshots but
  no explicit closing designation. Betfair historical data would be a separately approved
  exchange source and no file or account authorization is present.
- [ ] Complete acquisition. Only 30 of the expected 380 cohort fixtures are currently stored,
  Novibet is absent for the Premier League, no cohort result is final, and the entire store has
  zero explicit closing snapshots. These are evidence blockers, not thresholds to relax.
