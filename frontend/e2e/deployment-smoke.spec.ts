import { expect, test } from '@playwright/test'

const webUrl = process.env.DEPLOYMENT_WEB_URL?.replace(/\/$/, '')
const apiUrl = process.env.DEPLOYMENT_API_URL?.replace(/\/$/, '')

test('deployed desktop shell and API pass post-deploy smoke checks', async ({ page, request }) => {
  test.skip(!webUrl || !apiUrl, 'DEPLOYMENT_WEB_URL and DEPLOYMENT_API_URL are required')

  const health = await request.get(`${apiUrl}/health`)
  expect(health.ok()).toBeTruthy()
  const healthBody: unknown = await health.json()
  expect(healthBody).toMatchObject({ status: 'ok' })
  expect(health.headers()['x-request-id']).toBeTruthy()
  expect(health.headers()['server-timing']).toMatch(/^app;dur=/)

  const status = await request.get(`${apiUrl}/api/v1/status`)
  expect(status.ok()).toBeTruthy()
  const statusBody: unknown = await status.json()
  expect(statusBody).toMatchObject({ automated_betting: false })

  const shell = await request.get(webUrl!)
  expect(shell.ok()).toBeTruthy()
  expect(shell.headers()['x-content-type-options']).toBe('nosniff')
  expect(shell.headers()['x-frame-options']).toBe('DENY')

  await page.setViewportSize({ width: 1440, height: 900 })
  for (const path of ['/', '/analytics', '/research/workspace', '/admin/status']) {
    await page.goto(`${webUrl}${path}`, { waitUntil: 'networkidle' })
    await expect(page.getByText('OddsQuant', { exact: true })).toBeVisible()
    await expect(page.getByText('The research workspace could not render')).toBeHidden()
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeGreaterThanOrEqual(1180)
    expect(await page.locator('meta[name="viewport"]').getAttribute('content')).toBe('width=1180')
  }
})
