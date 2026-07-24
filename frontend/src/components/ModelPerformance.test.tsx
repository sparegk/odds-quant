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

  it('presents block-bootstrap intervals and paired benchmark evidence', () => {
    const model = { id: 3, name: 'Poisson baseline', version: 'poisson-v1', kind: 'poisson', training_start: '2026-01-01T00:00:00Z', training_end: '2026-06-01T00:00:00Z', data_fingerprint: 'abcdef1234567890', feature_version: 'team-strength-v1', sample_size: 80, evaluation_status: 'calibrated', config: {}, metrics: {}, status: 'trained', is_demo: false, created_at: '2026-06-01T01:00:00Z' }
    const interval = (estimate: number, lower: number, upper: number) => ({ method: 'moving_block_bootstrap', estimate, lower, upper, confidence_level: 0.95, resamples: 2000, block_length: 3, observations: 40, seed: 17 })
    const paired = (brier: [number, number, number], logLoss: [number, number, number]) => ({ definition: 'poisson_loss_minus_benchmark_loss', negative_values_favor: 'poisson', brier_score: interval(...brier), log_loss: interval(...logLoss) })
    const evaluation = {
      id: 8, model_version_id: 3, model_version: 'poisson-v1', status: 'completed', evaluation_start: '2026-03-01T00:00:00Z', evaluation_end: '2026-06-01T00:00:00Z', fingerprint: 'evaluation-fingerprint', config: {}, policy: {}, evaluation_status: 'calibrated', is_demo: false,
      metrics: { brier_score: 0.5, log_loss: 0.8, expected_calibration_error: 0.04, evaluated_events: 40, candidate_events: 40, observations: 40, score_intervals: { brier_score: interval(0.5, 0.47, 0.53), log_loss: interval(0.8, 0.75, 0.85) } },
      benchmarks: {
        dixon_coles: { brier_score: 0.52, log_loss: 0.82, observations: 40, score_intervals: { brier_score: interval(0.52, 0.49, 0.55), log_loss: interval(0.82, 0.77, 0.87) }, paired_loss_difference: paired([-0.02, -0.04, -0.005], [-0.02, -0.04, -0.003]) },
        elo: { brier_score: 0.51, log_loss: 0.81, observations: 40, score_intervals: { brier_score: interval(0.51, 0.48, 0.54), log_loss: interval(0.81, 0.76, 0.86) }, paired_loss_difference: paired([-0.01, -0.03, 0.01], [-0.01, -0.03, -0.001]) },
        uniform: { brier_score: 0.45, log_loss: 0.7, observations: 40, score_intervals: { brier_score: interval(0.45, 0.43, 0.47), log_loss: interval(0.7, 0.67, 0.73) }, paired_loss_difference: paired([0.05, 0.02, 0.08], [0.1, 0.05, 0.15]) },
      },
      calibration: [], created_at: '2026-06-01T02:00:00Z',
    }

    render(<ModelPerformance dashboard={{ ...base, models: [model], evaluations: [evaluation] }} />)

    expect(screen.getByText('Chronological Elo')).toBeInTheDocument()
    expect(screen.getByText('Dixon-Coles')).toBeInTheDocument()
    expect(screen.getByText('Market consensus')).toBeInTheDocument()
    expect(screen.getAllByText('0.5000 [0.4700, 0.5300]')).toHaveLength(2)
    expect(screen.getByText('-0.0200 [-0.0400, -0.0050]')).toBeInTheDocument()
    expect(screen.getByText('POISSON BETTER')).toBeInTheDocument()
    expect(screen.getByText('INCONCLUSIVE')).toBeInTheDocument()
    expect(screen.getByText('BENCHMARK BETTER')).toBeInTheDocument()
    expect(screen.getByText('NO INTERVAL')).toBeInTheDocument()
    expect(screen.getByText(/a wholly negative 95% interval favors Poisson/)).toBeInTheDocument()
  })
})
