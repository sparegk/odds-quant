# Pamestoixima-only prospective edge validation

This is a separate single-book study for Allwyn / Pamestoixima while Novibet acquisition is
parked. It does not modify, replace, or satisfy the frozen two-book market-consensus contract in
`MARKET_EDGE_VALIDATION.md`.

## Fixed sequence

- [x] Run the prospective collector as a durable per-user scheduled task that starts at logon,
  restarts on failure, prevents duplicate task instances, uses production mode, and stores no
  credentials or logs in the repository.
- [x] Freeze the full Premier League 2026/27 cohort before its earliest stored kickoff and before
  inspecting any cohort outcome, CLV, or return. Bind model 12, complete full-time 1X2 evidence,
  the existing explainable-value policy, fixed coverage/sample thresholds, moving-block bootstrap
  intervals, and the original probability-activation hashes.
- [x] Add one typed, outcome-blind coverage audit through the Pamestoixima API endpoint and CLI
  command. It reports only aggregate single-book acquisition fields, cannot authorize
  market-consensus validation, and exits 4 while any frozen single-book blocker remains.
- [ ] Collect complete Pamestoixima 1X2 snapshots between 24 hours and 60 minutes before kickoff
  for at least 160 events and 80% of the fixed 380-event cohort.
- [ ] Acquire explicitly designated Pamestoixima closing snapshots with original source timestamps
  before kickoff for at least 80% of the cohort. Proximity to kickoff must never infer closing.
- [ ] Configure sourced currency, settlement, tax, fee, stake-limit, and rounding evidence.
  Unknown or stale cost evidence blocks each observation.
- [ ] Wait until the complete fixed cohort is final, then compare the activated model with the
  proportional de-vigged Pamestoixima benchmark on identical events. This is not market consensus.
- [ ] Replay the unchanged explainable-value policy once. Require at least 100 qualified bets and
  positive 95% lower confidence bounds for both mean same-book CLV and net ROI after costs.
- [ ] Research staking only if every preceding single-book gate passes. A pass still cannot be
  reported as two-book market-consensus validation.

The machine-readable source of truth is
`backend/config/pamestoixima_edge_validation_v1.json`. Outcome-blind aggregate coverage audits
are allowed during collection; interim prices, selections, teams, thresholds, CLV, and returns
must not be inspected for decisions.
