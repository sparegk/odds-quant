# Resume Odds Data Onboarding

## Current checkpoint

- Branch: `main`; the working tree was clean at this checkpoint.
- Required bookmakers: Allwyn's Greek ΠΑΜΕ ΣΤΟΙΧΗΜΑ/Pamestoixima channel and Novibet.
- The API and Data Operations coverage audit fail closed until both bookmakers have permitted odds for a competition.
- The replacement Odds-API.io key is configured in the ignored root `.env`.
- The authenticated provider selection contains both required bookmakers.
- A credentialed Premier League collector is implemented and scheduler-registered. It
  accepts only complete timestamped pre-kickoff full-time 1X2 snapshots and fails closed
  before event requests while a target bookmaker is not selected.
- The local ignored database contains 1,140 permitted Premier League results: 380 each for 2022/23, 2023/24, and 2024/25.
- Pinned CC0 source files are retained under the ignored `backend/data/imports/openfootball/` directory. Public hashes and source commits are recorded in `DATA_IMPORTS.md`.
- `python -m app.cli probe-target-bookmakers` safely checks the authenticated account's
  selected bookmakers, rather than the provider's global bookmaker catalog.
- One atomic live import completed with 30 prices across 10 complete Pamestoixima 1X2
  snapshots for 10 upcoming 2026/27 Premier League events. The live window returned no
  complete Novibet match-result snapshots and no explicit closing evidence.
- The coverage audit recognizes Pamestoixima and remains blocked by missing Novibet odds,
  no closing prices, and fewer than 200 final results for the 2026/27 competition.

## Next action

Continue scheduled polling for complete Novibet match-result snapshots. Add closing
snapshots only if the provider supplies explicit source-timestamped closing evidence before
kickoff; do not infer it from the last observed price.

Keep the replacement key only in the ignored root `.env`. Never paste it into chat, logs,
tests, documentation, commits, screenshots, or command arguments.

## Resume sequence

From `backend`:

1. Keep both target bookmakers selected and poll through the scheduler collector.
2. Require complete timestamped Novibet 1X2 snapshots before counting Novibet coverage.
3. Rerun the coverage audit after each accepted live batch.
4. Add closing snapshots only when the feed supplies explicit timestamped closing evidence
   strictly before kickoff. Never infer a closing flag from an untimestamped final price.

## Verification and commit discipline

After each completed checkbox, run the relevant tests, commit with a focused message, and push `main`. Before declaring the odds collector complete, run:

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

Do not scrape bookmaker websites directly, weaken atomic ingestion, fabricate historical timestamps, or present demo/research results as profitable evidence.
