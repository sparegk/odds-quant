import type {
  DashboardData,
  EventSummary,
  ImportJob,
  MarketComparison,
  ProjectStatus,
  ProviderJob,
  ProviderSummary,
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

async function request<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { Accept: 'application/json' },
  })
  if (!response.ok) {
    throw new ApiError(`API request failed: ${response.status}`, response.status)
  }
  return (await response.json()) as T
}

export async function loadDashboard(): Promise<DashboardData> {
  const [status, events, providers, imports, jobs] = await Promise.all([
    request<ProjectStatus>('/api/v1/status'),
    request<EventSummary[]>('/api/v1/events?include_past=true'),
    request<ProviderSummary[]>('/api/v1/providers'),
    request<ImportJob[]>('/api/v1/imports'),
    request<ProviderJob[]>('/api/v1/jobs'),
  ])
  return { status, events, providers, imports, jobs }
}

export function loadComparison(eventId: number): Promise<MarketComparison[]> {
  return request<MarketComparison[]>(`/api/v1/odds/comparison?event_id=${eventId}`)
}

export { API_BASE_URL }
