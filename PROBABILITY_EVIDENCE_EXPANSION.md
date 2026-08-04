# Probability Evidence Expansion Checkpoint

## Decision

The 2025/26 Premier League holdout is now development evidence because its results informed the calibration, nested-selection, and ensemble specifications. It must not be replayed under those new rules and presented as untouched validation. No currently stored exact competition family has enough later permitted results for a fresh probability-validation run.

This checkpoint authorizes no model promotion, value signal, CLV, staking, ROI, or profitability claim.

## Aggregate audit

The read-only audit was run on 2026-08-04 against final, non-demo events with stored final results. Counts use distinct canonical event IDs and retain exact competition name/country families; qualification and main competitions are not pooled.

| Exact competition family | Stored seasons | Final events | Latest kickoff | Fresh holdout decision |
| --- | ---: | ---: | --- | --- |
| Premier League / England | 4 | 1,520 | 2026-05-24 | Blocked: zero events after the already-used 2026-05-27 evaluation cutoff. |
| Cypriot First Division / Cyprus | 1 | 188 | 2025-05-18 | Blocked: below the 200-match training floor and cannot supply a separate holdout. |
| Erovnuli Liga / Georgia | 1 | 167 | 2024-12-08 | Blocked: below the 200-match training floor and cannot supply a separate holdout. |
| UEFA Champions League / International | 2 | 113 | 2026-05-06 | Blocked: insufficient exact-family history for training plus holdout. |
| UEFA Champions League Qualification / International | 2 | 104 | 2025-08-27 | Blocked: insufficient exact-family history for training plus holdout. |
| UEFA Conference League Qualification / International | 2 | 173 | 2025-08-28 | Blocked: below the 200-match training floor and cannot supply a separate holdout. |
| UEFA Europa League Qualification / International | 2 | 91 | 2025-08-28 | Blocked: insufficient exact-family history for training plus holdout. |
| Other stored exact families | 1 each | 32–88 | 2025 or earlier | Blocked: insufficient exact-family history for training plus holdout. |

The configured database retains four historical evaluation runs. The two current non-demo probability-policy runs both end at `2026-05-27T00:00:00Z`; Poisson run 3 and Elo run 4 are `probability_validation_failed` and `insufficient_market_evidence`. No later non-demo evaluation receipt exists.

## Audit contract

A candidate fresh validation window must satisfy all of the following before execution:

- Results are final, non-demo, permitted, and retain original observation/correction timestamps.
- Training and evaluation stay inside the exact canonical sport/name/country competition family.
- At least 200 results precede the locked evaluation window.
- At least 200 candidate results are untouched by policy, feature, hyperparameter, calibration, or ensemble design decisions.
- The run retains at least 90% eligible-event coverage after venue-specific team-history checks.
- The policy and candidate grids are frozen before inspecting the new outcomes.
- Market/value validation remains separate and blocked without compatible historical price evidence.

## Exit criteria

Re-run this audit only after importing new permitted final results with source timestamps. A new probability-validation replay becomes eligible when either:

1. the Premier League has at least 200 final candidate events strictly after the current locked cutoff; or
2. another exact competition family has enough chronological depth for at least 200 prior training results plus at least 200 untouched held-out candidates.

Do not lower the thresholds, pool different UEFA competition identities, or reuse the examined 2025/26 outcomes to clear this checkpoint.
