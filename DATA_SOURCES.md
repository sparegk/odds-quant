# Data Sources And Freshness

## Source Policy

OddsQuant may ingest football data from licensed sports-data APIs, official competition or club sources, user-uploaded CSV files, manual entries, and clearly labelled demo data. It must not scrape protected bookmaker or sports-data services, bypass access controls, or infer that a named bookmaker exposes a public API.

Every record must identify its provider, source type, source key, source update time, ingestion time, effective period, and whether it is real, manually entered, or generated. Raw permitted responses should be retained immutably with a checksum so normalization can be reproduced.

## Matchday Provider Split

A production Matchday should not pretend one feed covers every evidence layer. The intended provider split is:

- Fixtures, competition identity, status, and final results from a permitted football-data provider. [football-data.org's official v4 documentation](https://docs.football-data.org/general/v4/coding_client.html) exposes current-day and competition match resources and is suitable for an initial schedule/result adapter after plan, coverage, rate-limit, and terms review.
- Deeper lineups, sidelined players, formations, events, and player/team statistics from a licensed detailed-data plan. [Sportmonks' official fixture documentation](https://docs.sportmonks.com/v3/endpoints-and-entities/endpoints/fixtures/get-all-fixtures) documents optional lineup, statistics, odds, expected-lineup, and related includes; actual availability depends on the subscribed plan and league coverage.
- Multi-bookmaker prices from a licensed or expressly permitted odds feed. [The Odds API's official soccer coverage](https://the-odds-api.com/sports-odds-data/) includes the requested major leagues and UEFA competitions, but market and bookmaker coverage is region- and competition-dependent.
- The implemented Odds-API.io adapter is restricted to pending England Premier League
  events and complete, timestamped, full-time 1X2 snapshots from the configured target
  bookmakers. It checks the authenticated account's selected bookmakers before collection,
  batches at most ten events per odds request, and rejects conflicting identity, incomplete
  outcomes, missing source timestamps, and timestamps at or after kickoff.
- Official club or competition publications for confirmed lineups and availability corrections when licensing permits storage and the original publication timestamp is retained.

Provider selection is a deployment decision, not a hard-coded endorsement. Before registration, record the exact competitions, countries, bookmakers, historical depth, update latency, redistribution rights, retention terms, rate limits, and stable identity keys. Player-prop availability from an odds feed does not remove the independent target, settlement, and calibration gates.

## Odds CSV Contract

The implemented `odds-csv-v1` importer accepts UTF-8 files up to 5 MiB and 20,000 rows. Required fields identify the provider event, competition and season, teams, offset-aware kickoff and observation times, bookmaker, market, selection, and decimal price. Optional fields carry the market line, provider update time, period, currency, settlement key, and closing flag.

Rows are grouped into bookmaker snapshots by event, market, line, period, currency, settlement rule, and observation time. Each group must contain the exact complete selection set for its market. An incomplete 1X2, totals, both-teams-to-score, double-chance, or supported team-total snapshot rejects the entire import; so do duplicate outcomes, future observations, post-kickoff pre-match prices, conflicting event identities, mixed closing flags, and odds at or below 1.0.

Accepted files preserve their SHA-256 digest and normalized payload in `raw_ingestions`. Rejected files create an auditable import job but cannot partially create football or odds records. Re-importing an identical snapshot is idempotent; reusing the same identity with changed prices is rejected rather than rewriting history.

## Permitted Coverage Audit

`GET /api/v1/data/coverage` and the Data Operations dashboard audit count only records whose event provider and, for prices, bookmaker are non-demo. They report coverage separately by competition so volume in one league cannot conceal a gap in another. The current evaluation readiness gate requires:

- at least one permitted event and team set;
- at least 200 permitted final results;
- timestamped permitted odds snapshots; and
- permitted closing snapshots observed strictly before kickoff.
- bookmaker-specific coverage for Allwyn's Greek ΠΑΜΕ ΣΤΟΙΧΗΜΑ/Pamestoixima channel, Novibet, and bet365.

The audit is an evidence-availability gate, not proof that a source is licensed, representative, unbiased, or suitable for production. Source terms and the provider registry remain authoritative. A passing audit also does not promote a model; chronological evaluation, calibration, benchmark, and promotion-policy requirements still apply.

## Football Data Required

### Teams And Matches

- Competition, season, venue, kickoff, status, and verified result.
- Goals, expected goals where licensed, shots, possession, field tilt, passing, pressing, transitions, set pieces, cards, and substitutions.
- Home/away splits, opponent strength, rest days, travel, schedule congestion, and competition context.
- Rolling and exponentially weighted form calculated strictly before the target kickoff.

Metric definitions must be provider-versioned. Similar names from different providers must not be merged until units, event definitions, and coverage are reconciled.

### Players And Availability

- Stable player identity, team registration, position, role, age band, and preferred side where licensed.
- Appearances, starts, minutes, substitutions, and position-specific per-90 statistics.
- Attacking, progression, creation, defensive, pressing, aerial, set-piece, and goalkeeper measures appropriate to the player's role.
- Injury, illness, suspension, registration, rotation, and return-to-play status with observation and effective timestamps.
- Expected lineup probabilities and confirmed lineup snapshots stored as different evidence classes.

Raw per-90 values require minimum-minute thresholds and shrinkage toward position and competition priors. Recent performance uses configurable rolling windows and exponential decay, with season and competition strength adjustments. A short hot streak must not be treated as a stable player effect.

### Coaches, Lineups, And Tactics

- Coach tenure, recent appointment, formation usage, starting shape, in-possession and out-of-possession roles where available.
- Pressing intensity, defensive block, line height, width, build-up route, tempo, directness, transition behavior, set-piece strength, and substitution patterns.
- Timestamped expected and confirmed starting elevens, bench, captain, formation, and role changes.

A coaching change is a regime change with high initial uncertainty, not an automatic improvement. Tactical labels must come from reproducible event data or a documented provider field; unsupported narrative labels are not model inputs.

## Matchup Features

Football matchups are contextual rather than fixed one-on-one contests. Candidate interactions include press versus build-up resistance, pace versus a high defensive line, aerial attack versus aerial defense, set-piece delivery versus set-piece prevention, flank overloads, transition attack versus rest defense, and key creator or finisher availability.

Each interaction must have:

- A precise quantitative definition.
- Data available before prediction time.
- Adequate samples for both sides and relevant roles.
- Opponent and competition adjustment.
- Shrinkage or regularization.
- Walk-forward evidence that it improves calibration out of sample.

Player, team, and tactical features can describe the same effect. Feature design and ablation tests must prevent double counting. Direct player-versus-player history is used only with adequate comparable minutes and roles; otherwise the model uses role-versus-system interactions and reports wider uncertainty.

## Freshness Contract

The system distinguishes `source_updated_at`, `observed_at`, `ingested_at`, and `effective_from`. Data age is measured from the provider observation or update time, never merely from the time OddsQuant received it.

- Event metadata is refreshed at least daily when kickoff is distant and more frequently inside 24 hours.
- Availability reports are refreshed whenever the permitted source changes and at scheduled pre-match checkpoints.
- Expected lineups remain provisional and carry scenario uncertainty.
- Confirmed lineups are collected when officially released, normally near kickoff, and trigger a new prediction version.
- Odds used for ordinary opportunity ranking default to `FRESH` through five minutes, `AGING` through fifteen minutes, and `STALE` afterward.
- Arbitrage legs require a stricter configurable window and low cross-leg timestamp skew; stale legs are never ranked as executable.
- Closing odds are the last valid snapshot strictly before kickoff. Post-kickoff data can never be relabelled as closing data.
- Results become training data only after final status and reconciliation. Corrections create a new version rather than silently rewriting lineage.

User result CSVs require canonical event/team identity, final home and away goals, kickoff, settlement, provider observation, and optional source-update timestamps. The importer rejects naive timestamps, future observations, negative goals, conflicting provider event identities, and settlement times before kickoff or after observation. Every accepted payload is retained with a content hash; later score corrections append a `supersedes_id` chain.

Training canonicalizes results by competition, kickoff, home team, and away team so the same fixture from multiple permitted providers is counted once. Consistent duplicates use the latest observation available by the cutoff; conflicting final scores block training until the source discrepancy is resolved.

Freshness thresholds are configurable per provider and competition because update schedules differ, but any override must be visible and tested. A provider's slower rate limit may reduce coverage; it must not be hidden by pretending cached data is current.

## Adaptive Collection

Collectors should poll more often as kickoff approaches while staying within provider terms and documented rate limits. They use conditional requests where supported, exponential backoff, jitter, retry budgets, and job-level observability. Repeated payload hashes, out-of-order timestamps, clock skew, partial markets, and implausible jumps are flagged.

No collector should optimize frequency at the expense of legality or validity. If the licensed source cannot provide sufficiently fresh data for a use case, the UI reports that limitation and disables strong signals or arbitrage ranking.

## Storage And Retention

The current implementation retains accepted raw and normalized records; it does not run an automatic deletion job. Normalized fixtures, final results, model inputs, odds referenced by predictions or backtests, and all records referenced by a model version, signal, builder quote, arbitrage calculation, or evaluation must not be pruned because they are required for reproducibility.

To control production storage, move immutable raw payloads to compressed object storage and keep their content hash and archive location in the database. Exact duplicate transport payloads, expired operational logs, and unreferenced rejected-upload bodies may use an explicit retention window after audit requirements are reviewed. Post-event odds may be downsampled only through a tested policy that preserves opening, defined pre-kickoff checkpoints, the last valid closing snapshot, and every referenced snapshot. No manual cleanup should delete a record still reachable from research evidence.

## Modelling And Leakage Rules

Every feature row carries an `as_of` cutoff. A prediction may use only records whose source evidence was available at or before its prediction timestamp. Historical backtests cannot use confirmed lineups, injury outcomes, coach decisions, or corrected statistics unless their historical publication time is known and precedes the simulated prediction.

The first model remains a team-level Poisson baseline. Player, coach, lineup, and matchup adjustments are added only after the underlying data passes coverage and timestamp audits. They improve match-level markets first. Player props remain out of scope until player-level targets, settlement rules, availability history, and calibration are independently validated.

## Quality Gates

A record or prediction is rejected, quarantined, or downgraded when:

- Event, team, player, market, line, or period identity is ambiguous.
- Required outcomes or minutes are missing.
- Provider timestamps are absent, out of order, or implausibly skewed.
- A lineup is presented as confirmed without official confirmation.
- Player availability conflicts across sources without a resolution policy.
- Metric definitions changed without a provider schema version.
- Information was published after the model cutoff.
- The prediction is overly sensitive to unresolved player or tactical scenarios.

The dashboard must display source, age, lineup status, missingness, and the main data-quality limitations next to each model or opportunity.
