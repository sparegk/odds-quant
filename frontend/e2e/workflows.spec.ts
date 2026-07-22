import { expect, test, type Page, type Route } from '@playwright/test'

const now = '2026-07-01T12:00:00Z'
const event = {
  id: 7, provider_event_key: 'e2e-7', competition_id: 3, competition: 'Test League', country: 'GB', season: '2025/26',
  home_team: 'North FC', away_team: 'South FC', kickoff_at: '2026-08-01T18:00:00Z', status: 'scheduled', is_demo: false, latest_odds_at: now,
}
const model = {
  id: 12, name: 'Poisson', version: 'poisson-e2e', kind: 'poisson', training_start: '2025-01-01T00:00:00Z', training_end: now,
  data_fingerprint: 'model-fingerprint', feature_version: 'team-form-v1', sample_size: 120, evaluation_status: 'calibrated', config: {}, metrics: {}, status: 'trained', is_demo: false, created_at: now,
}
const evaluation = {
  id: 22, model_version_id: 12, model_version: 'poisson-e2e', evaluation_start: '2026-01-01T00:00:00Z', evaluation_end: now,
  status: 'completed', fingerprint: 'evaluation-fingerprint', config: {}, policy: {}, evaluation_status: 'calibrated',
  metrics: { evaluated_events: 40, candidate_events: 40, brier_score: 0.18, log_loss: 0.75, expected_calibration_error: 0.04 },
  benchmarks: { dixon_coles: { observations: 40, brier_score: 0.19, log_loss: 0.78, expected_calibration_error: 0.04 }, elo: { observations: 40, brier_score: 0.2, log_loss: 0.8, expected_calibration_error: 0.05 }, uniform: { brier_score: 0.22, log_loss: 1.0986 }, market_consensus: { brier_score: 0.2, log_loss: 0.79 } }, calibration: [], is_demo: false, created_at: now,
}
const output = {
  id: 32, event_id: 7, model_version_id: 12, model_version: 'poisson-e2e', predicted_at: now, inputs_as_of: now, evidence_class: 'external',
  home_lambda: 1.4, away_lambda: 0.9, sample_size: 120, score_matrix: [], derived_probabilities: {}, predictions: [],
}
const backtest = {
  id: 42, model_version_id: 12, model_version: 'poisson-e2e', status: 'completed', evaluation_start: '2026-01-01T00:00:00Z', evaluation_end: now,
  fingerprint: 'backtest-fingerprint', evaluation_status: 'research_only', is_demo: false, config: {}, policy: {}, metrics: { bet_count: 1, net_profit_units: 0.8, roi: 0.08, maximum_drawdown_units: 0 },
  observations: [{ id: 1, event_id: 7, selection_id: 1, prediction_id: 32, odds_snapshot_id: 5, predicted_at: now, settled_at: now, market_type: 'moneyline_3way', selection_code: 'HOME', decimal_odds: 1.8, model_probability: 0.6, lower_probability: 0.55, expected_value: 0.08, settlement: 'won', stake: 10, profit_units: 8 }], created_at: now,
}

async function json(route: Route, body: unknown, status = 200) {
  await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
}

async function mockApi(page: Page) {
  await page.route('http://127.0.0.1:8000/api/v1/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    if (request.method() === 'POST') {
      if (path === '/api/v1/imports/odds') return json(route, { job_id: 51, status: 'completed', rows_received: 3, rows_imported: 3, snapshots_created: 1 }, 201)
      if (path === '/api/v1/models/train') return json(route, model, 201)
      if (path === '/api/v1/models/12/evaluate') return json(route, evaluation, 201)
      if (path === '/api/v1/models/12/predict') return json(route, output, 201)
      if (path === '/api/v1/signals/generate') return json(route, { event_id: 7, output_id: 32, model_version_id: 12, evaluation_run_id: 22, generated_at: now, signals: [] }, 201)
      if (path === '/api/v1/arbitrage/settings/tax-profiles') return json(route, { id: 61, bookmaker_id: 2, bookmaker: 'Beacon', name: 'GB bookmaker terms', jurisdiction: 'GB', currency: 'EUR', stake_tax_rate: '0', winnings_tax_rate: '0', payout_withholding_rate: '0', commission_rate: '0', fixed_fee: '0', effective_from: now, effective_to: null, verified_at: now, source_url: null, source_label: 'Published terms', status: 'verified' }, 201)
      if (path === '/api/v1/arbitrage/settings/constraints') return json(route, { id: 62, bookmaker_id: 2, bookmaker: 'Beacon', currency: 'EUR', minimum_stake: '1', maximum_stake: '500', stake_increment: '0.01', observed_at: now, source_label: 'Account observation' }, 201)
      if (path === '/api/v1/arbitrage/calculate') return json(route, { event_id: 7, calculated_at: now, opportunities: [] }, 201)
      if (path === '/api/v1/backtests/signals') return json(route, backtest, 201)
      if (path === '/api/v1/bankroll/simulate') return json(route, { backtest_run_id: 42, backtest_fingerprint: 'backtest-fingerprint', simulation_fingerprint: 'simulation-fingerprint', strategy: 'flat', initial_bankroll: 1000, final_bankroll: 1008, total_staked: 10, net_profit: 8, roi: 0.8, maximum_drawdown: 0, maximum_drawdown_fraction: 0, bets_placed: 1, bets_skipped: 0, is_demo: false, warnings: ['Research result only.'], points: [] }, 201)
    }
    if (path === '/api/v1/status') return json(route, { phase: 'research', sports: ['football'], data_mode: 'external', automated_betting: false })
    if (path === '/api/v1/events') return json(route, [event])
    if (path === '/api/v1/providers') return json(route, [{ id: 1, slug: 'feed', name: 'Test feed', kind: 'external', is_demo: false, terms_url: null, capabilities: {}, event_count: 1, snapshot_count: 1 }])
    if (path === '/api/v1/models') return json(route, [model])
    if (path === '/api/v1/evaluations') return json(route, [evaluation])
    if (path === '/api/v1/backtests') return json(route, [backtest])
    if (path === '/api/v1/readiness') return json(route, { events: 1, odds_snapshots: 1, final_results: 20, model_versions: 1, predictions: 1, non_demo_calibrated_evaluations: 1, signals: 1, signal_backtests: 1, bookmaker_tax_mappings: 1, bookmaker_constraints: 1, intelligence_records: 0 })
    if (path === '/api/v1/arbitrage/settings') return json(route, { bookmakers: [{ id: 2, slug: 'beacon', name: 'Beacon', is_demo: false }], tax_profiles: [], constraints: [] })
    if (path === '/api/v1/odds/comparison') return json(route, [])
    return json(route, [])
  })
}

test.beforeEach(async ({ page }) => {
  await mockApi(page)
  await page.goto('/')
  await expect(page.getByText('OddsQuant')).toBeVisible()
})

test('imports odds and completes the model-to-signal workflow', async ({ page }) => {
  await page.getByRole('button', { name: 'Data operations' }).click()
  await page.getByLabel('Odds snapshots CSV file').setInputFiles({ name: 'odds.csv', mimeType: 'text/csv', buffer: Buffer.from('event,price\n7,1.8') })
  await page.getByRole('button', { name: 'Import odds' }).click()
  await expect(page.getByText('Job #51 completed')).toBeVisible()

  await page.evaluate(() => { window.location.hash = 'models' })
  await expect(page.locator('header h1')).toHaveText('Model performance')
  await expect(page.getByText('Chronological Elo')).toBeVisible()
  await expect(page.getByRole('cell', { name: 'Dixon–Coles' })).toBeVisible()
  await page.getByLabel('Training start').fill('2025-01-01T00:00')
  await page.getByLabel('Training end').fill('2026-07-01T12:00')
  await page.getByRole('button', { name: 'Train model' }).click()
  await expect(page.getByText('train completed - #12')).toBeVisible()

  await page.getByRole('button', { name: '2. Evaluate' }).click()
  await page.getByLabel('Evaluation start').fill('2026-01-01T00:00')
  await page.getByLabel('Evaluation end').fill('2026-07-01T12:00')
  await page.getByRole('button', { name: 'Run evaluation' }).click()
  await expect(page.getByText('evaluate completed - #22')).toBeVisible()

  await page.getByRole('button', { name: '3. Predict' }).click()
  await page.getByRole('button', { name: 'Persist prediction' }).click()
  await expect(page.getByText('predict completed - #32')).toBeVisible()
  await page.getByRole('button', { name: '4. Signals' }).click()
  await page.getByRole('button', { name: 'Generate signals' }).click()
  await expect(page.getByText('signals completed - #32')).toBeVisible()
})

test('stores sourced arbitrage evidence before calculating', async ({ page }) => {
  await page.getByRole('button', { name: 'Arbitrage' }).click()
  await page.getByLabel('Verified/effective at').fill('2026-07-01T12:00')
  await page.getByLabel('Source label').fill('Published terms')
  await page.getByLabel('Jurisdiction').fill('GB')
  await page.getByRole('button', { name: 'Store sourced evidence' }).click()
  await expect(page.getByText('Tax profile stored with provenance.')).toBeVisible()

  await page.getByRole('button', { name: 'Stake constraints' }).click()
  await page.getByLabel('Observed at').fill('2026-07-01T12:00')
  await page.getByLabel('Source label').fill('Account observation')
  await page.getByLabel('Maximum stake').fill('500')
  await page.getByRole('button', { name: 'Store sourced evidence' }).click()
  await expect(page.getByText('Stake constraint stored with provenance.')).toBeVisible()
  await page.getByRole('button', { name: 'Calculate stored markets' }).click()
  await expect(page.getByText('Changes saved and dashboard resources synchronized.')).toBeVisible()
})

test('runs a settled signal replay and bankroll simulation', async ({ page }) => {
  await page.evaluate(() => { window.location.hash = 'backtests' })
  await expect(page.locator('header h1')).toHaveText('Backtesting')
  await page.getByLabel('Evaluation start').fill('2026-01-01T00:00')
  await page.getByLabel('Evaluation end').fill('2026-07-01T12:00')
  await page.getByRole('button', { name: 'Run signal backtest' }).click()
  await expect(page.getByText('#42 / poisson-e2e')).toBeVisible()

  await page.evaluate(() => { window.location.hash = 'bankroll' })
  await expect(page.locator('header h1')).toHaveText('Bankroll research')
  await page.getByRole('button', { name: 'Simulate stored sequence' }).click()
  await expect(page.getByText('flat replay')).toBeVisible()
  await expect(page.getByText('1008.00')).toBeVisible()
})
