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

export type DashboardResource =
  | 'status'
  | 'events'
  | 'providers'
  | 'imports'
  | 'jobs'
  | 'models'
  | 'evaluations'
  | 'signals'
  | 'underdogs'
  | 'arbitrage'

export interface CalibrationBucket {
  selection_code: string
  bucket_index: number
  lower_bound: number
  upper_bound: number
  count: number
  mean_predicted: number
  observed_frequency: number
  absolute_error: number
}

export interface EvaluationRun {
  id: number
  model_version_id: number
  model_version: string
  status: string
  evaluation_start: string
  evaluation_end: string
  fingerprint: string
  config: Record<string, unknown>
  policy: Record<string, unknown>
  evaluation_status: string
  is_demo: boolean
  metrics: Record<string, unknown>
  benchmarks: Record<string, Record<string, unknown>>
  calibration: CalibrationBucket[]
  created_at: string
}

export interface ValueSignal {
  id: number
  event_id: number
  output_id: number
  model_version_id: number
  model_version: string
  evaluation_run_id: number
  prediction_id: number
  market_id: number
  market_type: string
  line: number | null
  selection_id: number
  selection_code: string
  selection_name: string
  bookmaker_id: number
  bookmaker: string
  odds_snapshot_id: number
  signal_type: string
  offered_odds: number
  raw_implied_probability: number
  market_fair_probability: number
  model_probability: number
  lower_probability: number
  expected_value: number
  lower_expected_value: number
  probability_edge: number
  confidence: number
  calibration_error: number
  odds_age_minutes: number
  bookmaker_count: number
  odds_move_ratio: number
  implied_move_points: number
  generated_at: string
  reasons: string[]
  risks: string[]
}

export interface ArbitrageLeg {
  id: number
  selection_id: number
  selection_code: string
  selection_name: string
  bookmaker_id: number
  bookmaker: string
  odds_snapshot_id: number
  tax_profile_id: number | null
  bookmaker_constraint_id: number | null
  decimal_odds: number
  stake: number
  cash_outlay: number
  gross_payout: number
  win_deductions: number
  taxes_and_fees: number
  net_payout: number
}

export interface ArbitrageOpportunity {
  id: number
  event_id: number
  market_id: number
  market_type: string
  line: number | null
  period: string
  settlement_rule_key: string
  calculated_at: string
  fingerprint: string
  status: string
  inverse_sum: number
  budget: number
  total_cash_outlay: number
  minimum_net_payout: number
  net_profit: number
  net_roi: number
  tax_status: string
  constraint_status: string
  freshness_status: string
  currency: string
  risks: string[]
  legs: ArbitrageLeg[]
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
  evaluations: EvaluationRun[]
  signals: ValueSignal[]
  underdogs: ValueSignal[]
  arbitrage: ArbitrageOpportunity[]
  resource_errors: Partial<Record<DashboardResource, string>>
}
