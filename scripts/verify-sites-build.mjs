import worker from '../dist/server/index.js'

const requests = []
const env = {
  ASSETS: {
    async fetch(request) {
      const url = new URL(request.url)
      requests.push(url.pathname)
      if (url.pathname === '/') return new Response('<div id="root"></div>', { status: 200 })
      return new Response('Not found', { status: 404 })
    },
  },
}

const response = await worker.fetch(new Request('https://example.test/matches/7'), env)
if (response.status !== 200 || !requests.includes('/')) {
  throw new Error('Sites worker did not serve the SPA fallback for a match deep link')
}

const originalFetch = globalThis.fetch
let proxiedUrl = null
globalThis.fetch = async (request) => {
  proxiedUrl = request.url
  return Response.json({ total_events: 14 })
}

try {
  const apiResponse = await worker.fetch(
    new Request('https://example.test/api/v1/matchdays?date=2026-07-28'),
    { ...env, ODDSQUANT_API_BASE_URL: 'https://example.trycloudflare.com' },
  )
  if (apiResponse.status !== 200 || proxiedUrl !== 'https://example.trycloudflare.com/api/v1/matchdays?date=2026-07-28') {
    throw new Error('Sites worker did not proxy the API path to the configured tunnel')
  }

  const missingRoute = await worker.fetch(
    new Request('https://example.test/api/v1/status'),
    env,
  )
  if (missingRoute.status !== 503) {
    throw new Error('Sites worker did not fail closed without a configured tunnel')
  }
} finally {
  globalThis.fetch = originalFetch
}

console.log('Sites worker verified: SPA deep links and the fail-closed API tunnel proxy work')
