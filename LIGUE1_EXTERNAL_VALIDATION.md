# Ligue 1 External Validation

## Dataset selection checkpoint

The next untouched probability-validation family is `Ligue 1 / France`. This selection was made
before importing any of the files into the configured database or calculating any model score on
the holdout. OpenFootball publishes the selected files under CC0 1.0. Raw source files remain
temporary and must not be committed.

La Liga and Serie A were screened first and rejected because their latest pinned 2024/25 JSON
files contain only 370 of 380 final scores. No partial feed was imported. Ligue 1 contains all 306
final scores, has 686 complete prior results, and supplies 270 holdout candidates after the locked
boundary.

| Role | Dataset path | Source commit | Published UTC | Git blob | Final rows |
| --- | --- | --- | --- | --- | ---: |
| Training | `2022-23/fr.1.json` | `0b539b297fd18a5043ffd6d02188124fd6205d20` | `2024-09-19T17:16:39Z` | `66703493e83dbd16b18f0a891a78a3b3a91b71a1` | 380 |
| Training | `2023-24/fr.1.json` | `440950e9c855556cc5023a3ea598feeed7c08722` | `2024-08-28T10:00:05Z` | `9e42eb9982de8d3652242edf198b4197cdbbaef0` | 306 |
| Untouched holdout | `2024-25/fr.1.json` | `bd189ea365936c8e9c6c64261fcdd608e3cec3c5` | `2025-05-21T05:26:48Z` | `8bc6ec90c62fa423386ec60473cfa6236419a636` | 306 |

Imports must use the existing atomic OpenFootball adapter and retain the exact dataset path,
commit, original publication timestamp, competition `Ligue 1`, country `France`, season, and
`Europe/Paris` timezone. The source SHA-256 values are frozen in the machine-readable manifest.

## Locked experiment

`backend/config/ligue1_external_validation_v1.json` is the pre-replay contract. It binds the
experiment to implementation commit `f722ca1`, a Poisson primary trained from
`2022-08-01T00:00:00Z` through `2024-09-20T00:00:00Z`, and the untouched window from that boundary
through `2025-05-19T00:00:00Z` exclusive. No Ligue 1 model or evaluation exists yet.

The cold-start candidate uses league-prior expected goals for unseen teams. Before scoring, every
1X2 probability is widened toward uniform using only pre-kickoff venue counts:

`reliability = (min(home venue matches, 8) + min(away venue matches, 8)) / 16`

`widened probability = reliability × raw probability + (1 - reliability) / 3`

Calibration is frozen to identity after widening; it has no outcome-fitted parameter. The replay
must evaluate all candidates, use 10 ECE bins, and compare Brier and log loss with uniform through
the deterministic 2,000-resample 95% moving-block bootstrap. Qualification requires at least 200
observations, 90% coverage, ECE at most 0.08, and both paired upper bounds below zero.

The existing strict primary policy remains independent. Even if the cold-start candidate passes,
the run cannot automatically promote the stored model or authorize market acquisition, signals,
staking, ROI, or profitability claims. Activation would require a separately reviewed model
version that preserves this exact receipt. No threshold or formula may be retuned after inspection.

## Replay handoff

The temporary files are in `C:\Users\Administrator\AppData\Local\Temp\odds-quant-ligue1-validation`.
First run the manifest test, then import all three pinned files atomically. Audit 686 pre-boundary
results and exactly 270 candidates before training. Train the 2024/25 competition with the frozen
primary arguments, retain its model ID, and run:

`py -m app.cli evaluate-model MODEL_ID 2024-09-20T00:00:00+00:00 2025-05-19T00:00:00+00:00 --prediction-lead-minutes 60 --minimum-training-matches 200 --calibration-bins 10 --include-cold-start-validation`

Record every strict-primary and cold-start gate without retuning. The holdout becomes examined as
soon as the immutable run is written.

## Untouched replay receipt

The replay completed on 2026-08-10 without changing the registered specification. Model 8,
`pq1-c28-202409200000-ecd3f939`, retained exactly 686 leakage-safe training results. Immutable run
7 has fingerprint `28a2324ff783d412afbfe030d21f690892a5e2ac3f301e62b1896cea37b77471`.

The strict primary evaluated 161 of 270 candidates (59.63% coverage), with Brier `0.60680`, log
loss `1.01277`, and ECE `0.08824`. It passed both paired uniform intervals but failed the 200-event,
90%-coverage, and 0.08-ECE gates.

The pre-registered cold-start candidate evaluated all 270 candidates, including 109 league-prior
events. Its Brier score was `0.61341`, log loss `1.02224`, and ECE `0.08692`. The paired
cold-start-minus-uniform 95% upper differences were `-0.02685` for Brier and `-0.03721` for log
loss. Observation count, coverage, non-demo provenance, identity calibration, and both paired
intervals passed; ECE failed the frozen 0.08 threshold. Its decision is `insufficient_evidence`.

This holdout is now examined. Model 8 remains unvalidated on both tracks, and no retuning, market
acquisition, signal, player-feature, staking, ROI, or profitability work is authorized by this run.
