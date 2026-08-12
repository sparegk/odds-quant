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
- [x] Keep the scheduler polling only at its configured interval until the old failure jobs,
  including sanitized failed job `62`, age out of the recent-job window. Require
  `monitor-collection --fail-on-alerts` to exit successfully, confirm target bookmaker coverage
  has not regressed, and confirm player props and inferred closing prices remain blocked. Record
  the clean live evidence in this file, then commit and push.
- [x] Verify adequate permitted historical-result coverage before any new training. Premier League
  seasons 2022/23 through 2025/26 each retain 380 unique non-demo finals from
  `openfootball-cc0` (1,520 total). All four seasons have source-update timestamps, zero
  settled-after-observed violations, accepted non-demo raw provenance, and distinct pinned content
  fingerprints. No duplicate import was required. OpenFootball, result-import, and modeling tests
  passed (23 tests).
- [x] Verify immutable model training, chronological evaluation, and promotion gates. The
  2025/26 held-out Premier League replay remains the only calibrated non-demo model: 342
  observations at 90% coverage, with Poisson Brier `0.6191`, log loss `1.0306`, and ECE `0.0707`.
  It beats the uniform baseline but trails the stored Elo and Dixon-Coles comparators marginally.
  The separate current Premier League, Champions League qualification, and Conference League
  qualification models remain explicitly `unvalidated`; none was promoted or retrained
  redundantly. All persisted non-demo outputs have zero input-cutoff and kickoff chronology
  violations. No bookmaker/closing benchmark or profitability conclusion is authorized. Model
  and evaluation tests passed (24 tests).
- [x] Verify cutoff-safe prediction persistence and fail-closed signal generation. The active
  scheduler persisted current non-demo team-baseline outputs with three market probabilities per
  event, exact `inputs_as_of == predicted_at` cutoffs, and prediction times strictly before
  kickoff. The live watchlist exposed three `research_only` candidates; every candidate was
  blocked by an unvalidated model and fewer than eight venue-specific matches per team. Running
  the executable generator against current output `212` was rejected with `model is not
  calibrated`, and a post-attempt audit confirmed zero non-demo `ValueSignal` rows. Modeling,
  signal-policy, signal-service, and scheduler tests passed (46 tests).
- [x] Verify retrospective outcome evidence and keep bookmaker-performance promotion fail-closed.
  All 342 observations in non-demo held-out run `2` retain final result provenance, actual
  outcomes, and post-kickoff settlement timestamps, with zero training-cutoff or kickoff chronology
  violations. All 342 intentionally retain empty bookmaker snapshot evidence, no profit units, and
  no closing-line values; the database contains zero snapshots explicitly marked `is_closing`.
  This authorizes probability evaluation only—not market comparison, CLV, ROI, or profitability
  claims. Closing prices must remain unavailable until an explicit, timestamped source stores them;
  they must never be inferred. Backtesting and evaluation tests passed (21 tests).
- [x] Deploy the completed frontend-tab source from pushed commit `194d463` as owner-only Sites
  version 10. Frontend lint, all 64 unit tests, the production build, and the repository's Sites
  worker verification passed. The deployment completed successfully at
  `https://oddsquant-research.kkakarantzas17.chatgpt.site`; Sites reports the project active with
  custom access limited to exactly one allowed user and zero groups.

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

### Scheduler continuation (2026-07-28)

The prior worker had stopped and both providers were stale. The production-mode hidden scheduler
was restored as Python PID `10472`. Its startup cycle completed API-Football job `126`, while Odds
job `127` failed closed after a successful, credential-redacted HTTP response. The next
scheduler-owned adaptive interval completed Odds job `128`, imported 372 prices across 138 new
timestamped snapshots, and reproduced the bounded 42 eligible / 3 created / 39 skipped prediction
summary with the exact 33 home-history and 6 away-history reasons. `monitor-collection
--fail-on-alerts` then exited
successfully with no alerts; both required bookmakers remain covered for the active UEFA
qualification competitions, no closing snapshots were inferred, and Premier League Novibet
coverage remains explicitly blocked rather than fabricated.

The original recovery continued with successful job `129`, transient fail-closed Odds jobs `131`
and `132`, then consecutive successful jobs `133` and `134`. Both providers returned to healthy,
but the recent-window repeated-failure warning remains. The worker was replaced after job `134`
with the cadence-safe build as Python PID `9108`; its startup correctly skipped both providers
because neither configured interval was due. API-Football now applies the same persisted-job
restart guard as Odds, preventing restarts from accelerating its licensed request cadence.

Leave PID `9108` running at its configured adaptive cadence. Eight further successful Odds jobs
after `134` are required for newest failure `132` to age out before ticking the monitoring
checkbox. The active worker records the provider adapter's own validated `OddsApiIoError` reason
while retaining generic, secret-safe messages for unexpected exceptions.

The cadence-safe worker then completed Odds jobs `135` and `136`, but its skipped API-Football
startup left the next intelligence wake anchored 30 minutes after restart and monitoring marked
the feed stale. API-Football now runs on the five-minute scheduler heartbeat while its persisted
30-minute guard remains authoritative. The replacement worker is active as Python PID `11952`;
startup skipped the not-yet-due Odds collector and completed overdue API-Football job `137`.
Both providers returned healthy and only the recent Odds failure warning remains. Six further
successful Odds jobs after `136` are required for job `132` to age out.

The active diagnostics identified later failed Odds job `143` as
`invalid pre-match match-result timestamp`. The adapter had captured one observation timestamp
before the multi-request collection began, so a legitimate source update created while an HTTP
request was in flight could appear later than local observation. Odds sub-batches now use their
actual response receipt time while still requiring source update at or before receipt and strictly
before kickoff. The replacement worker is active as Python PID `18504`; both startup collectors
were cadence-skipped, and its first due Odds job `144` completed successfully. The
repeated-failure alert cleared, but job `143` remains in the last-10 Odds window. Nine further
successful Odds jobs after `144` are required before the monitoring checkbox can be ticked.

Subsequent scheduled jobs showed that response receipt timing alone does not resolve the provider
clock inconsistency. Jobs `145`, `149`, and `151` failed the same timestamp gate, job `146` failed
closed on HTTP 429, and jobs `147`, `150`, `152`, and `153` completed without weakening atomic
validation. The replacement diagnostic worker is active as Python PID `18664`. Its first due Odds
job `155` measured the unsafe match-result source update at `55.682` seconds after local response
receipt. No arbitrary clock-skew tolerance was added. The monitoring checkbox remains blocked
until an authoritative response timestamp can prove the source update existed when received, the
provider corrects its clock, or a separately tested fail-closed handling policy is approved.

The provider's standard HTTP `Date` response header is now accepted as authoritative receipt
evidence only when it parses as an aware timestamp and differs from the local response clock by no
more than five minutes. Missing, malformed, and excessive-skew headers fall back to local receipt
and continue to reject future source updates; every accepted source update must still be strictly
before kickoff. Ingestion time is advanced to the trusted observation time when needed, preserving
`source_updated_at <= observed_at <= ingested_at`. The bounded-clock worker is active as Python
PID `17720`; its first due Odds job `157` completed successfully after failed old-build job `156`.
Require consecutive post-fix successes and a clean monitoring report before ticking the checkbox.

The bounded HTTP-clock worker completed consecutive jobs `157` through `165`, then scheduled job
`166` exhausted its bounded internal retries on HTTP 429. A persisted 429 now forces the next Odds
collection to wait at least the normal 15-minute interval even when near-kickoff cadence would
otherwise be five minutes. The backoff worker is active as Python PID `18048`; startup and the
intervening heartbeat skipped Odds, and the first eligible post-backoff job `167` completed
successfully. One older failure warning remains in monitoring; require another successful Odds job
and a zero-alert report before ticking the checkbox.

Final monitoring completed on 2026-07-28 after Odds job `173` and API-Football job `174`. Odds had
six consecutive completed jobs, API-Football had ten, both providers were healthy, and
`monitor-collection --fail-on-alerts` exited `0` with zero alerts. Job `173` retained both required
bookmakers for the active Champions League and Conference League qualification feeds; the known
Premier League Novibet gap remained explicit without a regression alert. The permitted store
contained only `MATCH_RESULT` and `TOTAL_CORNERS`, player props remained unimplemented, closing
snapshots remained `0`, and deterministic database checks found no source-after-observation or
observation-after-ingestion violations. The full backend gate passed: 231 tests, Ruff, formatting,
and mypy.

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
- [x] Build a mobile-first navigation and responsive match/price layouts.
- [x] Improve loading, empty, and recoverable error states with actionable language.
- [x] Add a concise first-visit guide for probabilities, fair odds, value gates, and blocked states.
- [x] Validate the completed site source and deploy it through the configured hosting workflow.

### Production data connection checklist

- [x] Replace the card-gated Render plan with a local, production-mode API, migrated SQLite
  database, scheduler worker, and free Cloudflare Quick Tunnel. The 2026-07-27 tunnel proof
  returned 14 timestamped Matchday events over HTTPS, while an unauthenticated admin import
  failed closed with HTTP 503. `scripts/start-free-site-tunnel.ps1` reproduces the startup;
  the computer and processes must remain running, and a restarted Quick Tunnel gets a new URL.
- [x] Route production browser API requests through the same-origin Sites worker and store the
  live Quick Tunnel origin in Sites runtime configuration. Sites version 8 deployed from
  CI-passing commit `f32ab8a` with environment revision 1; the deterministic worker check proves
  API paths proxy to the configured HTTPS tunnel and fail closed when configuration is absent.
- [x] Allow only the exact Sites production origin in the tunneled API process. A live preflight
  returned HTTP 200 with that origin echoed in `Access-Control-Allow-Origin`; an unrelated origin
  returned HTTP 400 with no allow-origin header. The reproducible startup script contains no
  wildcard CORS setting.
- [x] Deploy owner-only Sites version 9 from CI-passing commit `85c63cd` and verify the production
  proxy end to end. Matchday returned 14 events; stable deep link `/matches/1256` returned HTTP
  200 and its detail API retained two price markets, a latest model prediction, an explicit
  blocked builder gate with zero stored quotes, and a non-empty evidence note.
- [x] Review production access and retain owner-only mode: exactly one allowed user and no groups.
  Do not make this Quick-Tunnel-backed deployment public without a separate explicit approval and
  a durable origin with appropriate uptime and operational controls.

### Live collection recovery checklist (2026-07-30)

- [x] Check the Odds-API.io quota/reset state with one bounded request before restarting collection.
  The selected-bookmaker probe completed successfully and retained both required bookmakers,
  confirming that the earlier HTTP 429 condition had reset. No repeated or collection-sized probe
  was issued. Persisted jobs `189` through `203` remain sanitized evidence that the old scheduler
  retried a sustained 429 condition every normal interval; collection stays stopped until a
  persistent cooldown is implemented.
- [x] Persist an HTTP 429 cooldown across scheduler heartbeats and process restarts, honoring a
  valid provider `Retry-After` value while using a conservative fallback when reset evidence is
  unavailable. Failed jobs now retain only a sanitized aware `retry_at` and its source in JSON
  metrics. The adaptive scheduler reads that persisted boundary before issuing another request;
  absent reset evidence defaults to a configurable 24-hour cooldown. Deterministic provider and
  restart tests pass, as do all 234 backend tests, Ruff, formatting, and mypy.
- [x] Resolve the first post-restart atomic fixture-import blocker without overwriting historical
  identity. Scheduler job `205` found that the provider had retained stable event IDs while
  replacing UEFA `Winner Match` placeholders with qualified teams and precise kickoff times. A
  new migration versions competition, teams, and kickoff on every fixture observation; the
  canonical scheduled event advances only before its stored kickoff and only when no model output
  or result exists. Fifteen diagnosed corrections had zero stored model outputs and zero markets.
  Upgrade/downgrade/upgrade verification and all 236 backend tests, Ruff, formatting, and mypy pass.
- [x] Restart both configured collectors, obtain at least two consecutive successful jobs per
  provider, and require recovery-window monitoring to exit successfully. After applying migration
  `a7b8c9d0e1f2`, hidden scheduler PID `5948` completed Odds jobs `206` and `207` at the configured
  adaptive cadence; each observed 71 fixtures and imported 327 prices across 119 snapshots.
  API-Football's latest two jobs are completed, with fresh job `204` retaining 97 requests after
  its bounded collection. `monitor-collection --recent-job-limit 2 --fail-on-alerts` exited `0`:
  both providers were healthy, each had a two-job completed streak, and alerts were empty.
- [x] Verify the resumed UEFA feed retains cutoff-safe timestamps, required-bookmaker coverage,
  supported team markets only, and no inferred closing snapshots or player props. The latest
  completed Odds job `211` retained Allwyn / Pamestoixima and Novibet across both active UEFA
  qualification competitions. A deterministic database audit found zero fixture or odds timestamp
  ordering violations, zero canonical-versus-latest fixture identity mismatches, zero prediction
  chronology violations, and zero closing snapshots. The only stored market types remain
  `MATCH_RESULT` and `TOTAL_CORNERS`; player props remain absent and disabled.
- [x] Establish the permitted historical-odds and explicit closing-price acquisition checkpoint;
  do not authorize market, CLV, ROI, or profitability validation without that evidence.
  `DATA_SOURCES.md` records the 2026-07-30 official-contract review. The Odds API lacks published
  Conference League qualification and target-bookmaker coverage; Sportmonks retains retrievable
  history for only seven days and has no configured subscription; Odds-API.io still lacks a
  per-price timestamp on its claimed closing response. No source passes the complete gate, so no
  purchase, adapter, historical import, or closing flag is authorized.
- [x] Revisit signal thresholds, staking, CLV, and market benchmarks only if the acquired evidence
  passes chronology, identity, price-provenance, completeness, and sample-size gates. The
  authorization audit found one calibrated non-demo probability run with 342 observations, but
  zero observations reference an odds snapshot, profit unit, or closing-line value. The database
  also retains zero non-demo signals and zero closing snapshots. This supports probability scoring
  only; no threshold, staking, market-benchmark, CLV, ROI, or profitability validation is
  authorized, and all existing policies remain unchanged.
- [x] Keep player-strength adjustments and player props blocked until timestamped licensed player
  targets, stable identities, minimum-minute and recency rules, settlement contracts, and
  chronological ablation evidence are independently validated. The 2026-07-30 local audit found
  zero non-demo players, registrations, appearances, player statistics, availability reports,
  expected lineups, confirmed lineups, or confirmed-context outputs. Stored markets remain only
  `MATCH_RESULT` and `TOTAL_CORNERS`. `DATA_SOURCES.md` records the separate player-strength and
  prop activation contracts; no player adjustment or prop behavior was enabled.
- [x] Verify the persistent circuit breaker against a later live rate limit. After the earlier
  healthy recovery checkpoint, scheduled Odds job `212` received HTTP 429 at
  `2026-07-30T14:18:00Z`. The failed job persisted a sanitized conservative retry boundary of
  `2026-07-31T14:18:00Z`; no later Odds job was issued, while API-Football continued successfully
  through job `214`. Scheduler PID `5948` remains active. Monitoring is expected to report the Odds
  provider unhealthy until the cooldown expires and fresh consecutive jobs complete; do not probe,
  restart, or manually bypass the boundary.

### Probability recalibration checkpoint (2026-07-30)

- [x] Align the tracked methodology and roadmap with the implemented uncertainty, market-relative
  promotion, and chronological recalibration contracts. Current model versions use deterministic
  chronological moving-block bootstrap refits rather than the legacy Wilson-only proxy. Promotion
  requires paired-bootstrap superiority to both uniform and sufficiently covered compatible market
  benchmarks, plus accepted held-out scalar temperature scaling. Predictions persist the exact
  calibrator cutoff and fingerprint, and signal generation fails closed unless the output applies
  the accepted pre-cutoff calibrator from the qualifying evaluation. These controls are software
  and provenance evidence only; no historical-odds, CLV, ROI, or profitability claim is added.
- [x] Smoke-test calibration-provenance migration `c9d0e1f2a3b4`. The configured local SQLite
  database reports the new revision as its Alembic head and exposes non-null JSON column
  `model_event_outputs.probability_calibration`. A separate temporary database upgraded through
  predecessor `b8c9d0e1f2a3` and then applied the exact predecessor-to-head transition successfully;
  inspection confirmed the same column contract. The isolated database was removed after the
  check. No production database, credential, or raw data was exposed by this receipt.
- [x] Complete and verify walk-forward probability recalibration. Evaluation now fits scalar
  temperature only from earlier held-out outcomes, persists acceptance checks and immutable fit
  provenance, and requires sufficient market-relative and recalibration evidence before promotion.
  Later 1X2 predictions apply only the exact accepted pre-cutoff calibrator, transform bootstrap
  intervals sample by sample, expose provenance through the typed API and Matchday dashboard, and
  block signal generation when calibrator provenance is absent or mismatched. The full backend
  suite passed with 259 tests; Ruff, format checking, and Mypy passed; all 65 frontend tests,
  ESLint, and the production build passed. This is deterministic software verification only, not
  evidence that any current model passes the new promotion policy or produces profitable signals.
- [x] Verify remote CI for calibration implementation commit `d0f31f4`. GitHub Actions run
  `30569429687` completed successfully on `main` after the migration, backend, and frontend
  checkpoints were pushed. This receipt confirms the remote repository gates only; it does not
  change the provider cooldown, authorize historical data, or promote a model.

### Probability-research scope checkpoint (2026-07-30)

- [x] Make match-result probability research the active project goal and move arbitrage to
  maintenance-only status. Existing arbitrage safety behavior remains tested and available, but no
  new market or execution work is authorized by this checkpoint. The next implementation separates
  chronological probability validation from market/value validation: the former may support model
  research without historical odds, while signals, CLV, staking, ROI, and profitability remain
  blocked until their independent market-evidence gates pass.
- [x] Persist independent probability-validation provenance. Policy
  `separated-probability-market-v5` records a probability decision from non-demo sample size,
  replay coverage, ECE, paired-bootstrap superiority to uniform, and accepted chronological
  recalibration, while the existing evaluation status retains the stricter market-relative
  decision. Additive migration `d0e1f2a3b4c5` upgraded the configured SQLite database and verified
  non-null status columns on both model versions and evaluation runs. Probability-validated runs
  may supply their exact accepted pre-cutoff calibrator to later research predictions; this does
  not make the run market-validated. Ruff, formatting, Mypy, and 24 targeted backend tests passed.
- [x] Expose the two validation tracks through the typed research surface. Model and evaluation API
  contracts now carry `probability_evaluation_status` alongside the existing market/value
  `evaluation_status`. Model Performance displays both classifications in the version registry,
  immutable evaluation history, and readiness audit; a probability-validated run is labelled
  research-ready while an insufficient market result remains visibly blocked for value use. All 65
  frontend tests, ESLint, TypeScript compilation, and the production build passed.
- [x] Prove probability validation cannot authorize betting-value output. Signal generation still
  requires model and evaluation `evaluation_status == calibrated`, the complete v5 market-policy
  checks, and the exact evaluation calibrator on the prediction. A deterministic regression creates
  a probability-validated, temperature-calibrated output whose market decision is
  `insufficient_market_evidence`; generation fails with `model is not market validated` and stores
  zero value signals. Research-candidate blockers now name the missing market-validated evaluation
  explicitly. Ruff, Mypy, and all 35 signal, suggestion, and backtesting tests passed.
- [x] Complete the probability-research scope verification. The full backend suite passed with 260
  tests; Ruff, format checking, and Mypy passed across 119 source files; the configured database is
  at Alembic head `d0e1f2a3b4c5`; all 65 frontend tests, ESLint, TypeScript compilation, and the
  production build passed. Arbitrage remains maintenance-only, probability validation is visible
  as a distinct research status, and market/value outputs remain independently fail-closed.
- [x] Replay the existing non-demo 2025/26 Premier League holdout under the separated probability
  and market policy before developing another model. Immutable run `3`, fingerprint
  `aa389cbbc5f9c3bf0baa26466047b88c64c247bfa132ac4863a59419adc487b5`, reused model version `3`,
  the exact `2025-08-01T00:00:00Z` through `2026-05-27T00:00:00Z` window, a 60-minute lead, a
  200-match training floor, and 10 calibration bins. It evaluated 342 of 380 fixtures (90%
  coverage): Poisson Brier score `0.619119`, log loss `1.030631`, and ECE `0.070717`. Policy
  `separated-probability-market-v5` classified the run `probability_validation_failed` and retained
  the independent market result `insufficient_market_evidence`; this receipt records the replay
  outcome without promoting the model or authorizing signals.
- [x] Audit every probability-validation gate on immutable run `3`. The non-demo, 342-observation
  minimum, 90% coverage, and maximum-ECE gates passed; Poisson ECE was `0.070717` against the
  `0.08` ceiling. Paired moving-block bootstrap superiority to uniform also passed: the 95%
  upper loss-difference bounds were `-0.006187` for Brier score and `-0.012774` for log loss.
  Chronological temperature scaling evaluated 282 later observations and improved subset Brier
  score from `0.626013` to `0.623984` and log loss from `1.039833` to `1.037598`, but worsened
  ECE from `0.066038` to `0.066738`. Because policy requires Brier, log loss, and ECE together,
  the sole failed probability gate is `chronological_recalibration_accepted`; temperature
  `1.263689`, fitted through the 342-observation run, remains explicitly unaccepted and cannot be
  applied to later predictions.
- [x] Apply the post-validation prediction condition without bypassing the failed gate. Because run
  `3` did not become probability validated and its final calibrator is unaccepted, no later
  calibrated research prediction was created. A direct database audit found model version `3`
  remains `unvalidated` on the probability track and retains zero model outputs, zero selection
  predictions, and zero value signals. Its legacy market-status label does not satisfy the v5
  evaluation-policy and exact-calibrator requirements used by signal generation. The project
  therefore remains fail-closed while model research continues.
- [x] Compare the current Poisson model with Elo and Dixon-Coles on the same 342-event holdout.
  Elo produced the best point estimates (Brier `0.615412`, log loss `1.024991`, ECE `0.046775`);
  Dixon-Coles followed (Brier `0.618151`, log loss `1.028645`, ECE `0.060217`), then Poisson
  (Brier `0.619119`, log loss `1.030631`, ECE `0.070717`). Poisson-minus-Elo paired 95%
  intervals were `[-0.009654, 0.017196]` for Brier and `[-0.013799, 0.026058]` for log loss;
  Poisson-minus-Dixon-Coles intervals were `[-0.010826, 0.012781]` and
  `[-0.015359, 0.018516]`. Both comparisons cross zero, so no challenger is selected from this
  evidence alone. Elo is the next implementation candidate because it has the strongest proper-
  scoring and calibration point estimates and avoids the repeated numerical optimization cost;
  it must still pass an identical chronological evaluation before selection.
- [x] Develop Elo as a first-class, still-unvalidated team-level research candidate. The new
  `train-elo` CLI command and admin API persist an immutable `davidson_elo` model version with
  explicit Davidson parameters, canonical competition-family scope, original result timestamps,
  chronological result ordering, minimum-history policy, and an exact input fingerprint. No Elo
  prediction or signal path is enabled before evaluation. The configured non-demo candidate is
  model `6`, version `elo1-c8-202508010000-083c8468`, trained through
  `2025-08-01T00:00:00Z` on 1,140 canonical fixtures and retained both validation statuses as
  `unvalidated`. Deterministic tests prove idempotent versioning and that a post-cutoff correction
  cannot change its fingerprint or sample. All 262 backend tests, Ruff, formatting, Mypy, and the
  CLI contract passed.
- [x] Evaluate the Elo candidate on the identical holdout and apply the challenger-selection gate.
  Elo-primary evaluation now persists its model kind, primary benchmark, aligned Poisson
  comparison, calibration buckets, and model-specific paired-loss provenance while preserving the
  prior Poisson replay contract. Immutable run `4`, fingerprint
  `9ccc83a9e2fe94781e441103309e422fa0127706123bcad182d589336825d02b`, evaluated the same 342 of
  380 fixtures. Elo improved point Brier score from Poisson `0.619119` to `0.615412` and log loss
  from `1.030631` to `1.024991`, but its Elo-minus-Poisson paired 95% intervals were
  `[-0.018042, 0.010941]` and `[-0.025559, 0.013215]`; both cross zero, so Elo is not selected.
  Walk-forward temperature scaling also worsened Brier `0.623256` to `0.624918`, log loss
  `1.034874` to `1.037277`, and ECE `0.049211` to `0.065760`. The run therefore remains
  `probability_validation_failed`, model `6` remains `unvalidated`, and zero Elo outputs or
  signals exist. All 263 backend tests, Ruff, formatting, and Mypy passed.

### Probability evidence expansion checkpoint (2026-08-04)

- [x] Audit stored permitted final-result depth before running the new calibration, nested-selection,
  or ensemble specifications on historical outcomes. The already-examined 2025/26 Premier League
  holdout is development evidence and cannot be relabelled as untouched validation. Premier League
  history ends before the existing 2026-05-27 evaluation cutoff, leaving zero later final events.
  Every other exact competition family has fewer than the 400 results needed for a fixed 200-match
  training floor plus a separate 200-observation holdout. No new evaluation or promotion was
  authorized. `PROBABILITY_EVIDENCE_EXPANSION.md` stores the aggregate counts, audit contract, and
  explicit exit criteria without pooling distinct UEFA identities or weakening thresholds.

### Player and tactical feature activation checkpoint (2026-08-04)

- [x] Persist a machine-readable fail-closed feature decision on every new model output. Migration
  `b9c0d1e2f3a4` adds non-null JSON provenance; team baselines and confirmed-lineup context both
  retain `probabilities_adjusted=false`, no applied features, requested context labels, and fixed
  blocker codes for the absent validated feature version, licensed timestamped player history,
  chronological ablation evidence, and double-counting exclusion. Confirmed lineups remain linked
  evidence only and deterministic tests prove their expected goals equal the team baseline. The
  configured database upgraded to the single Alembic head, all 275 backend tests passed, and Ruff,
  formatting, and Mypy passed. No player adjustment, tactical adjustment, or player prop was enabled.

### Evaluation diagnosis and readiness checkpoint (2026-08-04)

- [x] Make evaluation failure evidence actionable in the desktop site. Model Performance now lists
  every stored promotion gate with its exact threshold or interval evidence, explains the next
  valid research action, and compares raw versus selected calibration metrics on the untouched
  partition with method, cutoff, sample, and fingerprint provenance. Backend and frontend readiness
  contracts now count non-demo probability-validated and market-validated evaluations separately;
  stored runs cannot make either stage appear qualified. Match research also exposes the persisted
  player/tactical feature gate and its blockers. All 275 backend tests, 76 frontend tests, Ruff,
  formatting, Mypy, ESLint, TypeScript compilation, and the production build passed.

### Aligned model experiment checkpoint (2026-08-04)

- [x] Add an exact-window experiment matrix to Model Performance. It compares aligned primary
  Poisson/Elo runs and stored Dixon-Coles, nested-selection, and chronological-ensemble benchmarks
  without mixing demo provenance or evaluation windows. The table exposes proper-score point
  estimates, calibration error, observation alignment, exact configuration or selection counts,
  and paired uncertainty verdicts. Reference attribution follows the actual primary model, so an
  Elo-primary run cannot mislabel Poisson as the reference. This is comparison evidence only: no
  challenger was promoted and the probability and market/value gates remain unchanged. All 275
  backend tests, 76 frontend tests, Ruff, formatting, Mypy, ESLint, TypeScript compilation, and the
  production build passed.

### Bundesliga external-validation selection checkpoint (2026-08-04)

- [x] Identify a permitted exact competition family before inspecting new model scores.
  `BUNDESLIGA_EXTERNAL_VALIDATION.md` pins CC0 OpenFootball commits and blobs for two complete
  Bundesliga training seasons (612 results) and the 2024/25 holdout source. The locked window from
  `2024-09-20T00:00:00Z` contains 279 final candidates, exceeding the 200-event requirement before
  eligibility checks. No raw source file, database change, holdout metric, promotion, or signal is
  included in this checkpoint.
- [x] Import and audit the three pinned files without committing raw data or the local database.
  Atomic jobs `158`, `159`, and `160` each created 306 final results and retained distinct raw
  content hashes plus their exact publication timestamps. The configured database now has 918
  final non-demo Bundesliga results and exactly 279 events in the locked holdout. All 16
  OpenFootball and result-import tests passed. No model score has been calculated yet.
- [x] Freeze the complete experiment before replay. The machine-readable
  `backend/config/bundesliga_external_validation_v1.json` pins the Poisson primary, training and
  evaluation boundaries, v6 probability policy, calibration partitions, bootstrap rules, nested
  grid, ensemble grid, benchmark versions, and fail-closed decision rules to implementation commit
  `28ce95e`. A deterministic test fails if those quantitative constants drift. No holdout metric
  was inspected while selecting this specification.

### Pause checkpoint: Bundesliga replay ready (2026-08-04)

- The repository should be clean on `main` after the commit containing this section. Dataset
  selection commit `0cef05a` and atomic import receipt commit `28ce95e` are already pushed.
- The configured local database retains Bundesliga competition IDs `23` (2022/23), `24`
  (2023/24), and `25` (2024/25), plus completed import jobs `158` through `160`.
- The frozen manifest test passes; full Ruff checking, Ruff format checking, and Mypy pass across
  132 Python source files. No Bundesliga model has been trained and no holdout metric inspected.
- Resume from `backend` by first running `git status -sb` and
  `py -m pytest tests/test_external_validation_spec.py`. Then train the frozen primary exactly:

  `py -m app.cli train-poisson 25 2022-08-01T00:00:00+00:00 2024-09-20T00:00:00+00:00 --minimum-matches 200 --minimum-team-matches 8 --shrinkage-matches 5`

- Retain the returned model ID. Only then run the pre-registered replay exactly:

  `py -m app.cli evaluate-model MODEL_ID 2024-09-20T00:00:00+00:00 2025-05-18T00:00:00+00:00 --prediction-lead-minutes 60 --minimum-training-matches 200 --calibration-bins 10`

- After the immutable run is stored, audit every probability gate and record the outcome without
  retuning. Do not start market, signal, staking, or player-feature work unless its prerequisite
  gate explicitly passes.

### Bundesliga untouched replay checkpoint (2026-08-07)

- [x] Train the frozen primary specification as model ID `7`, version
  `pq1-c25-202409200000-c72fb25b`, from all 612 eligible prior results without changing the
  registered training boundary or hyperparameters.
- [x] Complete immutable evaluation run `5` over the locked 2024/25 window. Its fingerprint is
  `0784718941c4f2e22326902be89c76158f038b0d2a66e487f4b078708d2bf9cb`.
- [x] Audit every frozen probability gate. Observation count and chronological identity
  recalibration passed. Coverage was 219/279 (78.49%) against 90%, ECE was 0.08521 against 0.08,
  and the paired uniform Brier/log-loss upper differences were 0.01140/0.03010 against the
  below-zero requirements. The stored probability decision is `insufficient_evidence`.
- [x] Preserve the failed result without retuning. The Bundesliga holdout is now examined evidence;
  it does not promote the model or authorize market, signal, staking, player-feature, or
  profitability work. See `BUNDESLIGA_EXTERNAL_VALIDATION.md` for the full receipt.

### External-validation site receipt checkpoint (2026-08-07)

- [x] Bind the Bundesliga external-validation classification to the immutable evaluation
  fingerprint in a typed backend registry. Unmatched evaluation runs receive no external-holdout
  label, and the matched receipt explicitly blocks retuning and market authorization.
- [x] Expose the receipt through the evaluation API and Model Performance. The site shows the
  pre-registration date, execution date, examined status, probability decision, full fingerprint,
  and separate retuning and market-validation decisions.
- [x] Add deterministic backend fingerprint tests and frontend rendering coverage. Focused backend
  evaluation/API tests, Ruff, formatting, Mypy, the Model Performance test, ESLint, TypeScript,
  and the production build pass.

### Historical market-evidence recheck (2026-08-07)

- [x] Re-audit the configured database after the external replay. It contains 3,463 permitted
  finals and 11,539 permitted odds snapshots, but historical result seasons have zero timestamped
  odds and the entire store has zero explicit closing snapshots. Current prices cover upcoming
  2026/27 events only and cannot be backfilled into examined evaluations.
- [x] Recheck current official historical-price contracts without making a paid request. The Odds
  API offers paid timestamp-addressed Bundesliga snapshots but still requires subscription,
  bookmaker, licensing, identity, completeness, and quota approval; Sportmonks retains its
  seven-day retrieval limit; Odds-API.io still lacks an original per-price timestamp on its
  closing response. `DATA_SOURCES.md` records the decision.
- [x] Apply the probability prerequisite. Because frozen Bundesliga run `5` did not pass, no paid
  market acquisition, adapter, market evaluation, signal, CLV, staking, ROI, or profitability work
  is authorized now.
- [ ] Acquire permitted historical market evidence. This remains externally blocked until the
  owner supplies a permitted timestamped odds file or approves a source/account after a genuinely
  new untouched probability run passes.

### Cold-start probability development (2026-08-07)

- [x] Add an isolated league-prior Poisson primitive for promoted or otherwise unseen teams. It
  returns explicit prior-use and venue-history evidence, while the existing strict
  `expected_goals` path still rejects an unseen team. This is a tested development primitive only;
  it is not active in stored models, live predictions, promotion, or signals.
- [x] Add an explicit `--include-cold-start-benchmark` development replay mode. It stores a
  separately versioned full-candidate benchmark, cold-start counts, aligned paired intervals, and
  all cold-start inputs in the evaluation fingerprint. The strict primary eligibility and policy
  decision remain unchanged, Elo primaries reject the option, and Model Performance labels the
  row as a development benchmark with different-coverage evidence. Focused backend tests, Ruff,
  formatting, Mypy, the Model Performance test, ESLint, TypeScript, and the production build pass.
- [x] Run the opt-in benchmark on the now-examined Bundesliga window and store immutable
  development run `6`, fingerprint
  `4e6ae4ba47f46b6a6f2596a966ac154bf3109073014d8d9ba7a26a1c3245b010`. It recovered 279/279
  coverage across 60 unseen-team fixtures. All-candidate Brier/log loss/ECE were
  0.62910/1.04955/0.08225; the shared 219 forecasts were exactly identical to strict Poisson. The
  candidate remains development-only because ECE still misses 0.08 and no new untouched evidence
  has tested it.

### Final fail-closed and collection handoff (2026-08-07)

- [x] Audit the post-development database state. Model `7` remains `unvalidated` on both tracks,
  has zero stored outputs, and runs `5` and `6` both remain `insufficient_evidence`. The store has
  zero value signals and zero explicit closing snapshots. It also has zero players, registrations,
  appearances, player statistics, availability reports, or lineups; stored markets remain only
  `MATCH_RESULT` and `TOTAL_CORNERS`.
- [x] Re-run the fail-closed signal, feature-activation, and arbitrage maintenance tests. All 35
  targeted tests passed. The complete verification after the cold-start implementation passed with
  281 backend tests, 76 frontend tests, Ruff, formatting, Mypy, ESLint, TypeScript, and the
  production build.
- [x] Restore the expired-cooldown scheduler without issuing a separate provider probe or bypassing
  its cadence. Hidden PID `10312` completed fresh API-Football job `233` and consecutive Odds jobs
  `234` and `235`. Both providers have no current blockers, permitted odds coverage reached 11,663
  snapshots, and the expected warning for older Odds failures remains until those jobs age out of
  the recent window. Closing snapshots remain zero.

### Matchday discovery and recommendation handoff (2026-08-07)

- [x] Fix empty Matchday landing dates. `GET /api/v1/matchdays` now returns the nearest previous
  and next stored event dates, the dashboard automatically recovers a stale empty landing date
  once, and exact stored-matchday controls remain visible on mobile. Commit `d42a270` is pushed.
- [x] Put recommendation status directly below bookmaker selection for every opened match. Qualified
  suggestions remain distinct from a clearly labelled research-only watchlist; when none qualify,
  the UI displays the exact market blockers and never promotes raw EV to a recommendation. Commit
  `95d6d49` is pushed.
- [x] Reconcile only the deterministic provider-name variation `Club` versus `Club FC` across
  fixture, odds, and result imports. The earliest stored identity remains canonical; no broader
  fuzzy matching was added and all minimum-history gates remain unchanged. A rollback-only 30-day
  replay increased creatable/reusable predictions from 1 to 8 and research candidates from 1 to
  10, while the other 39 eligible events still failed their original history gates. Commit
  `6563d2d` is pushed.
- [x] Reload the worker and apply the resolver through normal provider collection. Odds job `261`
  completed, all upcoming fixture identities now have zero pending trailing-`FC` corrections, and
  the persistent scheduler is running under Python PID `18032`. No signal gate was bypassed.
- [x] Complete verification: 283 backend tests and 78 frontend tests pass, together with Ruff,
  Ruff formatting, Mypy, ESLint, TypeScript, and the production build.

### Ligue 1 cold-start external validation (2026-08-10)

- [x] Restore the stopped persistent scheduler at its configured cadence. Jobs `262` and `263`
  completed normally, both providers returned healthy with no alerts, and hidden launcher PID
  `6620` remains active. No ad hoc provider request or cadence acceleration was used.
- [x] Select a genuinely new exact family before model scoring. La Liga and Serie A 2024/25 were
  rejected at 370/380 finals; no partial feed was imported. Complete CC0 Ligue 1 files were pinned
  by commit, blob, publication timestamp, and SHA-256.
- [x] Freeze the cold-start implementation at `f722ca1` and the pre-replay manifest at `15af527`.
  The v2 candidate widens probabilities toward uniform from pre-kickoff venue-history counts, uses
  identity-only calibration, retains fixed v6 proper-score/ECE gates, cannot auto-promote a model,
  and cannot authorize markets.
- [x] Atomically import jobs `187` through `189`, creating 992/992 final results under Ligue 1
  competition IDs `26`, `27`, and `28`. Model `8` trained on exactly 686 leakage-safe prior-season
  results; the 36 early holdout fixtures were excluded at the training boundary because their
  pinned source was published only after the season.
- [x] Complete immutable run `7`, fingerprint
  `28a2324ff783d412afbfe030d21f690892a5e2ac3f301e62b1896cea37b77471`. Strict Poisson covered
  161/270 and failed coverage, observation, and ECE gates. The cold-start candidate covered 270/270
  and passed both paired uniform intervals, but ECE `0.08692` failed the frozen `0.08` threshold.
  Both decisions remain `insufficient_evidence`; model `8` remains unvalidated and no retuning or
  market work is authorized. See `LIGUE1_EXTERNAL_VALIDATION.md`.
- [x] Complete verification: 288 backend tests and 78 frontend tests pass, together with Ruff,
  Ruff formatting, Mypy, ESLint, TypeScript, and the production build. Final monitoring is healthy
  on provider jobs `268` and `269`; the store still has zero value signals and zero closing prices.

## Next resume action

### Cold-start v2 activation (2026-08-11)

- [x] Freeze probability-only activation contract `cold-start-v2-probability-activation-v1` against
  the exact two-family receipt. It authorizes only a new `pqc2` model row using the frozen v2 math;
  models `9`/`10` and strict runs `8`/`9` remain unchanged. Market validation, automatic signals,
  player features, staking, ROI, and profitability claims remain blocked. See
  `COLD_START_ACTIVATION.md`.
- [x] Implement and verify the new explicitly versioned `pqc2` model path without changing the
  frozen activation contract or creating market signals. The path clones a non-demo trained
  Poisson source into a distinct immutable row, supports unseen and sparse venue histories through
  the frozen eight-match league-prior widening, persists only `MATCH_RESULT` probabilities, and
  remains `insufficient_market_evidence` for all signal gates. Legacy source model `2` failed
  closed on its v2 feature version, so current-feature strict source model `11` was trained with the
  same 1,520-match window and remains unvalidated. Activated model `12`,
  `pqc2-c5-202606020000-7917411c`, produced pre-kickoff output `232` for Arsenal-Coventry with
  Coventry at zero away-history, league-prior uncertainty, reliability `0.5`, 400/400 bootstrap
  refits, identity calibration, and only `MATCH_RESULT` predictions. Models `9`/`10` and runs
  `8`/`9` remain unchanged; value signals and closing snapshots remain zero.

Final verification: 302 backend tests and 78 frontend tests pass, together with Ruff, Ruff
formatting, Mypy, ESLint, TypeScript, and the production build. Collection monitoring is healthy
with no alerts on provider jobs `282` and `284`; the reloaded scheduler is active under PID
`16368`.

### Cross-league replication execution (2026-08-10)

- [x] Verify the operational baseline before new research. `monitor-collection --fail-on-alerts`
  reports both providers healthy with no alerts on jobs `268` and `269`; persistent scheduler PID
  `6620` remains active at the configured 900-second cadence. The branch was clean and aligned with
  `origin/main`. No provider request was accelerated.
- [x] Freeze cross-league confirmation policy `cross-league-cold-start-confirmation-v1` before
  selecting or scoring outcomes. Exactly two preselected families must both pass independently;
  metric pooling, post-first-replay replacement, third-family rescue, automatic promotion, and
  market authorization are forbidden. See `CROSS_LEAGUE_CONFIRMATION.md`.
- [x] Select and jointly pre-register both untouched families before replaying either. Execution is
  fixed as Eredivisie 2024/25 first (612 training results, 263 candidates), then Primeira Liga
  2024/25 (612 training results, 261 candidates). All six pinned CC0 files are complete at 306/306
  finals; neither family had a stored competition, model, or run at selection time.
- [x] Execute unchanged cold-start v2 on family one. Eredivisie jobs `193`-`195` imported 918/918
  results; model `9` trained on 612 results. Run `8`, fingerprint
  `40d196d536580d5af7153af345aaf43d075760e817e16ddd41b4e24acc65e551`, produced 263/263 candidate
  coverage, ECE `0.04460`, and paired upper differences `-0.00851`/`-0.01218`; every family gate
  passed. The combined decision remains pending family two and model `9` remains unvalidated.
- [x] Execute family two and apply the frozen combined decision. Primeira Liga jobs `197`, `198`,
  and `200` imported 918/918 results; model `10` trained on 612. Run `9`, fingerprint
  `353bc4310da6b91615e76265aefd25e290c9545fa1d6052aa99a2e6472565821`, produced 261/261 coverage,
  ECE `0.02759`, and paired upper differences `-0.000027`/`-0.001642`; every family gate passed.
  With both preselected families passing independently, the combined status is
  `replicated_probability_candidate`. Models `9`/`10` remain unvalidated, and automatic promotion
  and all market authorization remain blocked pending a separately reviewed activation.
- [x] Complete final verification: 296 backend tests and 78 frontend tests pass, together with
  Ruff, Ruff formatting, Mypy, ESLint, TypeScript, and the production build. Final monitoring is
  healthy with no alerts on provider jobs `277` and `278`; scheduler PID `6620` remains active.
  The store still has zero value signals and zero closing snapshots.

Keep the scheduler on its configured cadence and use `py -m app.cli monitor-collection
--fail-on-alerts`; do not accelerate requests merely to clear an aging warning. The cold-start v2
candidate now has replicated probability evidence from the preselected Eredivisie and Primeira
Liga sequence. Do not retune or reuse either holdout. The next quantitative step is a separately
reviewed activation contract and a new explicitly versioned model path; do not mutate models `9`
or `10`, whose strict-primary decisions remain insufficient. Historical market acquisition remains
unchecked until the owner supplies permitted timestamped odds or approves a source/account after probability
validation passes. Player adjustments, player props, market signals, CLV, staking, ROI, and
profitability claims remain blocked. Matchday will create supported Premier League prediction
research through the normal seven-day refresh horizon; until independent validation and fresh
compatible prices satisfy every gate, the site must continue to show no qualified bet
recommendation and explain why.

### Market-edge validation protocol (2026-08-11)

- [x] Freeze contract cold-start-v2-market-edge-validation-v1 before inspecting any 2026/27
  Premier League outcome, CLV, or return. The contract is hash-bound to the probability activation
  evidence and pins the complete prospective cohort, lawful 1X2/closing evidence, existing paired
  market-score gates, fixed explainable-value thresholds, one-candidate-per-event rule, explicit
  cost treatment, and positive lower confidence bounds for both mean CLV and net ROI. Model 12
  remains insufficient_market_evidence; automatic signals and staking remain blocked. See
  MARKET_EDGE_VALIDATION.md.
- [x] Verify the frozen protocol implementation. All 305 backend tests passed together with Ruff,
  Ruff formatting, and Mypy across 148 source files.
- [x] Restore the stopped prospective collectors without accelerating cadence. Hidden scheduler
  PID 2820 completed Odds job 309 and football-data job 310; monitoring returned healthy with no
  alerts. Job 309 received 326 prices across 69 fixtures, while the Premier League slice remained
  Pamestoixima-only. Permitted Premier League snapshots reached 1,660.
- [x] Re-audit official historical-price contracts without a paid request. No reviewed source
  supplies both an explicit closing designation and its original pre-kickoff price timestamp under
  an already approved account. The fixed acquisition box remains open at 30/380 stored cohort
  fixtures, zero finals, no Premier League Novibet coverage, and zero explicit closing snapshots.
  No source join, inferred closing flag, market replay, or return inspection was performed.

### Outcome-blind market-edge coverage audit (2026-08-12)

- [x] Add a typed frozen-cohort audit through both
  GET /api/v1/data/market-edge-coverage and python -m app.cli audit-market-edge-coverage. It reports
  aggregate event, prediction, exact 1X2 decision-window, two-bookmaker, explicit closing, final,
  and tax/constraint coverage with bounded blockers. It exposes no score, price, selection, CLV,
  ROI, profit, or return fields.
- [x] Verify deterministic API and CLI behavior, exact selection completeness, source-time
  cutoffs, separate bookmaker rows, contract thresholds, and fail-closed replay authorization.
  The configured receipt is 30/380 events, one prediction, 1,750 snapshots, Pamestoixima on 10
  events, Novibet on zero, and zero decision-window, closing, final, or cost-covered observations.
- [x] Add the frozen-cohort receipt to the Data operations dashboard with separate bookmaker rows,
  bounded blockers, endpoint-failure handling, and no performance or price fields. Replay remains
  visibly locked until acquisition is complete.
- [x] Add a machine-actionable audit-market-edge-coverage --fail-on-blockers mode. It preserves
  the JSON receipt and exits 4 unless blockers are empty and both acquisition and fixed replay are
  explicitly authorized; the ordinary reporting command remains exit 0 while collection runs.
