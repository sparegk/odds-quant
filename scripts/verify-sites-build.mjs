import worker from '../dist/server/index.js'

const requests = []
const env = {
  ASSETS: {
    async fetch(request) {
      const url = new URL(request.url)
      requests.push(url.pathname)
      if (url.pathname === '/index.html') return new Response('<div id="root"></div>', { status: 200 })
      return new Response('Not found', { status: 404 })
    },
  },
}

const response = await worker.fetch(new Request('https://example.test/matches/7'), env)
if (response.status !== 200 || !requests.includes('/index.html')) {
  throw new Error('Sites worker did not serve the SPA fallback for a match deep link')
}

console.log('Sites worker verified: /matches/7 falls back to /index.html')
