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

  it('compares Poisson with chronological Elo and other independent baselines', () => {
    const model = { id: 3, name: 'Poisson baseline', version: 'poisson-v1', kind: 'poisson', training_start: '2026-01-01T00:00:00Z', training_end: '2026-06-01T00:00:00Z', data_fingerprint: 'abcdef1234567890', feature_version: 'team-strength-v1', sample_size: 80, evaluation_status: 'calibrated', config: {}, metrics: {}, status: 'trained', is_demo: false, created_at: '2026-06-01T01:00:00Z' }
    render(<ModelPerformance dashboard={{ ...base, models: [model], evaluations: [{ id: 8, model_version_id: 3, model_version: 'poisson-v1', status: 'completed', evaluation_start: '2026-03-01T00:00:00Z', evaluation_end: '2026-06-01T00:00:00Z', fingerprint: 'evaluation-fingerprint', config: {}, policy: {}, evaluation_status: 'calibrated', is_demo: false, metrics: { brier_score: 0.5, log_loss: 0.8, expected_calibration_error: 0.04, evaluated_events: 40, candidate_events: 40, observations: 40 }, benchmarks: { elo: { brier_score: 0.55, log_loss: 0.85, expected_calibration_error: 0.06, observations: 40 }, uniform: { brier_score: 0.6667, log_loss: 1.0986, expected_calibration_error: 0.1, observations: 40 } }, calibration: [], created_at: '2026-06-01T02:00:00Z' }] }} />)

    expect(screen.getByText('Chronological Elo')).toBeInTheDocument()
    expect(screen.getByText('Market consensus')).toBeInTheDocument()
    expect(screen.getAllByText('BEAT')).toHaveLength(2)
    expect(screen.getByText(/Elo is replayed only from results known before each forecast cutoff/)).toBeInTheDocument()
  })
})
