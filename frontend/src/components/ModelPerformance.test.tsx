import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import type { DashboardData } from '../types'
import { ModelPerformance } from './ModelPerformance'

afterEach(cleanup)

const base: DashboardData = { status: { phase: 'model_baseline', sports: ['football'], data_mode: 'user_supplied', automated_betting: false }, events: [], providers: [], imports: [], jobs: [], models: [], evaluations: [], signals: [], underdogs: [], arbitrage: [], backtests: [], resource_errors: {} }

describe('ModelPerformance', () => {
  it('keeps training provenance separate from absent evaluation evidence', () => {
    render(<ModelPerformance dashboard={{ ...base, models: [{ id: 3, name: 'Poisson baseline', version: 'poisson-v1', kind: 'poisson', training_start: '2026-01-01T00:00:00Z', training_end: '2026-06-01T00:00:00Z', data_fingerprint: 'abcdef1234567890', feature_version: 'team-strength-v1', sample_size: 80, probability_evaluation_status: 'unvalidated', evaluation_status: 'unvalidated', config: {}, metrics: {}, status: 'trained', is_demo: false, created_at: '2026-06-01T01:00:00Z' }] }} />)
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
    const model = { id: 3, name: 'Poisson baseline', version: 'poisson-v1', kind: 'poisson', training_start: '2026-01-01T00:00:00Z', training_end: '2026-06-01T00:00:00Z', data_fingerprint: 'abcdef1234567890', feature_version: 'team-strength-v1', sample_size: 80, probability_evaluation_status: 'probability_validated', evaluation_status: 'insufficient_market_evidence', config: {}, metrics: {}, status: 'trained', is_demo: false, created_at: '2026-06-01T01:00:00Z' }
    const interval = (estimate: number, lower: number, upper: number) => ({ method: 'moving_block_bootstrap', estimate, lower, upper, confidence_level: 0.95, resamples: 2000, block_length: 3, observations: 40, seed: 17 })
    const paired = (brier: [number, number, number], logLoss: [number, number, number]) => ({ definition: 'poisson_loss_minus_benchmark_loss', negative_values_favor: 'poisson', brier_score: interval(...brier), log_loss: interval(...logLoss) })
    const evaluation = {
      id: 8, model_version_id: 3, model_version: 'poisson-v1', status: 'completed', evaluation_start: '2026-03-01T00:00:00Z', evaluation_end: '2026-06-01T00:00:00Z', fingerprint: 'evaluation-fingerprint', config: {}, policy: {
        version: 'separated-probability-market-v6', minimum_observations: 40, minimum_coverage: 0.9, maximum_expected_calibration_error: 0.08, minimum_market_observations: 20, minimum_market_coverage: 0.8,
        probability_checks: { non_demo_data: true, minimum_observations: true, minimum_coverage: true, maximum_expected_calibration_error: true, uniform_brier_upper_difference_below_zero: true, uniform_log_loss_upper_difference_below_zero: true, chronological_recalibration_accepted: true },
        checks: { non_demo_data: true, minimum_observations: true, minimum_coverage: true, maximum_expected_calibration_error: true, uniform_brier_upper_difference_below_zero: true, uniform_log_loss_upper_difference_below_zero: true, chronological_recalibration_accepted: true, market_benchmark_available: false, minimum_market_observations: false, minimum_market_coverage: false, market_brier_upper_difference_below_zero: false, market_log_loss_upper_difference_below_zero: false },
      }, probability_evaluation_status: 'probability_validated', evaluation_status: 'insufficient_market_evidence', is_demo: false,
      metrics: { brier_score: 0.5, log_loss: 0.8, expected_calibration_error: 0.04, evaluated_events: 40, candidate_events: 40, observations: 40, score_intervals: { brier_score: interval(0.5, 0.47, 0.53), log_loss: interval(0.8, 0.75, 0.85) } },
      benchmarks: {
        poisson_cold_start: { brier_score: 0.49, log_loss: 0.79, expected_calibration_error: 0.04, observations: 44, evaluated_events: 44, candidate_events: 44, below_minimum_venue_history_events: 4, paired_loss_difference: paired([0.01, -0.01, 0.03], [0.01, -0.01, 0.03]) },
        dixon_coles: { brier_score: 0.52, log_loss: 0.82, observations: 40, score_intervals: { brier_score: interval(0.52, 0.49, 0.55), log_loss: interval(0.82, 0.77, 0.87) }, paired_loss_difference: paired([-0.02, -0.04, -0.005], [-0.02, -0.04, -0.003]) },
        elo: { brier_score: 0.51, log_loss: 0.81, observations: 40, score_intervals: { brier_score: interval(0.51, 0.48, 0.54), log_loss: interval(0.81, 0.76, 0.86) }, paired_loss_difference: paired([-0.01, -0.03, 0.01], [-0.01, -0.03, -0.001]) },
        nested_selected: { brier_score: 0.505, log_loss: 0.805, expected_calibration_error: 0.045, observations: 40, selection_counts: { poisson_shrinkage_5: 25, elo_k_20: 15 }, paired_loss_difference: paired([-0.005, -0.02, 0.01], [-0.005, -0.02, 0.01]) },
        chronological_ensemble: { brier_score: 0.495, log_loss: 0.795, expected_calibration_error: 0.035, observations: 40, weight_counts: { 'poisson=0.5|elo=0.25|dixon_coles=0.25': 40 }, paired_loss_difference: paired([0.005, -0.005, 0.015], [0.005, -0.005, 0.015]) },
        uniform: { brier_score: 0.45, log_loss: 0.7, observations: 40, score_intervals: { brier_score: interval(0.45, 0.43, 0.47), log_loss: interval(0.7, 0.67, 0.73) }, paired_loss_difference: paired([0.05, 0.02, 0.08], [0.1, 0.05, 0.15]) },
        temperature_scaled: { method: 'identity', activation_status: 'accepted', development_observations: 60, validation_observations: 60, brier_score: 0.49, log_loss: 0.79, expected_calibration_error: 0.04, raw_subset_metrics: { brier_score: 0.49, log_loss: 0.79, expected_calibration_error: 0.04 }, final_calibrator: { fit_through: '2026-06-01T00:00:00Z', sample_size: 120, input_fingerprint: 'calibrator-fingerprint' } },
      },
      calibration: [], created_at: '2026-06-01T02:00:00Z',
    }

    const externalValidation = {
      experiment_id: 'bundesliga-2024-25-v6-poisson-primary',
      display_name: 'Bundesliga 2024/25',
      evidence_role: 'pre_registered_external_holdout',
      specification_frozen_at: '2026-08-04T00:00:00Z',
      executed_at: '2026-08-07T12:00:35Z',
      evaluation_fingerprint: 'external-validation-fingerprint',
      probability_decision: 'insufficient_evidence',
      examined: true,
      retuning_permitted: false,
      market_validation_authorized: false,
    }
    render(<ModelPerformance dashboard={{ ...base, models: [model], evaluations: [{ ...evaluation, external_validation: externalValidation }] }} />)

    expect(screen.getByRole('heading', { name: 'External validation receipt' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Bundesliga 2024/25' })).toBeInTheDocument()
    expect(screen.getByText('EXAMINED · INSUFFICIENT EVIDENCE')).toBeInTheDocument()
    expect(screen.getByText('Evaluation fingerprint: external-validation-fingerprint')).toBeInTheDocument()
    expect(screen.getAllByText('Not permitted').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Not authorized').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Chronological Elo').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Poisson cold-start').length).toBeGreaterThan(0)
    expect(screen.getByText(/44 \/ 44 coverage · 4 cold-start events/)).toBeInTheDocument()
    expect(screen.getAllByText('Dixon-Coles').length).toBeGreaterThan(0)
    expect(screen.getByRole('heading', { name: 'Model and configuration comparison' })).toBeInTheDocument()
    expect(screen.getByText('Identical evaluation window')).toBeInTheDocument()
    expect(screen.getByText('CHECK COVERAGE')).toBeInTheDocument()
    expect(screen.getAllByText('Nested selected').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Chronological ensemble').length).toBeGreaterThan(0)
    expect(screen.getByText(/Poisson Shrinkage 5 25/)).toBeInTheDocument()
    expect(screen.getByText(/poisson=0.5\|elo=0.25\|dixon_coles=0.25 \(40\)/)).toBeInTheDocument()
    expect(screen.getByText(/only exact-window evidence is included/)).toBeInTheDocument()
    expect(screen.getByText('Market consensus')).toBeInTheDocument()
    expect(screen.getAllByText('0.5000 [0.4700, 0.5300]')).toHaveLength(2)
    expect(screen.getByText('-0.0200 [-0.0400, -0.0050]')).toBeInTheDocument()
    expect(screen.getAllByText('POISSON BETTER').length).toBeGreaterThan(0)
    expect(screen.getAllByText('INCONCLUSIVE').length).toBeGreaterThan(0)
    expect(screen.getAllByText('BENCHMARK BETTER').length).toBeGreaterThan(0)
    expect(screen.getAllByText('NO INTERVAL').length).toBeGreaterThan(0)
    expect(screen.getByText(/a wholly negative 95% interval favors Poisson/)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Validation readiness' })).toBeInTheDocument()
    expect(screen.getByText('Probability research validated')).toBeInTheDocument()
    expect(screen.getByText('Market / value policy')).toBeInTheDocument()
    expect(screen.getAllByText('Probability Validated').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Insufficient Market Evidence').length).toBeGreaterThan(0)
    expect(screen.getByText('Paired interval verdict: BENCHMARK BETTER.')).toBeInTheDocument()
    expect(screen.getByText(/value signals remain blocked unless it is calibrated/)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Why this evaluation is blocked' })).toBeInTheDocument()
    expect(screen.getByText('Evaluation #8 / Probability Validated')).toBeInTheDocument()
    expect(screen.getByText('Calibration decision')).toBeInTheDocument()
    expect(screen.getByText('Identity')).toBeInTheDocument()
    expect(screen.getByText(/Import compatible timestamped historical bookmaker/)).toBeInTheDocument()
    expect(screen.getByText(/Calibrator fingerprint: calibrator-fingerprint/)).toBeInTheDocument()
  })
})
