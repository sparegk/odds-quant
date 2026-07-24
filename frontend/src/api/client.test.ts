import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  createBuilderQuote,
  calculateArbitrage,
  loadComparison,
  loadDashboard,
  loadMatchday,
  loadMatchdayEvent,
  loadPredictions,
  runSignalBacktest,
  uploadCsv,
  importIntelligenceBundle,
} from './client'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('API client', () => {
  it('loads all operational dashboard resources', async () => {
    const fetchMock = vi.fn((input: string | URL | Request) => {
      const url = input instanceof Request ? input.url : input.toString()
      let payload: unknown = []
      if (url.endsWith('/api/v1/status')) {
        payload = {
          phase: 'model_baseline',
          sports: ['football'],
          data_mode: 'demo_or_user_supplied',
          automated_betting: false,
        }
      }
      return Promise.resolve(new Response(JSON.stringify(payload), { status: 200 }))
    })
    vi.stubGlobal('fetch', fetchMock)

    const data = await loadDashboard()

    expect(data.status.automated_betting).toBe(false)
    expect(data.resource_errors).toEqual({})
    expect(fetchMock).toHaveBeenCalledTimes(13)
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/data/monitoring'),
      expect.any(Object),
    )
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/arbitrage/opportunities'),
      expect.any(Object),
    )
  })

  it('keeps successful resources available when one dashboard endpoint fails', async () => {
    const fetchMock = vi.fn((input: string | URL | Request) => {
      const url = input instanceof Request ? input.url : input.toString()
      if (url.endsWith('/api/v1/status')) {
        return Promise.resolve(new Response(JSON.stringify({
          phase: 'model_baseline',
          sports: ['football'],
          data_mode: 'user_supplied',
          automated_betting: false,
        }), { status: 200 }))
      }
      if (url.endsWith('/api/v1/data/monitoring')) {
        return Promise.resolve(new Response('{}', { status: 503 }))
      }
      return Promise.resolve(new Response('[]', { status: 200 }))
    })
    vi.stubGlobal('fetch', fetchMock)

    const data = await loadDashboard()

    expect(data.status.phase).toBe('model_baseline')
    expect(data.monitoring).toBeNull()
    expect(data.signals).toEqual([])
    expect(data.resource_errors).toEqual({ monitoring: 'API request failed: 503' })
  })

  it('requests comparison data for the selected event', async () => {
    const fetchMock = vi.fn(() => Promise.resolve(new Response('[]', { status: 200 })))
    vi.stubGlobal('fetch', fetchMock)

    await loadComparison(42)

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/odds/comparison?event_id=42'),
      expect.any(Object),
    )
  })

  it('raises a typed error for failed API responses', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response('{}', { status: 503 }))))
    await expect(loadComparison(1)).rejects.toMatchObject({ status: 503 })
  })

  it('requests a timezone-aware matchday and its selected match research', async () => {
    const fetchMock = vi.fn(() => Promise.resolve(new Response('{}', { status: 200 })))
    vi.stubGlobal('fetch', fetchMock)

    await loadMatchday('2026-07-21', 'Europe/Athens')
    await loadMatchdayEvent(42)

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      expect.stringContaining('/api/v1/matchdays?date=2026-07-21&timezone=Europe%2FAthens'),
      expect.any(Object),
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      expect.stringContaining(
        '/api/v1/matchdays/events/42?bookmakers=allwyn&bookmakers=novibet',
      ),
      expect.any(Object),
    )
  })

  it('loads prediction evidence and submits timestamped builder inputs', async () => {
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
      void input
      void init
      return Promise.resolve(new Response('[]', { status: 200 }))
    })
    vi.stubGlobal('fetch', fetchMock)

    await loadPredictions(42)
    await createBuilderQuote({
      event_id: 42,
      prediction_output_id: 9,
      legs: [
        { market_type: 'MATCH_RESULT', selection: 'HOME', line: null },
        { market_type: 'TOTAL_GOALS', selection: 'OVER', line: 2.5 },
      ],
      quoted_at: '2026-07-19T12:00:00Z',
    })

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      expect.stringContaining('/api/v1/events/42/predictions'),
      expect.any(Object),
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      expect.stringContaining('/api/v1/bet-builder/quotes'),
      expect.objectContaining({ method: 'POST' }),
    )
    const requestBody = fetchMock.mock.calls[1]?.[1]?.body
    expect(typeof requestBody).toBe('string')
    if (typeof requestBody === 'string') expect(requestBody).toContain('prediction_output_id')
  })

  it('submits protected arbitrage controls without persisting the admin key', async () => {
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
      void input
      void init
      return Promise.resolve(new Response(JSON.stringify({ event_id: 42, calculated_at: '2026-07-19T12:00:00Z', opportunities: [] }), { status: 201 }))
    })
    vi.stubGlobal('fetch', fetchMock)
    await calculateArbitrage({ event_id: 42, budget: 100, currency: 'EUR', odds_stale_after_seconds: 300, tax_max_age_days: 365, constraint_max_age_minutes: 1440 }, 'secret')
    const request = fetchMock.mock.calls[0]
    const requestUrl = request?.[0]
    expect(typeof requestUrl === 'string' ? requestUrl : requestUrl instanceof Request ? requestUrl.url : requestUrl?.href).toContain('/api/v1/arbitrage/calculate')
    expect(request?.[1]?.method).toBe('POST')
    expect(request?.[1]?.headers).toMatchObject({ 'X-Admin-Key': 'secret' })
  })

  it('submits an exact chronological signal replay', async () => {
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => { void input; void init; return Promise.resolve(new Response('{}', { status: 201 })) })
    vi.stubGlobal('fetch', fetchMock)
    await runSignalBacktest({ model_version_id: 3, evaluation_start: '2026-01-01T00:00:00Z', evaluation_end: '2026-06-01T00:00:00Z', signal_types: ['VALUE'] }, 'secret')
    const init = fetchMock.mock.calls[0]?.[1]
    expect(init?.method).toBe('POST')
    expect(init?.body).toContain('evaluation_start')
    expect(init?.headers).toMatchObject({ 'X-Admin-Key': 'secret' })
  })

  it('uploads CSV data as multipart with an in-memory admin key', async () => {
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => { void input; void init; return Promise.resolve(new Response(JSON.stringify({ job_id: 8, status: 'completed', rows_received: 1, rows_imported: 1 }), { status: 201 })) })
    vi.stubGlobal('fetch', fetchMock)
    await uploadCsv('odds', new File(['header\nvalue'], 'odds.csv', { type: 'text/csv' }), { adminKey: 'secret' })
    const init = fetchMock.mock.calls[0]?.[1]
    expect(init?.method).toBe('POST')
    expect(init?.body).toBeInstanceOf(FormData)
    expect(init?.headers).toMatchObject({ 'X-Admin-Key': 'secret' })
  })

  it('submits the complete intelligence bundle as protected JSON', async () => {
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => { void input; void init; return Promise.resolve(new Response(JSON.stringify({ job_id: 10, status: 'completed', rows_received: 1, rows_imported: 1, created: { players: 1 }, content_sha256: 'abc' }), { status: 201 })) })
    vi.stubGlobal('fetch', fetchMock)
    await importIntelligenceBundle({ source_key: 'source', players: [{ provider_player_key: 'p1' }] }, 'secret')
    const init = fetchMock.mock.calls[0]?.[1]
    expect(init?.method).toBe('POST')
    expect(init?.body).toContain('source_key')
    expect(init?.headers).toMatchObject({ 'X-Admin-Key': 'secret' })
  })
})
