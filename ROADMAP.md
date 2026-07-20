# Roadmap

## Phase 0: Foundation

- Repository, configuration, schema, provider contracts, quantitative primitives, health API, tests, and documentation.

## Phase 1: Runnable Football MVP

Completed slices: Alembic schema lifecycle, labelled demo odds and results, atomic CSV ingestion, stored-data API, connected React dashboard, scheduled-provider boundary, full-stack deployment configuration, backend/frontend CI, and a versioned leakage-safe Poisson baseline with stored scoreline predictions. Live deployment has not been claimed or tested.

- Alembic migration and deterministic labelled demo dataset.
- Timestamped team, player, coach, roster, appearance, availability, lineup, formation, tactical, and matchup data contracts.
- Atomic CSV odds import and manual coherent-market entry.
- Tax-aware football arbitrage engine for complete 1X2, over/under, and BTTS markets, including best-price selection, per-leg taxes/fees, rounded stake optimization, conservative net-profit ranking, and execution-risk warnings.
- Completed: leakage-safe Poisson training, sampling intervals, immutable versions, and scoreline-derived predictions.
- Completed: expanding-window chronological evaluation, immutable replay evidence, Brier/log-loss/ECE metrics, calibration buckets, uniform and optional market benchmarks, and a non-demo promotion policy.
- Completed: gated explainable value signals, best-price selection, compatible market consensus, lower-bound EV, freshness and movement checks, immutable calibration provenance, and positive-EV team-underdog ranking.
- Remaining: adequate permitted evaluation history, richer model benchmarks, independently validated confidence thresholds, and tax-aware arbitrage.
- Recency-weighted player and lineup strength, coach-regime handling, tactical matchup features, scenario sensitivity, and walk-forward ablation tests.
- Opportunity, underdog, arbitrage, odds comparison, event, and bet-builder APIs and dashboard pages.
- Walk-forward backtesting and bankroll simulation.
- Connected React dashboard, Docker Compose, CI, and deployment configuration.

## Later Phases

- Licensed live provider adapters, Dixon-Coles and comparison models, richer calibration, more competitions, and additional sports.
- No player props until reliable timestamped player targets, availability histories, settlement rules, and an independently calibrated player-level model exist.
