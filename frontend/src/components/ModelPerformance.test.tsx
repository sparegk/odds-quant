import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import type { DashboardData } from '../types'
import { ModelPerformance } from './ModelPerformance'

afterEach(cleanup)

const base: DashboardData = { status: { phase: 'model_baseline', sports: ['football'], data_mode: 'user_supplied', automated_betting: false }, events: [], providers: [], imports: [], jobs: [], models: [], evaluations: [], signals: [], underdogs: [], arbitrage: [], backtests: [], resource_errors: {} }

describe('ModelPerformance', () => {
  it('keeps training provenance separate from absent evaluation evidence', () => {
    render(<ModelPerformance dashboard={{ ...base, models: [{ id: 3, name: 'Poisson baseline', version: 'poisson-v1', kind: 'poisson', training_start: '2026-01-01T00:00:00Z', training_end: '2026-06-01T00:00:00Z', data_fingerprint: 'abcdef1234567890', feature_version: 'team-strength-v1', sample_size: 80, evaluation_status: 'unvalidated', config: {}, metrics: {}, status: 'trained', is_demo: false, created_at: '2026-06-01T01:00:00Z' }] }} />)
    expect(screen.getAllByText('poisson-v1')).toHaveLength(2)
    expect(screen.getByText('80')).toBeInTheDocument()
    expect(screen.getByText('Performance is not established')).toBeInTheDocument()
    expect(screen.getByText(/Data fingerprint: abcdef1234567890/)).toBeInTheDocument()
  })

  it('fails closed when no model has been trained', () => {
    render(<ModelPerformance dashboard={base} />)
    expect(screen.getByText('No trained model versions')).toBeInTheDocument()
  })
})
