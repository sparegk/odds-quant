export interface ProjectStatus {
  phase: string
  sports: string[]
  data_mode: string
  automated_betting: boolean
}

export interface EventSummary {
  id: number
  provider_event_key: string
  competition_id?: number
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

export interface ImportUploadResult {
  job_id: number
  status: string
  rows_received: number
  rows_imported: number
  snapshots_created?: number
  results_created?: number
  created?: Record<string, number>
  content_sha256?: string
}

export interface SelectionPrediction {
  id: number
  market_id: number
  market_type: string
  line: number | null
  selection_id: number
  selection_code: string
  selection_name: string
  probability: number
  lower_probability: number
  upper_probability: number
  fair_odds: number
}

export interface ModelOutput {
  id: number
  event_id: number
  model_version_id: number
  model_version: string
  predicted_at: string
  inputs_as_of: string
  evidence_class: string
  home_lambda: number
  away_lambda: number
  sample_size: number
  score_matrix: number[][]
  derived_probabilities: Record<string, Record<string, number>>
  predictions: SelectionPrediction[]
}

export interface BetBuilderLeg {
  market_type: string
  selection: string
  line: number | null
  marginal_probability: number
}

export interface BetBuilderQuote {
  id: number
  event_id: number
  model_version_id: number
  model_version: string
  is_demo: boolean
  evidence_class: string
  prediction_output_id: number
  predicted_at: string
  inputs_as_of: string
  quoted_at: string
  fingerprint: string
  feature_version: string
  input_fingerprint: string
  legs: BetBuilderLeg[]
  joint_probability: number
  lower_joint_probability: number
  upper_joint_probability: number
  independent_product: number
  dependence_ratio: number
  fair_odds: number
  offered_odds: number | null
  offered_odds_source: string | null
  offered_odds_observed_at: string | null
  expected_value: number | null
  lower_expected_value: number | null
  warnings: string[]
}

export interface CreateBetBuilderQuote {
  event_id: number
  prediction_output_id: number
  legs: Array<{ market_type: string; selection: string; line: number | null }>
  offered_odds?: number
  offered_odds_source?: string
  offered_odds_observed_at?: string
  quoted_at: string
}

export interface SignalBacktestObservation {
  id: number
  event_id: number
  selection_id: number
  prediction_id: number
  odds_snapshot_id: number
  predicted_at: string
  settled_at: string
  market_type: string
  selection_code: string
  decimal_odds: number
  model_probability: number
  lower_probability: number
  expected_value: number
  settlement: string
  stake: number
  profit_units: number
  closing_odds_snapshot_id?: number | null
  closing_decimal_odds?: number | null
  closing_observed_at?: string | null
  closing_line_value?: number | null
}

export interface SignalBacktest {
  id: number
  model_version_id: number
  model_version: string
  status: string
  evaluation_start: string
  evaluation_end: string
  fingerprint: string
  evaluation_status: string
  is_demo: boolean
  config: Record<string, unknown>
  policy: Record<string, unknown>
  metrics: Record<string, unknown>
  observations: SignalBacktestObservation[]
  created_at: string
}

export interface BankrollPoint {
  observation_id: number
  bankroll: number
  stake: number
  profit: number
  drawdown: number
}

export interface BankrollSimulation {
  backtest_run_id: number
  backtest_fingerprint: string
  simulation_fingerprint: string
  strategy: string
  initial_bankroll: number
  final_bankroll: number
  total_staked: number
  net_profit: number
  roi: number
  maximum_drawdown: number
  maximum_drawdown_fraction: number
  bets_placed: number
  bets_skipped: number
  is_demo: boolean
  warnings: string[]
  points: BankrollPoint[]
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
  | 'backtests'
  | 'readiness'

export interface ReadinessCounts {
  events: number
  odds_snapshots: number
  final_results: number
  model_versions: number
  predictions: number
  non_demo_calibrated_evaluations: number
  signals: number
  signal_backtests: number
  bookmaker_tax_mappings: number
  bookmaker_constraints: number
  intelligence_records: number
}

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

export interface SignalBatch {
  event_id: number
  output_id: number
  model_version_id: number
  evaluation_run_id: number
  generated_at: string
  signals: ValueSignal[]
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

export interface ArbitrageBatch {
  event_id: number
  calculated_at: string
  opportunities: ArbitrageOpportunity[]
}

export interface ArbitrageBookmaker {
  id: number
  slug: string
  name: string
  is_demo: boolean
}

export interface ArbitrageTaxProfile {
  id: number
  bookmaker_id: number
  bookmaker: string
  name: string
  jurisdiction: string
  currency: string
  stake_tax_rate: string
  winnings_tax_rate: string
  payout_withholding_rate: string
  commission_rate: string
  fixed_fee: string
  effective_from: string
  effective_to: string | null
  verified_at: string
  source_url: string | null
  source_label: string
  status: string
}

export interface ArbitrageConstraint {
  id: number
  bookmaker_id: number
  bookmaker: string
  currency: string
  minimum_stake: string
  maximum_stake: string | null
  stake_increment: string
  observed_at: string
  source_label: string
}

export interface ArbitrageSettings {
  bookmakers: ArbitrageBookmaker[]
  tax_profiles: ArbitrageTaxProfile[]
  constraints: ArbitrageConstraint[]
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

export interface MatchdayEvent {
  event: EventSummary
  market_count: number
  bookmaker_count: number
  latest_prediction_at: string | null
  qualified_signal_count: number
}

export interface MatchdayCompetition {
  competition_id: number
  name: string
  country: string
  season: string
  group_key: string
  group_label: string
  priority: number
  is_featured: boolean
  events: MatchdayEvent[]
}

export interface Matchday {
  date: string
  timezone: string
  local_start: string
  local_end: string
  as_of: string
  total_events: number
  competitions: MatchdayCompetition[]
  data_note: string
}

export interface RecentTeamResult {
  event_id: number
  kickoff_at: string
  opponent: string
  venue: 'home' | 'away'
  goals_for: number
  goals_against: number
  outcome: 'W' | 'D' | 'L'
  observed_at: string
}

export interface TeamForm {
  team_id: number
  team: string
  sample_size: number
  wins: number
  draws: number
  losses: number
  goals_for: number
  goals_against: number
  clean_sheets: number
  points_per_game: number | null
  results: RecentTeamResult[]
  warnings: string[]
}

export interface ResearchGate {
  status: 'available' | 'blocked'
  title: string
  available_records: number
  reasons: string[]
}

export interface MatchdayEventDetail {
  event: EventSummary
  competition_group: string
  competition_group_label: string
  as_of: string
  team_form: TeamForm[]
  markets: MarketComparison[]
  latest_prediction: ModelOutput | null
  signals: ValueSignal[]
  builder_quotes: BetBuilderQuote[]
  player_research: ResearchGate
  builder_value: ResearchGate
  bookmaker_guidance: string
  evidence_note: string
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
  backtests: SignalBacktest[]
  readiness?: ReadinessCounts
  resource_errors: Partial<Record<DashboardResource, string>>
}
