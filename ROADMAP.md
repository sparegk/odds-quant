# Roadmap

## Phase 0: Foundation

- Repository, configuration, schema, provider contracts, quantitative primitives, health API, tests, and documentation.

## Phase 1: Runnable Football MVP

Completed slices: Alembic schema lifecycle, labelled demo odds and results, atomic CSV ingestion, stored-data API, connected React research dashboards, a local-date Matchday workspace, scheduled-provider boundary, full-stack deployment configuration, backend/frontend CI, a versioned leakage-safe Poisson baseline, stored scoreline predictions, scoreline-based bet builders, signal-return backtests, bankroll research, and browser-tested write workflows. Live deployment has not been claimed or tested.

- Alembic migration and deterministic labelled demo dataset.
- Timestamped team, player, coach, roster, appearance, availability, lineup, formation, tactical, and matchup data contracts.
- Atomic CSV odds import and manual coherent-market entry.
- Completed: dashboard-driven atomic odds/result/player-availability imports and full timestamped football-intelligence bundle ingestion.
- Completed: tax-aware football arbitrage engine for complete 1X2, over/under, and BTTS markets, including best-price selection, per-leg taxes/fees, rounded stake optimization, provenance fingerprints, conservative net-profit ranking, and execution-risk warnings.
- Completed: leakage-safe Poisson training, sampling intervals, immutable versions, and scoreline-derived predictions.
- Completed: expanding-window chronological evaluation, immutable replay evidence, Brier/log-loss/ECE metrics, calibration buckets, uniform and optional market benchmarks, and a non-demo promotion policy.
- Completed: point-in-time Davidson-style Elo forecasts and a persisted Poisson-versus-Elo proper-score comparison exposed in Model Performance.
- Completed: time-decayed Dixon–Coles fitting with bounded low-score correction, chronological held-out replay, persisted proper scores, and dashboard comparison.
- Completed: gated explainable value signals, best-price selection, compatible market consensus, lower-bound EV, freshness and movement checks, immutable calibration provenance, and positive-EV team-underdog ranking.
- Remaining: adequate permitted evaluation history, further independently justified model benchmarks, and independently validated confidence thresholds.
- Recency-weighted player and lineup strength, coach-regime handling, tactical matchup features, scenario sensitivity, and walk-forward ablation tests.
- Completed: value, underdog, arbitrage, bet-builder, backtesting, and bankroll dashboard pages with typed API integration and partial-resource failure states.
- Completed: protected model operations for training, evaluation, prediction, and signal generation; sourced tax/constraint management; per-tab readiness; automatic post-write synchronization; preserved event context; and success notifications.
- Completed: Matchday API and dashboard with featured-league grouping, timezone-correct day boundaries, pre-cutoff team form, selection-specific best prices, model/signal separation, and fail-closed player and builder states.
- Completed: reproducible scoreline-based bet-builder quote APIs with correlated joint probability, uncertainty, manual offered-price provenance, and immutable prediction/model fingerprints.
- Completed: expanding-window probability replay plus timestamp-valid stored-signal return backtests and flat, percentage, and capped fractional-Kelly bankroll simulation with exposure limits.
- Remaining: adequate permitted signal/result history, timestamped closing prices for CLV coverage, richer benchmarks, and independently validated staking/confidence thresholds. Demo backtests remain software evidence only.
- Connected React dashboard, Docker Compose, CI, and deployment configuration.
- Completed: Playwright Chromium workflows for ingestion-to-signals, sourced arbitrage calculation, and backtest-to-bankroll, alongside the Vitest component/API suite.
- Completed: timestamp-valid same-market/bookmaker/provider closing-price provenance, per-observation CLV, aggregate coverage/mean/median reporting, and explicit exclusion of post-kickoff closing evidence from retrospective metrics.
- Remaining: adequate permitted closing-price history across target competitions; closing evidence remains retrospective and is never fed into predictions or signals.

## Later Phases

- Licensed live provider adapters, independently justified comparison models, richer calibration, more competitions, and additional sports.
- Fixture/result and multi-book odds adapters for the requested leagues after credentials, coverage, rate limits, retention, and terms are approved; then independently licensed player/lineup data and identity reconciliation.
- No player props until reliable timestamped player targets, availability histories, settlement rules, and an independently calibrated player-level model exist.
