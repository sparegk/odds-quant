import { expect, test, type Page, type Route } from '@playwright/test'

const now = '2026-08-04T00:00:00Z'
const events = Array.from({ length: 120 }, (_, index) => ({
  id: index + 1,
  provider_event_key: `scale-${index + 1}`,
  competition_id: 1,
  competition: 'Scale League',
  country: 'GB',
  season: '2026/27',
  home_team: `Home ${String(index + 1).padStart(3, '0')}`,
  away_team: `Away ${String(index + 1).padStart(3, '0')}`,
  kickoff_at: `2026-08-04T${String(10 + (index % 10)).padStart(2, '0')}:00:00Z`,
  status: 'scheduled',
  is_demo: false,
  latest_odds_at: now,
}))
const matchday = {
  date: '2026-08-04', timezone: 'Europe/Athens', local_start: '2026-08-03T21:00:00Z', local_end: '2026-08-04T21:00:00Z', as_of: now,
  total_events: events.length, data_note: 'Synthetic production-shaped acceptance fixture; not research evidence.',
  competitions: [{ competition_id: 1, name: 'Scale League', country: 'GB', season: '2026/27', group_key: 'other', group_label: 'Other tracked', priority: 99, is_featured: false, events: events.map((event) => ({ event, market_count: 1, bookmaker_count: 834, latest_prediction_at: null, qualified_signal_count: 0 })) }],
}
const comparisons = [{
  market_id: 1, market_type: 'MATCH_RESULT', line: null, period: 'full_time', currency: 'EUR', settlement_rule_key: 'standard',
  snapshots: Array.from({ length: 834 }, (_, index) => ({
    snapshot_id: index + 1, bookmaker_id: index + 1, bookmaker: `Book ${String(index + 1).padStart(4, '0')}`, provider: 'licensed-scale-feed',
    observed_at: now, source_updated_at: now, is_closing: false, is_demo: false, source_label: 'synthetic acceptance fixture',
    freshness_seconds: index % 2 ? 60 : 900, is_stale: index % 2 === 0, overround: 1.05, bookmaker_margin: 0.05,
    prices: ['HOME', 'DRAW', 'AWAY'].map((selection, selectionIndex) => ({ selection_code: selection, selection_name: selection, decimal_odds: 1.8 + selectionIndex + index / 10000, raw_implied_probability: 0.4, proportional_fair_probability: 0.38, proportional_fair_odds: 2.63, power_fair_probability: 0.38, power_fair_odds: 2.63 })),
  })),
  best_prices: [],
}]
const readiness = { events: 120, odds_snapshots: 2502, final_results: 0, model_versions: 0, predictions: 0, non_demo_calibrated_evaluations: 0, signals: 0, signal_backtests: 0, bookmaker_tax_mappings: 0, bookmaker_constraints: 0, intelligence_records: 0 }

async function json(route: Route, body: unknown, status = 200) {
  await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
}

async function scaleApi(page: Page) {
  await page.route('http://127.0.0.1:8000/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    if (path === '/api/v1/status') return json(route, { phase: 'research', sports: ['football'], data_mode: 'external', automated_betting: false })
    if (path === '/api/v1/events') return json(route, events)
    if (path === '/api/v1/matchdays') return json(route, matchday)
    if (path === '/api/v1/odds/comparison') return json(route, comparisons)
    if (path === '/api/v1/providers') return json(route, [{ id: 9, slug: 'stale-feed', name: 'Stale feed', kind: 'external', is_demo: false, terms_url: null, capabilities: {}, event_count: 120, snapshot_count: 2502 }])
    if (path === '/api/v1/imports') return json(route, [{ id: 77, provider_id: 9, filename: 'rejected-feed.csv', file_sha256: 'fixture', status: 'rejected', rows_received: 5000, rows_imported: 0, errors: [{ row: 14, message: 'incomplete market' }], created_at: now }])
    if (path === '/api/v1/data/monitoring') return json(route, { observed_at: now, expected_poll_seconds: 300, healthy: false, providers: [{ provider_id: 9, provider: 'Stale feed', provider_slug: 'stale-feed', healthy: false, latest_success_at: '2026-08-03T20:00:00Z', latest_job_id: 88, latest_job_status: 'failed', consecutive_completed_jobs: 0, failures_in_recent_window: 3, blockers: ['stale_provider_success'] }], alerts: [{ code: 'stale_provider_success', severity: 'critical', detail: 'No successful collection inside the required cadence.', provider_slug: 'stale-feed', competition: null, bookmaker: null }], latest_prediction_refresh: null })
    if (path === '/api/v1/readiness') return json(route, readiness)
    if (path === '/api/v1/data/coverage') return json(route, { minimum_evaluation_results: 200, required_bookmakers: [], total_events: 120, permitted_events: 120, permitted_final_results: 0, permitted_odds_snapshots: 2502, permitted_closing_snapshots: 0, competitions: [] })
    if (path.startsWith('/api/v1/matchdays/events/')) return json(route, { event: events[0], competition_group: 'other', competition_group_label: 'Other tracked', as_of: now, team_form: [], markets: [], latest_prediction: null, model_market_comparisons: [], signals: [], builder_quotes: [], suggestions: [], selected_bookmakers: ['allwyn', 'novibet'], bookmaker_options: [], suggestion_market_statuses: [], availability_audit: [], stored_lineups: [], lineup_projections: [], lineup_research: { status: 'blocked', title: 'Lineups blocked', available_records: 0, reasons: ['No timestamped lineup evidence.'] }, player_research: { status: 'blocked', title: 'Players blocked', available_records: 0, reasons: ['No validated player evidence.'] }, builder_value: { status: 'blocked', title: 'Builder blocked', available_records: 0, reasons: ['No prediction.'] }, bookmaker_guidance: 'Acceptance fixture only.', evidence_note: 'Not research evidence.' })
    return json(route, [])
  })
}

test.beforeEach(async ({ page }) => {
  await scaleApi(page)
})

test('handles a 120-match desktop matchday and 2,502 price rows', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('120 matches / Europe/Athens')).toBeVisible()
  await page.goto('/odds')
  await expect(page.getByLabel('MATCH_RESULT price evidence controls')).toBeVisible()
  await expect(page.getByText('2502 matching rows · page 1 of 251')).toBeVisible()
  await page.getByLabel('MATCH_RESULT price evidence search').fill('Book 0834')
  await expect(page.getByText('3 matching rows · page 1 of 1')).toBeVisible()
})

test('surfaces rejected feeds, stale providers, missing predictions, and partial API failure', async ({ page }) => {
  await page.route('http://127.0.0.1:8000/api/v1/models', (route) => json(route, { detail: 'model registry unavailable' }, 503))
  await page.goto('/admin/status')
  await expect(page.getByText(/operational items require attention/)).toBeVisible()
  await expect(page.getByText('Rejected imports')).toBeVisible()
  await expect(page.getByText('rejected-feed.csv')).toBeVisible()
  await expect(page.getByText('Stale Provider Success').first()).toBeVisible()
  await expect(page.getByText('Some dashboard resources are unavailable')).toBeVisible()
  await page.goto('/matches/1')
  await expect(page.getByText('Builder blocked')).toBeVisible()
  await expect(page.getByText('No prediction.')).toBeVisible()
})
