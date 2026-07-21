import { afterEach, describe, expect, it, vi } from 'vitest'

import { createBuilderQuote, loadComparison, loadDashboard, loadPredictions } from './client'

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
    expect(fetchMock).toHaveBeenCalledTimes(11)
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
      if (url.endsWith('/api/v1/signals')) {
        return Promise.resolve(new Response('{}', { status: 503 }))
      }
      return Promise.resolve(new Response('[]', { status: 200 }))
    })
    vi.stubGlobal('fetch', fetchMock)

    const data = await loadDashboard()

    expect(data.status.phase).toBe('model_baseline')
    expect(data.signals).toEqual([])
    expect(data.resource_errors).toEqual({ signals: 'API request failed: 503' })
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
})
