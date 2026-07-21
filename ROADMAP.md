# Roadmap

## Phase 0: Foundation

- Repository, configuration, schema, provider contracts, quantitative primitives, health API, tests, and documentation.

## Phase 1: Runnable Football MVP

Completed slices: Alembic schema lifecycle, labelled demo odds and results, atomic CSV ingestion, stored-data API, connected React research dashboards, scheduled-provider boundary, full-stack deployment configuration, backend/frontend CI, a versioned leakage-safe Poisson baseline, stored scoreline predictions, scoreline-based bet builders, signal-return backtests, and bankroll research. Live deployment has not been claimed or tested.

- Alembic migration and deterministic labelled demo dataset.
- Timestamped team, player, coach, roster, appearance, availability, lineup, formation, tactical, and matchup data contracts.
- Atomic CSV odds import and manual coherent-market entry.
- Completed: tax-aware football arbitrage engine for complete 1X2, over/under, and BTTS markets, including best-price selection, per-leg taxes/fees, rounded stake optimization, provenance fingerprints, conservative net-profit ranking, and execution-risk warnings.
- Completed: leakage-safe Poisson training, sampling intervals, immutable versions, and scoreline-derived predictions.
- Completed: expanding-window chronological evaluation, immutable replay evidence, Brier/log-loss/ECE metrics, calibration buckets, uniform and optional market benchmarks, and a non-demo promotion policy.
- Completed: gated explainable value signals, best-price selection, compatible market consensus, lower-bound EV, freshness and movement checks, immutable calibration provenance, and positive-EV team-underdog ranking.
- Remaining: adequate permitted evaluation history, richer model benchmarks, and independently validated confidence thresholds.
- Recency-weighted player and lineup strength, coach-regime handling, tactical matchup features, scenario sensitivity, and walk-forward ablation tests.
- Completed: value, underdog, arbitrage, bet-builder, backtesting, and bankroll dashboard pages with typed API integration and partial-resource failure states.
- Completed: reproducible scoreline-based bet-builder quote APIs with correlated joint probability, uncertainty, manual offered-price provenance, and immutable prediction/model fingerprints.
- Completed: expanding-window probability replay plus timestamp-valid stored-signal return backtests and flat, percentage, and capped fractional-Kelly bankroll simulation with exposure limits.
- Remaining: adequate permitted signal/result history, timestamped closing prices for CLV coverage, richer benchmarks, and independently validated staking/confidence thresholds. Demo backtests remain software evidence only.
- Connected React dashboard, Docker Compose, CI, and deployment configuration.

## Later Phases

- Licensed live provider adapters, Dixon-Coles and comparison models, richer calibration, more competitions, and additional sports.
- No player props until reliable timestamped player targets, availability histories, settlement rules, and an independently calibrated player-level model exist.
