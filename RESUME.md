# Resume UEFA And Bet-Builder Coverage

## Current checkpoint

- Branch: `main`. Implementation checkpoints `4426763` and `22ca928` are pushed.
- The replacement Odds-API.io key remains only in the ignored root `.env`.
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

## Next action

Keep scheduled polling active for UEFA main-stage fixtures and newly appearing shot/player
market metadata. Do not ingest player props when they first appear. First obtain and record
stable provider player IDs, a licensed timestamped player result source, and explicit
bookmaker settlement rules; then add deterministic settlement and chronological evaluation
tests in a separate checkpoint.

Continue to add closing snapshots only when the provider supplies explicit source-timestamped
closing evidence strictly before kickoff.

## Resume sequence

From `backend`:

1. Run `python -m app.cli probe-target-bookmakers` and require `complete: true`.
2. Run `python -m app.cli probe-bet-builder-markets` for sanitized availability metadata.
3. Poll through the registered scheduler collector for normal atomic imports.
4. Rerun `GET /api/v1/data/coverage` after each accepted batch.
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
