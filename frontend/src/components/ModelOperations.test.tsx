import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { DashboardData } from '../types'
import { ModelOperations } from './ModelOperations'

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

const dashboard: DashboardData = {
  status: { phase: 'model_baseline', sports: ['football'], data_mode: 'user_supplied', automated_betting: false },
  events: [{ id: 7, provider_event_key: 'event-7', competition_id: 2, competition: 'Research League', country: 'GB', season: '2026', home_team: 'Northbridge', away_team: 'Harbour', kickoff_at: '2026-08-01T18:00:00Z', status: 'scheduled', is_demo: false, latest_odds_at: '2026-07-31T12:00:00Z' }],
  providers: [], imports: [], jobs: [], evaluations: [], signals: [], underdogs: [], arbitrage: [], backtests: [], resource_errors: {},
  models: [{ id: 3, name: 'Poisson', version: 'poisson-v1', kind: 'poisson', training_start: '2026-01-01T00:00:00Z', training_end: '2026-06-01T00:00:00Z', data_fingerprint: 'abc', feature_version: 'v1', sample_size: 80, evaluation_status: 'unvalidated', config: {}, metrics: {}, status: 'trained', is_demo: false, created_at: '2026-06-01T01:00:00Z' }],
}

describe('ModelOperations', () => {
  it('exposes the four explicit stages and carries stored identifiers into their controls', () => {
    render(<ModelOperations dashboard={dashboard} />)
    expect(screen.getByLabelText('Competition')).toHaveValue('2')
    fireEvent.click(screen.getByText('2. Evaluate'))
    expect(screen.getByLabelText('Model version')).toHaveValue('3')
    fireEvent.click(screen.getByText('3. Predict'))
    expect(screen.getByLabelText('Target event')).toHaveValue('7')
    fireEvent.click(screen.getByText('4. Signals'))
    expect(screen.getByLabelText('Prediction output ID')).toBeInTheDocument()
  })

  it('refreshes shared dashboard resources after a successful write', async () => {
    const changed = vi.fn(() => Promise.resolve())
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response(JSON.stringify(dashboard.models[0]), { status: 201 }))))
    render(<ModelOperations dashboard={dashboard} onChanged={changed} />)
    fireEvent.change(screen.getByLabelText('Training start'), { target: { value: '2026-01-01T00:00' } })
    fireEvent.change(screen.getByLabelText('Training end'), { target: { value: '2026-06-01T00:00' } })
    fireEvent.click(screen.getByText('Train model'))
    expect(await screen.findByText(/train completed/)).toBeInTheDocument()
    expect(changed).toHaveBeenCalledTimes(1)
  })
})
