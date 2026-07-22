# Resume Odds Data Onboarding

## Current checkpoint

- Branch: `main`; the working tree was clean at this checkpoint.
- Required bookmakers: Allwyn's Greek ΠΑΜΕ ΣΤΟΙΧΗΜΑ/Pamestoixima channel, Novibet, and bet365.
- The API and Data Operations coverage audit fail closed until all three bookmakers have permitted odds for a competition.
- The replacement Odds-API.io key is configured in the ignored root `.env`.
- The authenticated provider selection currently contains Pamestoixima and Novibet only.
  The corrected probe reports `missing_bookmakers: ["bet365"]` and `complete: false`.
- A credentialed Premier League collector is implemented and scheduler-registered. It
  accepts only complete timestamped pre-kickoff full-time 1X2 snapshots and fails closed
  before event requests while a target bookmaker is not selected.
- The local ignored database contains 1,140 permitted Premier League results: 380 each for 2022/23, 2023/24, and 2024/25.
- Pinned CC0 source files are retained under the ignored `backend/data/imports/openfootball/` directory. Public hashes and source commits are recorded in `DATA_IMPORTS.md`.
- `python -m app.cli probe-target-bookmakers` safely checks the authenticated account's
  selected bookmakers, rather than the provider's global bookmaker catalog.
- No real target-bookmaker odds have been imported yet.

## Provider action required before resuming

Select bet365 for the authenticated Odds-API.io account in the provider dashboard. The
current account selection has only two bookmakers, and an odds request for all three returns
HTTP 403. A plan or selection-limit change may be required. Do not bypass this gate by
collecting or importing only the other two bookmakers.

Keep the replacement key only in the ignored root `.env`. Never paste it into chat, logs,
tests, documentation, commits, screenshots, or command arguments.

## Resume sequence

From `backend`:

1. Select bet365 in the provider dashboard, then run
   `python -m app.cli probe-target-bookmakers`.
2. Require `complete: true` with Allwyn/Pamestoixima, Novibet, and bet365 all selected.
   Stop if any are missing.
3. Run a read-only live normalization check, then import one narrow Premier League window
   through the scheduler collector.
4. Rerun the coverage audit and record only reproducible source/licence metadata—never raw
   licensed payloads or the local database—in version control.
5. Add closing snapshots only when the feed supplies explicit timestamped closing evidence
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

Do not scrape the three bookmaker websites directly, weaken atomic ingestion, fabricate historical timestamps, or present demo/research results as profitable evidence.
