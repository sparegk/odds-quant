export interface ProjectStatus {
  phase: string
  sports: string[]
  data_mode: string
  automated_betting: boolean
}

export interface EventSummary {
  id: number
  provider_event_key: string
  competition: string
  country: string
  season: string
  home_team: string
  away_team: string
  kickoff_at: string
  status: string
  is_demo: boolean
  latest_odds_at: string | null
}

export interface ProviderSummary {
  id: number
  slug: string
  name: string
  kind: string
  is_demo: boolean
  terms_url: string | null
  capabilities: Record<string, unknown>
  event_count: number
  snapshot_count: number
}

export interface ImportJob {
  id: number
  filename: string
  status: string
  rows_received: number
  rows_imported: number
  errors: Array<Record<string, unknown>>
  created_at: string
}

export interface ProviderJob {
  id: number
  provider_id: number
  provider: string
  job_type: string
  status: string
  message: string
  created_at: string
  finished_at: string | null
}

export interface ModelVersion {
  id: number
  name: string
  version: string
  kind: string
  training_start: string
  training_end: string
  data_fingerprint: string
  feature_version: string
  sample_size: number
  evaluation_status: string
  config: Record<string, unknown>
  metrics: Record<string, unknown>
  status: string
  is_demo: boolean
  created_at: string
}

export interface PriceComparison {
  selection_code: string
  selection_name: string
  decimal_odds: number
  raw_implied_probability: number
  proportional_fair_probability: number
  proportional_fair_odds: number
  power_fair_probability: number
  power_fair_odds: number
}

export interface SnapshotComparison {
  snapshot_id: number
  bookmaker_id: number
  bookmaker: string
  provider: string
  observed_at: string
  source_updated_at: string | null
  is_closing: boolean
  is_demo: boolean
  source_label: string
  freshness_seconds: number
  is_stale: boolean
  overround: number
  bookmaker_margin: number
  prices: PriceComparison[]
}

export interface BestPrice {
  selection_code: string
  selection_name: string
  bookmaker: string
  decimal_odds: number
  observed_at: string
  freshness_seconds: number
}

export interface MarketComparison {
  market_id: number
  market_type: string
  line: number | null
  period: string
  currency: string
  settlement_rule_key: string
  snapshots: SnapshotComparison[]
  best_prices: BestPrice[]
}

export interface DashboardData {
  status: ProjectStatus
  events: EventSummary[]
  providers: ProviderSummary[]
  imports: ImportJob[]
  jobs: ProviderJob[]
  models: ModelVersion[]
}
