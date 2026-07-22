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
