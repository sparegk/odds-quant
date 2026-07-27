import { copyFile, mkdir, writeFile } from 'node:fs/promises'

await mkdir('dist/server', { recursive: true })
await mkdir('dist/.openai', { recursive: true })
await copyFile('.openai/hosting.json', 'dist/.openai/hosting.json')

const worker = `export default {
  async fetch(request, env) {
    const requestUrl = new URL(request.url)
    if (requestUrl.pathname.startsWith('/api/')) {
      let upstream
      try {
        upstream = new URL(env.ODDSQUANT_API_BASE_URL)
      } catch {
        return Response.json({ detail: 'Production API route is not configured' }, { status: 503 })
      }

      if (upstream.protocol !== 'https:' || !upstream.hostname.endsWith('.trycloudflare.com')) {
        return Response.json({ detail: 'Production API route is invalid' }, { status: 503 })
      }

      const upstreamUrl = new URL(requestUrl.pathname + requestUrl.search, upstream)
      return fetch(new Request(upstreamUrl, request))
    }

    const response = await env.ASSETS.fetch(request)
    if (response.status !== 404 || request.method !== 'GET') return response

    const fallbackUrl = new URL(request.url)
    fallbackUrl.pathname = '/'
    return env.ASSETS.fetch(new Request(fallbackUrl, request))
  },
}
`

await writeFile('dist/server/index.js', worker, 'utf8')
