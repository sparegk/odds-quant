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

## Import receipt

The configured local database imported all three pinned files atomically on 2026-08-04. Raw files
remain outside the repository and the database remains unversioned.

| Import job | Season | Received | Imported | Created | Stored raw SHA-256 |
| ---: | --- | ---: | ---: | ---: | --- |
| 158 | 2022/23 | 306 | 306 | 306 | `cf914cd9cecb7bcd02caa542cd2501d02e28b39d5629f8f963e700ec9fb10190` |
| 159 | 2023/24 | 306 | 306 | 306 | `4bcc9688cea2652f99d55c030791ce172cf1bc434ffc951f7c1186e79992c067` |
| 160 | 2024/25 | 306 | 306 | 306 | `27267088236f322f77f06cbf06c89e23e3b0bc713542552d6a714d3ac1afbae0` |

A post-import database audit confirmed 918 final non-demo Bundesliga results, the exact source
observation timestamps listed above, and 279 final candidates in the locked holdout. All 16
OpenFootball and atomic result-import tests passed.

## Frozen experiment receipt

`backend/config/bundesliga_external_validation_v1.json` is the machine-readable pre-replay
contract. It freezes a Poisson primary trained from `2022-08-01T00:00:00Z` through the locked
boundary with a 200-match floor, eight venue-specific matches per team, and shrinkage 5. The
evaluation uses the existing v6 policy, 60-minute lead, 10 calibration bins, 2,000-sample 95%
moving-block bootstrap, development-selected calibration with identity fallback, six-candidate
nested grid, and 12-member Poisson/Elo/Dixon-Coles ensemble grid.

A deterministic test binds the manifest to the implementation constants. The implementation
commit is `28ce95ebc2a5c51ef89a2ea6dfef6ef37382e658`. Any specification change requires a new manifest
and a new untouched dataset; it cannot be justified from this holdout's metrics.
