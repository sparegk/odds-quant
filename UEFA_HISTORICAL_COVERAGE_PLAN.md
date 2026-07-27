# UEFA Qualification Historical Coverage Plan

## Decision

Keep live UEFA baseline prediction and research activation fail closed. No additional lawful,
identity-compatible historical qualification file is currently available from the approved
source, so this checkpoint does not import results, retrain a model, lower a threshold, or
promote an evaluation.

The approved source is the [OpenFootball Champions League repository](https://github.com/openfootball/champions-league),
which identifies its data as CC0-1.0 and includes Champions League, Europa League, and Conference
League datasets. Existing local imports are pinned to commit
`abfaeddc2ee3d14f99ecc163c9ddb46cb4d67cef`, committed at
`2026-07-02T15:56:11Z`, with the provider terms URL pointing to the repository
[license](https://github.com/openfootball/champions-league/blob/master/LICENSE.md).

At that pinned source state, explicit qualification files exist for 2024/25 and 2025/26. The
2023/24 and earlier season directories expose `cl.txt`, `conf.txt`, and `el.txt`, but not separate
`clq.txt` or `confq.txt` files. Main-tournament files must not be relabeled, split by inference, or
mixed into qualification competition families.

## Current evidence

The local database contains 277 permitted, source-timestamped OpenFootball qualification finals:

| Exact competition | Season | Finals |
| --- | ---: | ---: |
| UEFA Champions League Qualification | 2024/25 | 55 |
| UEFA Champions League Qualification | 2025/26 | 49 |
| UEFA Conference League Qualification | 2024/25 | 96 |
| UEFA Conference League Qualification | 2025/26 | 77 |

The source timestamp for all four imported files is `2026-07-02T15:56:11Z`, before the live model
cutoffs discussed below. Raw normalized rows, content hashes, atomic import jobs, exact competition
names, seasons, and provider provenance remain persisted locally. No result publication time is
invented: the pinned file commit is the first asserted availability time.

Scheduled Odds-API.io job 64 refreshed predictions at cutoff
`2026-07-26T21:22:54.662133Z`. Its 42 eligible upcoming priced UEFA qualification events split as
follows:

| Baseline result | Events | Evidence |
| --- | ---: | --- |
| Created | 3 | At least one same-competition home result for the home team and one away result for the away team |
| Skipped at home-history check | 33 | No same-competition home result for the home team |
| Skipped at away-history check | 6 | Home check passed, but no same-competition away result for the away team |

The three baseline outputs were Riga FC–FK Vardar Skopje, NK Celje–KF Egnatia Rrogozhine, and
Zira FK–Paide Linnameeskond. The active baseline models require one venue-specific match to emit a
research output. This is separate from the signal policy: all 42 events had fewer than eight
venue-specific matches on at least one required side, so none can pass the conservative research
activation sample gate. The eight-match gate must not be lowered.

## Source acceptance gate

A future historical file may enter an import checkpoint only when every item below is true:

1. The source is legally approved for the intended storage and use. Prefer the existing CC0
   repository; adding a paid, restricted, or unapproved provider requires a separate approval.
2. The file path explicitly identifies the exact competition, such as `{season}/clq.txt` or
   `{season}/confq.txt`. Stage identity may not be inferred from a combined or main-stage file.
3. The full immutable source commit, dataset path, file content SHA-256, file-specific commit time,
   license URL, and acquisition time are recorded before normalization.
4. The source timestamp is at or after every accepted kickoff and strictly before any model cutoff
   that consumes the results. Missing or guessed timestamps block the file.
5. Kickoff timezone semantics are documented for that file. An undocumented timezone blocks the
   import; it must not be guessed from the competition name or venue country.
6. Only unambiguous regulation-time finals are accepted. Rows marked after extra time, penalties,
   awarded, incomplete, duplicated, or without a published kickoff time remain excluded by the
   normalizer. The accepted set must be complete relative to the normalizer contract and imported
   atomically.

## Team identity gate

Team names are global football identities in the current schema, so aliases can join seasons only
after explicit review:

1. Generate candidate source-to-canonical mappings for review; never apply fuzzy matching during
   import.
2. Require stable evidence that both names identify the same club. Similar names, city names,
   reserve teams, successor clubs, and renamed legal entities remain distinct until verified.
3. Store accepted mappings in `backend/config/openfootball_team_aliases.json` and cover each new
   mapping with a deterministic normalizer/import test.
4. Reject alias collisions, many-to-one ambiguity, empty names, or a mapping that would make an
   event self-opposed.
5. Recompute venue counts after alias review. Do not treat a new alias as evidence that historical
   matches existed; it only links already accepted source rows to the correct stable identity.

## Chronological training and evaluation gate

Champions League Qualification and Conference League Qualification remain separate exact
competition families across seasons. Domestic leagues, UEFA main stages, Europa League, and the
other qualification competition must not contribute observations to either fitted model.

After a newly accepted season is imported:

1. Recalculate per-team home and away counts at an explicit cutoff using only final results whose
   `observed_at` and `settled_at` are no later than that cutoff.
2. Train a new immutable model version per exact competition family. Retain the full contributing
   competition ID list, cutoff, feature version, fingerprint, sample size, and configured minimum
   history.
3. Evaluate chronologically: train only on earlier source-available results and replay a later
   held-out period at the configured pre-kickoff lead. Persist coverage and every exclusion reason.
4. Keep the model `unvalidated` unless the existing stored calibration policy passes on qualifying
   competition data. A good training fit, three emitted outputs, or a domestic/main-stage result is
   not calibration evidence.
5. Keep research candidates non-executable unless each compared team has at least eight
   venue-specific observations at the candidate cutoff and every existing price, calibration,
   edge, uncertainty, and provenance gate also passes.

## Recheck cadence and exit criteria

- Recheck the approved repository only when a new immutable source revision advertises explicit
  qualification files. Do not poll or scrape it on the provider scheduler cadence.
- Before import, produce a sanitized manifest and dry-run summary containing paths, hashes,
  timestamps, accepted counts, bounded exclusion counts, and alias-review counts, but no licensed
  raw payloads.
- Add deterministic tests for any parser, alias, provenance, training, or evaluation behavior
  change before importing into the configured database.
- This coverage checkpoint is complete only when a focused commit records the manifest/tests and
  the atomic import succeeds. Research activation remains a separate later checkpoint requiring a
  qualifying chronological evaluation and the unchanged eight-match venue gate.

Until those conditions are met, continued source-timestamped odds collection is useful evidence,
but time alone and repeated price snapshots do not repair historical result depth.
