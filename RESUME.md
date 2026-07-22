# Resume Odds Data Onboarding

## Current checkpoint

- Branch: `main`; the working tree was clean at this checkpoint.
- Required bookmakers: Allwyn's Greek ΠΑΜΕ ΣΤΟΙΧΗΜΑ/Pamestoixima channel, Novibet, and bet365.
- The API and Data Operations coverage audit fail closed until all three bookmakers have permitted odds for a competition.
- The local ignored database contains 1,140 permitted Premier League results: 380 each for 2022/23, 2023/24, and 2024/25.
- Pinned CC0 source files are retained under the ignored `backend/data/imports/openfootball/` directory. Public hashes and source commits are recorded in `DATA_IMPORTS.md`.
- `python -m app.cli probe-target-bookmakers` safely checks whether the configured Odds-API.io account exposes all three required bookmakers.
- No real target-bookmaker odds have been imported yet.

## Security action required before resuming

The API key previously sent through chat must be considered exposed. Revoke it in the provider dashboard, create a replacement, and put the replacement only in the ignored repository-root `.env`:

```env
ODDSQUANT_ODDS_API_IO_KEY=<replacement-key>
ODDSQUANT_ODDS_API_IO_BASE_URL=https://api.odds-api.io/v3
```

Never paste the replacement into chat, logs, tests, documentation, commits, screenshots, or command arguments.

## Resume sequence

From `backend`:

1. Run `python -m app.cli probe-target-bookmakers`.
2. Require `complete: true` with Allwyn/Pamestoixima, Novibet, and bet365 all active. Stop if any are missing.
3. Implement the credentialed event/odds collector using the existing client in `app/providers/odds_api_io.py`.
4. Start with complete pre-match full-time 1X2 snapshots only. Preserve the provider event ID, bookmaker identity, source update timestamp, observation timestamp, kickoff, currency, and settlement rules.
5. Reject partial outcome sets, post-kickoff pre-match observations, ambiguous team/event identity, and any response lacking a trustworthy timestamp.
6. Add deterministic provider-normalization and scheduler tests before running a live import.
7. Import one narrow Premier League window, rerun the coverage audit, and record only reproducible source/licence metadata—never raw licensed payloads or the local database—in version control.
8. Add closing snapshots only when the feed supplies explicit timestamped closing evidence strictly before kickoff. Never infer a closing flag from an untimestamped final price.

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
