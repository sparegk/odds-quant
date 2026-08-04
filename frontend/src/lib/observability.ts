const configuredApiBaseUrl = import.meta.env.VITE_API_BASE_URL as string | undefined
const apiBaseUrl = configuredApiBaseUrl
  ? configuredApiBaseUrl.endsWith('/') ? configuredApiBaseUrl.slice(0, -1) : configuredApiBaseUrl
  : import.meta.env.DEV ? 'http://127.0.0.1:8000' : ''

interface ClientEvent {
  event: 'frontend_error' | 'api_failure'
  route: string
  error_type: string
  status?: number
  duration_ms?: number
}

export function reportApiFailure(path: string, errorType: string, status: number | undefined, durationMs: number) {
  send({ event: 'api_failure', route: safeRoute(path), error_type: safeType(errorType), status, duration_ms: rounded(durationMs) })
}

export function reportFrontendError(error: unknown) {
  const errorType = error instanceof Error ? error.name : 'UnknownError'
  send({ event: 'frontend_error', route: safeRoute(window.location.pathname), error_type: safeType(errorType) })
}

export function installGlobalErrorReporting() {
  window.addEventListener('error', (event) => reportFrontendError(event.error))
  window.addEventListener('unhandledrejection', (event) => reportFrontendError(event.reason))
}

export function safeRoute(input: string): string {
  const pathname = input.split('?')[0] || '/'
  return pathname.replace(/\/[0-9]+(?=\/|$)/g, '/:id').slice(0, 160)
}

function safeType(value: string): string {
  const normalized = value.replace(/[^A-Za-z0-9_.-]/g, '').slice(0, 80)
  return normalized || 'UnknownError'
}

function rounded(value: number): number {
  return Math.min(300000, Math.max(0, Math.round(value * 10) / 10))
}

function send(event: ClientEvent) {
  const body = JSON.stringify(event)
  const url = `${apiBaseUrl}/api/v1/client-events`
  if (navigator.sendBeacon?.(url, new Blob([body], { type: 'application/json' }))) return
  void fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body, keepalive: true }).catch(() => undefined)
}
