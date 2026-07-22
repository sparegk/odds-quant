import type {
  ArbitrageOpportunity,
  ArbitrageBatch,
  ArbitrageConstraint,
  ArbitrageSettings,
  ArbitrageTaxProfile,
  BankrollSimulation,
  BetBuilderQuote,
  CreateBetBuilderQuote,
  DashboardData,
  DashboardResource,
  EvaluationRun,
  EventSummary,
  ImportJob,
  ImportUploadResult,
  MarketComparison,
  Matchday,
  MatchdayEventDetail,
  ModelVersion,
  ModelOutput,
  ProjectStatus,
  ProviderJob,
  ProviderSummary,
  SignalBacktest,
  SignalBatch,
  ValueSignal,
} from '../types'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, '') ?? 'http://127.0.0.1:8000'

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message)
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { Accept: 'application/json', ...init?.headers },
  })
  if (!response.ok) {
    let detail = ''
    try {
      const body: unknown = await response.json()
      const message = apiProblemMessage(body)
      if (message) detail = ` — ${message}`
    } catch {
      // Non-JSON failures still retain their HTTP status.
    }
    throw new ApiError(`API request failed: ${response.status}${detail}`, response.status)
  }
  return (await response.json()) as T
}

function apiProblemMessage(body: unknown): string | null {
  if (typeof body !== 'object' || body === null || !('detail' in body)) return null
  if (typeof body.detail === 'string') return body.detail
  if (typeof body.detail !== 'object' || body.detail === null) return null
  const problem = body.detail as Record<string, unknown>
  const summary = typeof problem.detail === 'string' ? problem.detail : typeof problem.title === 'string' ? problem.title : null
  const errors: unknown[] = Array.isArray(problem.errors) ? problem.errors as unknown[] : []
  const first = errors[0]
  const firstRecord = typeof first === 'object' && first !== null ? first as Record<string, unknown> : null
  const firstMessage = firstRecord && typeof firstRecord.message === 'string' ? firstRecord.message : null
  return [summary, firstMessage].filter(Boolean).join(': ') || null
}

interface ResourceResult<T> {
  resource: DashboardResource
  data: T
  error?: string
}

async function loadResource<T>(resource: DashboardResource, path: string, fallback: T): Promise<ResourceResult<T>> {
  try {
    return { resource, data: await request<T>(path) }
  } catch (caught) {
    return {
      resource,
      data: fallback,
      error: caught instanceof Error ? caught.message : 'Unknown API error',
    }
  }
}

export async function loadDashboard(): Promise<DashboardData> {
  const [status, events, providers, imports, jobs, models, evaluations, signals, underdogs, arbitrage, backtests] = await Promise.all([
    loadResource<ProjectStatus>('status', '/api/v1/status', {
      phase: 'unavailable',
      sports: [],
      data_mode: 'unknown',
      automated_betting: false,
    }),
    loadResource<EventSummary[]>('events', '/api/v1/events?include_past=true', []),
    loadResource<ProviderSummary[]>('providers', '/api/v1/providers', []),
    loadResource<ImportJob[]>('imports', '/api/v1/imports', []),
    loadResource<ProviderJob[]>('jobs', '/api/v1/jobs', []),
    loadResource<ModelVersion[]>('models', '/api/v1/models', []),
    loadResource<EvaluationRun[]>('evaluations', '/api/v1/evaluations', []),
    loadResource<ValueSignal[]>('signals', '/api/v1/recommendations', []),
    loadResource<ValueSignal[]>('underdogs', '/api/v1/signals/underdogs', []),
    loadResource<ArbitrageOpportunity[]>('arbitrage', '/api/v1/arbitrage/opportunities', []),
    loadResource<SignalBacktest[]>('backtests', '/api/v1/backtests', []),
  ])
  const resources = [status, events, providers, imports, jobs, models, evaluations, signals, underdogs, arbitrage, backtests]
  const resource_errors = Object.fromEntries(
    resources.filter((result) => result.error).map((result) => [result.resource, result.error]),
  ) as DashboardData['resource_errors']
  return {
    status: status.data,
    events: events.data,
    providers: providers.data,
    imports: imports.data,
    jobs: jobs.data,
    models: models.data,
    evaluations: evaluations.data,
    signals: signals.data,
    underdogs: underdogs.data,
    arbitrage: arbitrage.data,
    backtests: backtests.data,
    resource_errors,
  }
}

export function loadComparison(eventId: number): Promise<MarketComparison[]> {
  return request<MarketComparison[]>(`/api/v1/odds/comparison?event_id=${eventId}`)
}

export function uploadCsv(
  kind: 'odds' | 'results' | 'availability',
  file: File,
  options: { adminKey?: string; sourceKey?: string; providerSlug?: string; providerName?: string } = {},
): Promise<ImportUploadResult> {
  const form = new FormData()
  form.append('file', file)
  if (kind === 'availability') {
    form.append('source_key', options.sourceKey ?? '')
    form.append('provider_slug', options.providerSlug ?? '')
    form.append('provider_name', options.providerName ?? '')
  }
  const path = kind === 'availability' ? '/api/v1/imports/intelligence/availability' : `/api/v1/imports/${kind}`
  return request<ImportUploadResult>(path, {
    method: 'POST',
    headers: options.adminKey ? { 'X-Admin-Key': options.adminKey } : undefined,
    body: form,
  })
}

export function importIntelligenceBundle(payload: Record<string, unknown>, adminKey?: string): Promise<ImportUploadResult> {
  return request<ImportUploadResult>('/api/v1/imports/intelligence', {
    method: 'POST', headers: adminJson(adminKey), body: JSON.stringify(payload),
  })
}

export function calculateArbitrage(payload: {
  event_id: number
  budget: number
  currency: string
  odds_stale_after_seconds: number
  tax_max_age_days: number
  constraint_max_age_minutes: number
}, adminKey?: string): Promise<ArbitrageBatch> {
  return request<ArbitrageBatch>('/api/v1/arbitrage/calculate', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(adminKey ? { 'X-Admin-Key': adminKey } : {}),
    },
    body: JSON.stringify(payload),
  })
}

export function loadArbitrageSettings(): Promise<ArbitrageSettings> {
  return request<ArbitrageSettings>('/api/v1/arbitrage/settings')
}

export function createTaxProfile(payload: {
  bookmaker_id: number; name: string; jurisdiction: string; currency: string; tax_basis: string
  stake_tax_rate: number; winnings_tax_rate: number; payout_withholding_rate: number
  commission_rate: number; fixed_fee: number; effective_from: string; verified_at: string
  source_url?: string; source_label: string
}, adminKey?: string): Promise<ArbitrageTaxProfile> {
  return request<ArbitrageTaxProfile>('/api/v1/arbitrage/settings/tax-profiles', { method: 'POST', headers: adminJson(adminKey), body: JSON.stringify(payload) })
}

export function createBookmakerConstraint(payload: {
  bookmaker_id: number; currency: string; minimum_stake: number; maximum_stake?: number
  stake_increment: number; observed_at: string; source_label: string
}, adminKey?: string): Promise<ArbitrageConstraint> {
  return request<ArbitrageConstraint>('/api/v1/arbitrage/settings/constraints', { method: 'POST', headers: adminJson(adminKey), body: JSON.stringify(payload) })
}

export function loadPredictions(eventId: number): Promise<ModelOutput[]> {
  return request<ModelOutput[]>(`/api/v1/events/${eventId}/predictions`)
}

function adminJson(adminKey?: string): HeadersInit {
  return { 'Content-Type': 'application/json', ...(adminKey ? { 'X-Admin-Key': adminKey } : {}) }
}

export function trainPoissonModel(payload: { competition_id: number; training_start: string; training_end: string; minimum_matches: number; minimum_team_matches: number; shrinkage_matches: number }, adminKey?: string): Promise<ModelVersion> {
  return request<ModelVersion>('/api/v1/models/train', { method: 'POST', headers: adminJson(adminKey), body: JSON.stringify(payload) })
}

export function evaluateModel(modelId: number, payload: { evaluation_start: string; evaluation_end: string; prediction_lead_minutes: number; minimum_training_matches: number; calibration_bins: number }, adminKey?: string): Promise<EvaluationRun> {
  return request<EvaluationRun>(`/api/v1/models/${modelId}/evaluate`, { method: 'POST', headers: adminJson(adminKey), body: JSON.stringify(payload) })
}

export function predictEvent(modelId: number, payload: { event_id: number; predicted_at?: string; inputs_as_of?: string }, adminKey?: string): Promise<ModelOutput> {
  return request<ModelOutput>(`/api/v1/models/${modelId}/predict`, { method: 'POST', headers: adminJson(adminKey), body: JSON.stringify(payload) })
}

export function generateSignals(payload: { output_id: number; generated_at?: string }, adminKey?: string): Promise<SignalBatch> {
  return request<SignalBatch>('/api/v1/signals/generate', { method: 'POST', headers: adminJson(adminKey), body: JSON.stringify(payload) })
}

export function loadBuilderQuotes(eventId: number): Promise<BetBuilderQuote[]> {
  return request<BetBuilderQuote[]>(`/api/v1/bet-builder/quotes?event_id=${eventId}`)
}

export function loadMatchday(date: string, timezone: string): Promise<Matchday> {
  const query = new URLSearchParams({ date, timezone })
  return request<Matchday>(`/api/v1/matchdays?${query.toString()}`)
}

export function loadMatchdayEvent(eventId: number): Promise<MatchdayEventDetail> {
  return request<MatchdayEventDetail>(`/api/v1/matchdays/events/${eventId}`)
}

export function createBuilderQuote(payload: CreateBetBuilderQuote): Promise<BetBuilderQuote> {
  return request<BetBuilderQuote>('/api/v1/bet-builder/quotes', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function simulateBankroll(payload: {
  backtest_run_id: number
  strategy: 'flat' | 'percentage' | 'fractional_kelly'
  initial_bankroll: number
}): Promise<BankrollSimulation> {
  return request<BankrollSimulation>('/api/v1/bankroll/simulate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function runSignalBacktest(payload: {
  model_version_id: number
  evaluation_start: string
  evaluation_end: string
  signal_types: string[]
}, adminKey?: string): Promise<SignalBacktest> {
  return request<SignalBacktest>('/api/v1/backtests/signals', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(adminKey ? { 'X-Admin-Key': adminKey } : {}) },
    body: JSON.stringify(payload),
  })
}

export { API_BASE_URL }
