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

## Next action

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
4. Run `python -m app.cli monitor-collection` (or `GET /api/v1/data/monitoring`) after each
   accepted batch; require fresh consecutive jobs and review the embedded coverage blockers.
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
