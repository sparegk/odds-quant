import { afterEach, describe, expect, it, vi } from 'vitest'

import { loadComparison, loadDashboard } from './client'

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
    expect(fetchMock).toHaveBeenCalledTimes(7)
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
})
