import { copyFile, mkdir, writeFile } from 'node:fs/promises'

await mkdir('dist/server', { recursive: true })
await mkdir('dist/.openai', { recursive: true })
await copyFile('.openai/hosting.json', 'dist/.openai/hosting.json')

const worker = `export default {
  async fetch(request, env) {
    const response = await env.ASSETS.fetch(request)
    if (response.status !== 404 || request.method !== 'GET') return response

    const fallbackUrl = new URL(request.url)
    fallbackUrl.pathname = '/index.html'
    return env.ASSETS.fetch(new Request(fallbackUrl, request))
  },
}
`

await writeFile('dist/server/index.js', worker, 'utf8')
