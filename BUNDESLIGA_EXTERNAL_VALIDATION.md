# Bundesliga External Validation

## Dataset selection checkpoint

The next untouched probability-validation family is `Bundesliga / Germany`. This choice was
made before importing the files into the configured database or calculating any model score on
the holdout.

OpenFootball publishes the selected files under CC0 1.0. Raw source files remain temporary and
must not be committed. Imports must use the existing atomic OpenFootball adapter and retain the
exact source commit, source publication timestamp, repository-relative path, season, competition,
country, and `Europe/Berlin` timezone.

| Role | Dataset path | Source commit | Published | Git blob | Final rows |
| --- | --- | --- | --- | --- | ---: |
| Training | `2022-23/de.1.json` | `0b539b297fd18a5043ffd6d02188124fd6205d20` | `2024-09-19T19:16:39+02:00` | `373f4811b584727fce49cde8989a02bdbafc0d53` | 306 |
| Training | `2023-24/de.1.json` | `0b539b297fd18a5043ffd6d02188124fd6205d20` | `2024-09-19T19:16:39+02:00` | `9c6a3b97ef02539482ac9855ce10766c96cf5673` | 306 |
| Untouched holdout source | `2024-25/de.1.json` | `bd189ea365936c8e9c6c64261fcdd608e3cec3c5` | `2025-05-21T05:26:48Z` | `9921b1d8485429913ff6d161500beb519d8b0e51` | 306 |

## Locked boundary

- Exact family: `football / Bundesliga / Germany`; do not pool another German division or cup.
- Evaluation window: `2024-09-20T00:00:00Z` through `2025-05-18T00:00:00Z`.
- Candidate events in that window: 279, before venue-history and other pre-registered eligibility
  checks.
- Earlier complete results available at the locked boundary: 612.
- Minimum training floor: 200 results.
- Minimum untouched evaluation observations: 200.
- Minimum eligible-event coverage: 90%.
- Prediction lead: 60 minutes.
- The existing v6 policy, calibration candidates, nested candidate grid, ensemble grid, and
  bootstrap rules must be frozen in a separate receipt before holdout metrics are inspected.

This checkpoint authorizes local atomic import and eligibility auditing only. It does not promote
a model or authorize value signals, CLV, staking, ROI, or profitability claims.

