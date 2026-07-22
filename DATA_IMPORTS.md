# Permitted Data Import Receipts

This file records reproducible public-source acquisitions used in local development. Raw files and the local database remain unversioned. A receipt is evidence of source identity and licence, not a claim of accuracy, representativeness, model quality, or profitability.

## OpenFootball Premier League results

Source: [openfootball/football.json](https://github.com/openfootball/football.json)  
Licence: [CC0 1.0](https://github.com/openfootball/football.json/blob/master/LICENSE.md)  
Provider classification: `open_data`, non-demo  
Observation policy: each completed season snapshot uses its pinned Git commit timestamp as `settled_at`, `observed_at`, and `source_updated_at`. No earlier per-match availability is inferred.

| Dataset | Source commit | Source updated | SHA-256 | Rows | Local import |
| --- | --- | --- | --- | ---: | --- |
| `2022-23/en.1.json` | `74f91dec7bc4c1ff3cd9f69efd756628498c5b1d` | `2025-03-27T20:52:42+01:00` | `8d09f0f9846981626cdfec48903e1f21e7c79aabe6f92535c9e092e8e79b808b` | 380 | Completed 2026-07-22 |
| `2023-24/en.1.json` | `74f91dec7bc4c1ff3cd9f69efd756628498c5b1d` | `2025-03-27T20:52:42+01:00` | `03e13eafbf78dfe00d7e89dd3bf6643986eb6e8fd86c7664aeb8c5bc0bed88d0` | 380 | Completed 2026-07-22 |
| `2024-25/en.1.json` | `6a225eabc8be1f7e354faa55befe790fea93332d` | `2025-06-01T05:26:17Z` | `81c472577b20c1440d2e0899e5e774777a151dbe6fc93c6ccf49af309ec65a95` | 380 | Completed 2026-07-22 |

## Odds-API.io pre-match odds

Source: [Odds-API.io](https://odds-api.io/)

Terms: [Odds-API.io terms](https://odds-api.io/terms)

Provider classification: `licensed_api`, non-demo

Collection policy: pending football events in the Premier League, UEFA Champions League,
and UEFA Conference League (main and qualification feeds) within a 35-day window, capped
at the nearest 30 events per feed. Only complete source-timestamped pre-kickoff full-time
1X2 snapshots and Novibet regulation-time corner totals are accepted. No closing status is
inferred. Player markets are not ingested.

| Local import | Scope | Bookmaker snapshots | Prices | Bookmaker/market coverage | Closing snapshots |
| --- | --- | ---: | ---: | --- | ---: |
| 2026-07-22 | Premier League | 10 | 30 | Pamestoixima 1X2 only | 0 |
| 2026-07-23 | Premier League + Conference League qualification | 67 | 173 | Pamestoixima: 11 1X2; Novibet: 28 1X2 + 28 corner totals | 0 |

The licensed raw response and local database are not versioned. The receipt records only
the reproducible request scope, source terms, normalized counts, and observed coverage.
