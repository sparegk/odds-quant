# Resume UEFA And Bet-Builder Coverage

## Current checkpoint

- Branch: `main`. Security, polling, cross-season modeling, canonical competition, and
  historical evaluation checkpoints through `83acb30` are pushed and passing CI.
- The prior Odds-API.io key was exposed through local `httpx` URL logging. The ignored logs
  were removed, the key was regenerated only in the ignored root `.env`, credential query
  logging is redacted, and the scheduler is restored. Never paste the replacement key into
  chat or tracked files.
- Required bookmakers are Allwyn/Pamestoixima and Novibet; the authenticated provider
  selection contains both.
- The collector covers the Premier League plus UEFA Champions League and Conference League
  main/qualification feeds within 35 days, capped at the nearest 30 events per feed.
- Complete source-timestamped pre-kickoff full-time 1X2 is accepted from either target
  bookmaker. Complete Novibet `Corners Totals` is accepted as `TOTAL_CORNERS` with the
  bookmaker-specific regulation-time settlement key.
- A 2026-07-23 local atomic collection imported 173 prices across 67 snapshots: 11
  Pamestoixima 1X2, 28 Novibet 1X2, and 28 Novibet corner-total snapshots.
- The sanitized `python -m app.cli probe-bet-builder-markets` command checked 70 upcoming
  events and found 28 timestamped Novibet `Corners Totals` markets. It observed no player
  shots or shots-on-target markets in that window.
- The probe returns aggregate counts and field names only. It cannot return player labels
  or prices, and `player_props_ingestion_enabled` is always false.
- Player shots, player shots on target, and other player props remain discovery-only. The
  repository rule blocks ingestion until stable player identity, licensed player targets,
  complete outcomes, bookmaker settlement/void rules, and deterministic chronological
  settlement tests are independently validated.
- No closing status is inferred. Coverage remains unsuitable for evaluation where final
  result depth, both-bookmaker coverage, or explicit pre-kickoff closing evidence is absent.
- Pinned CC0 Premier League results now cover 2022/23 through 2025/26 with 1,520 permitted
  finals. Current-season Poisson training can use cutoff-valid prior seasons from the exact
  same sport/name/country competition family and stores every contributing competition ID.
- Live provider competition labels are canonicalized by supported league slug. Migration
  `a13c7e9b4d20` reconciles the exact known 2026/27 aliases without fuzzy matching.
- A local 1,520-match Premier League model and pre-kickoff prediction verified the pipeline.
  The model remains `unvalidated`; it is not performance or profitability evidence.
- A separate immutable 2025/26 held-out replay evaluated 342 of 380 permitted fixtures at a
  60-minute lead (90% coverage). Poisson recorded Brier `0.6191`, log loss `1.0306`, and ECE
  `0.0707`, beating the uniform benchmark and satisfying the stored calibration policy. Elo
  (`0.6154` Brier) and Dixon-Coles (`0.6182` Brier) were both marginally better. This calibrates
  only the historical 2025/26 model version; it does not promote the separate 2026/27 model.
  No compatible historical bookmaker or closing-price benchmark was available, and no
  profitability conclusion is authorized.
- On 2026-07-24, the target-bookmaker probe returned `complete: true`, while the sanitized
  bet-builder probe checked 70 events without returning raw values or enabling player props.
  Scheduler jobs `11` through `19` then completed consecutively at the configured 15-minute
  interval without throttling or failures. Coverage reached 512 permitted snapshots: 150
  Premier League, 45 Champions League qualification, and 317 Conference League qualification.
  Only Conference League qualification currently covers both required bookmakers, and no
  competition has explicit closing snapshots.
- A separate coverage-gap review confirmed that global bookmaker selection is not per-league
  availability. The accepted provider store contains Novibet `MATCH_RESULT` only for Conference
  League qualification; Premier League and Champions League qualification currently contain
  only Allwyn/Pamestoixima. The adapter already recognizes complete timestamped Novibet `ML`
  and rejects incomplete or ambiguous outcomes deterministically. A new sanitized 70-event
  probe advertised no additional target markets, so no alias expansion or validation weakening
  is justified. Continue polling and treat these as provider-side availability gaps.
- A deterministic near-kickoff provider regression now supplies complete Novibet 1X2 beside a
  labeled player-shots market. Collection emits only the three 1X2 outcomes, excludes the
  player label, and keeps every row `is_closing=false`. Closing-line tests still require an
  explicitly stored pre-kickoff closing snapshot and exclude post-kickoff candidates.
- On 2026-07-24, both target bookmakers remained configured and a fresh sanitized 70-event
  probe advertised no player or additional team markets. Normal scheduler jobs `24` through
  `26` each observed 70 fixtures and atomically imported 105 prices across 35 snapshots.
  Monitoring after job `26` reported 10 consecutive completed jobs, no failures in the recent
  window, and 693 permitted snapshots. Champions League qualification now covers both required
  bookmakers; Premier League still lacks Novibet, and every competition still lacks explicit
  closing snapshots.
- An official provider-documentation audit found that the historical-odds endpoint labels its
  finished-event response as closing but documents no per-price source timestamp. The movements
  endpoint supplies timestamps without an explicit closing designation. Joining them would
  infer closing status, so closing ingestion remains blocked pending one response containing
  both the designation and an original timestamp strictly before kickoff.
- A sanitized historical-result audit found 143 settled UEFA qualification events, including
  two without `ft` and seven with extra-time or after-penalty structures. The provider does not
  document the football period-key semantics or a result publication/update timestamp. Import
  remains blocked rather than inferring regulation-time scores or accepting a partial feed.
- A 2026-07-24 football-data.org review found current Champions League qualification only on
  `TIER_TWO`, while Conference League qualification was `TIER_FOUR` and still cataloged a 2025
  season. Its score contract is sufficiently explicit, but plan coverage and post-cancellation
  reference restrictions are not yet compatible with approving it for both live feeds. No
  subscription or adapter registration was authorized.
- A Sportmonks review found explicit UEFA qualifying-round coverage, regulation/extra-time/
  penalty score types, correction handling, and terms that permit storage but prohibit resale.
  It remains unapproved because access is paid, no token is configured, and current provider
  documentation conflicts on whether `last_processed_at` remains in fixture responses. A
  credentialed field-only probe is required before implementation or registration.
- Adaptive provider scheduling now uses the normal 15-minute interval while fixtures are
  distant and a five-minute interval inside the final six hours before kickoff. Exact window
  and kickoff boundaries are deterministic, restarts skip premature duplicate requests, and
  every accepted price remains non-closing without explicit provider evidence.
- Provider jobs now retain sanitized per-competition bookmaker counts. Monitoring emits
  machine-readable alerts for stale success, latest or repeated failures, and bookmaker
  coverage regression between consecutive active batches. The CLI can fail automation with
  exit status `3` while returning the complete JSON evidence report.

## Next action

- On 2026-07-26, the configured local database upgraded from `d4e5f6a7b8c9` through
  `e5f6a7b8c9d0` to `f6a7b8c9d0e1`. The hidden scheduler worker was restarted from the
  migrated checkout and remained active after its startup check.
- A 2026-07-26 sanitized provider probe again returned `complete: true` for Allwyn /
  Pamestoixima and Novibet. The bet-builder probe checked 78 events, retained implemented
  Novibet `Corners Totals`, and classified Allwyn `Corners Totals` plus `Corners Totals HT`
  as discovery-only pending independent target and settlement validation. Player-prop
  ingestion remained disabled, and the probe returned no raw values.
- After the probes triggered transient provider failures, retries were held to the configured
  interval rather than looped rapidly. Odds-API.io jobs `53` and `55` then completed
  consecutively, each observing 78 fixtures and atomically importing 308/310 prices across
  107/108 snapshots. Odds-API.io and API-Football both reported healthy with no provider
  blockers; monitoring retained a warning for the earlier failures still present in its recent
  job window.
- Persisted metrics for jobs `53` and `55` each reported 42 eligible upcoming priced events,
  3 newly versioned predictions, 39 fail-closed skips, and 5 research-watchlist candidates.
  A deterministic database assertion confirmed all six recent outputs satisfy
  `inputs_as_of <= predicted_at < kickoff`.
- A post-batch watchlist audit found 5 fresh research-only candidates across Champions League
  and Conference League qualification. Every candidate retained cutoff-valid prediction and
  price evidence and was approximately two minutes old. All 5 remained blocked by missing
  qualifying chronological calibration and fewer than 8 venue-specific matches per team; 3
  also failed conservative EV, and 1 additionally missed the raw-EV and model-edge thresholds.

### Resume checkpoint: live workflow activation

Explicit fail-closed prediction skip-reason observability is now implemented. Baseline refresh
summaries and persisted provider-job metrics retain bounded aggregate reason codes whose counts
sum to `events_skipped`; raw modeling exception text and variable match counts are not persisted.
Deterministic coverage includes the missing cutoff-valid model and insufficient venue-specific
team-history paths. The restored scheduler completed fresh jobs `58` and `59`, clearing both
provider freshness blockers; the expected warning for earlier Odds-API.io failures remains until
those jobs age out of the recent-job window.

Scheduled Odds-API.io job `64` provided the first live post-deployment proof of the bounded
reason metrics: 42 eligible events produced 3 predictions and 39 fail-closed skips. The reasons
were 33 `insufficient_home_team_home_history` and 6
`insufficient_away_team_away_history`, exactly summing to the stored skip count. The preceding
scheduled job `62` failed with a sanitized `OddsApiIoError`; no rapid retry was issued.

The five activation boxes are complete and pushed as focused commits: migration/scheduler
activation `9f9ec05`, sanitized probes `5f65998`, consecutive live batches `d005fd1`, prediction
metrics `196d645`, and watchlist audit (the commit containing this checkpoint). The scheduler is
still running in the background. On the next session, start with `git status -sb`, then run
`python -m app.cli monitor-collection --fail-on-alerts` from `backend`. The expected remaining
operational condition is a temporary repeated-failure warning until the earlier probe-time
failures age out of the recent-job window; do not retry faster than the configured interval.
The skip-reason checkpoint is now complete; use the continuation checklist below rather than
repeating that work.

### Next-session continuation checklist (2026-07-27)

The monitoring surface now exposes a typed `latest_prediction_refresh` summary from the newest
completed non-demo provider job with valid persisted evidence. It includes provider-job
provenance, all aggregate refresh counts, research-watchlist availability, and only the fixed
bounded skip-reason vocabulary. Malformed, inconsistent, boolean, negative, or unrecognized
metrics fail closed. Both `GET /api/v1/data/monitoring` and `python -m app.cli
monitor-collection` return the same object. A live local CLI read selected job `64` and returned
the exact 42 eligible, 3 created, 39 skipped, 5 watchlist, and 33/6 history split. Deterministic
API, service-validation, and CLI JSON tests cover the behavior; the full backend suite passes.

- [x] Verify a scheduler-owned live Odds batch persists bounded reasons for every skipped event.
  Job `64` is the proof: 33 home-history plus 6 away-history skips equal all 39 skips. Commit and
  push this evidence before starting the next box if it is not already the tip of `main`.
- [x] Expose the latest prediction-refresh summary and bounded `skip_reasons` directly in both
  `python -m app.cli monitor-collection` and `GET /api/v1/data/monitoring`. Add deterministic API,
  service, and CLI/serialization tests. Run relevant backend checks, then make a focused commit
  and push `main`.
- [x] Use the live 33/6 reason split to create a fail-closed, lawful UEFA historical-result and
  chronological-training coverage plan or implementation checkpoint. Do not lower the minimum
  eight venue-specific matches, mix competition identities, fabricate timestamps, or register a
  paid/unapproved provider. Add deterministic tests for any code behavior, then commit and push.
  `UEFA_HISTORICAL_COVERAGE_PLAN.md` records the resulting source, identity, chronology, and
  promotion gates. The approved CC0 archive has no additional explicit qualification files before
  2024/25, so no result import or model promotion was authorized in this checkpoint.
- [ ] Keep the scheduler polling only at its configured interval until the old failure jobs,
  including sanitized failed job `62`, age out of the recent-job window. Require
  `monitor-collection --fail-on-alerts` to exit successfully, confirm target bookmaker coverage
  has not regressed, and confirm player props and inferred closing prices remain blocked. Record
  the clean live evidence in this file, then commit and push.

### In-progress scheduler recovery (2026-07-27)

PID `14120` had not survived and both providers were stale when this continuation began. The
configured hidden scheduler was restored as PID `13804`; its normal startup cycle completed
API-Football job `65` and Odds-API.io job `66`. Both providers became fresh and individually
healthy, target-bookmaker coverage emitted no regression alert, and job `66` reproduced the
bounded 42 eligible / 3 created / 39 skipped summary with the exact 33 home-history and 6
away-history split. The only remaining monitoring alert is `repeated_provider_failures`: failed
Odds jobs `62` and `52` are still inside the default last-10 window. Starting from job `66`, eight
additional successful scheduler-owned Odds intervals are required for job `62` itself to age out.
Do not restart the live process or trigger manual provider calls while it remains active.

At handoff time the hidden scheduler process was active as PID `14120`. Always verify the process
rather than assuming the PID survived. Start the next session with `git status -sb`, `git log -1
--oneline`, a process check, and `python -m app.cli monitor-collection --fail-on-alerts`. Do not
manually accelerate provider retries.

The scheduled odds workflow now refreshes cutoff-safe baseline predictions for upcoming priced
fixtures, reports research-watchlist availability, and reuses an output when the exact cutoff is
polled again. API-Football intelligence polling creates a separate
`confirmed_lineup_context_unadjusted` output only after both complete confirmed XIs have original
publication timestamps at or before the cutoff. Both lineup snapshot IDs are retained; model
probabilities remain unchanged until player-strength adjustments are independently validated.
Deterministic tests cover future-price exclusion, future-lineup exclusion, exact-cutoff
idempotency, the 60-minute stale-price boundary, and baseline/confirmed version separation.

Keep the restored scheduler collecting UEFA fixtures and supported team markets, and monitor
provider jobs for renewed throttling or coverage regressions. Do not ingest player props when
they first appear. First obtain stable provider player IDs, a licensed timestamped player
result source, and explicit bookmaker settlement rules; then add deterministic settlement and
chronological evaluation tests in a separate checkpoint.

Continue to add closing snapshots only when the provider supplies explicit source-timestamped
closing evidence strictly before kickoff.

## Resume sequence

From `backend`:

1. Run `python -m app.cli probe-target-bookmakers` and require `complete: true`.
2. Run `python -m app.cli probe-bet-builder-markets` for sanitized availability metadata.
3. Poll through the registered scheduler collector for normal atomic imports.
4. Run `python -m app.cli monitor-collection --fail-on-alerts` (or
   `GET /api/v1/data/monitoring`) after each accepted batch; require fresh consecutive jobs and
   review the embedded alerts and coverage blockers.
5. Keep all secrets, raw licensed responses, and the local database unversioned.

## Verification and commit discipline

After each completed checkbox, run the relevant tests, commit with a focused message, and
push `main`. Before release, run:

```bash
cd backend
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy app tests

cd ../frontend
npm run test
npm run lint
npm run build
npm run test:e2e
```

Do not scrape bookmaker websites, weaken atomic ingestion, fabricate historical timestamps,
infer closing flags, or enable player props before their independent validation gates pass.

## Site experience roadmap

- [x] Make Matchday the default homepage and reorganize the navigation into Matches, Research,
  Analytics, Admin, and About groups. Deterministic navigation tests, the full frontend unit suite,
  lint, production build, and Playwright workflows pass.
- [x] Add stable, shareable event deep links that preserve the selected match across refreshes.
- [x] Unify kickoff, bookmaker prices, model evidence, availability gates, and builder research in
  one coherent match-detail experience.
- [ ] Build a mobile-first navigation and responsive match/price layouts.
- [ ] Improve loading, empty, and recoverable error states with actionable language.
- [ ] Add a concise first-visit guide for probabilities, fair odds, value gates, and blocked states.
- [ ] Validate the completed site source and deploy it through the configured hosting workflow.
