import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { BetBuilderQuote } from '../types'
import { BuilderQuoteCard } from './BetBuilderLab'

const quote: BetBuilderQuote = {
  id: 12,
  event_id: 7,
  model_version_id: 3,
  model_version: 'poisson-v1',
  is_demo: true,
  evidence_class: 'team_baseline',
  prediction_output_id: 9,
  predicted_at: '2026-07-19T10:00:00Z',
  inputs_as_of: '2026-07-19T10:00:00Z',
  quoted_at: '2026-07-19T10:02:00Z',
  fingerprint: 'abcdef1234567890',
  feature_version: 'final-score-home-away-v1',
  input_fingerprint: '9876543210fedcba',
  legs: [
    { market_type: 'MATCH_RESULT', selection: 'HOME', line: null, marginal_probability: 0.5 },
    { market_type: 'TOTAL_GOALS', selection: 'OVER', line: 2.5, marginal_probability: 0.55 },
  ],
  joint_probability: 0.34,
  lower_joint_probability: 0.25,
  upper_joint_probability: 0.44,
  independent_product: 0.275,
  dependence_ratio: 1.236,
  fair_odds: 2.941,
  offered_odds: 3.2,
  offered_odds_source: 'Dashboard manual observation',
  offered_odds_observed_at: '2026-07-19T10:02:00Z',
  expected_value: 0.088,
  lower_expected_value: -0.2,
  warnings: ['Legs are correlated; joint probability is summed from scorelines, not multiplied.'],
}

describe('BuilderQuoteCard', () => {
  it('separates joint probability from the naive product and labels demo provenance', () => {
    render(<BuilderQuoteCard quote={quote} />)

    expect(screen.getByText('34.0%')).toBeInTheDocument()
    expect(screen.getByText('25.0%')).toBeInTheDocument()
    expect(screen.getByText('27.5%')).toBeInTheDocument()
    expect(screen.getByText('2.94')).toBeInTheDocument()
    expect(screen.getByText('-20.0%')).toBeInTheDocument()
    expect(screen.getByText(/DEMO MODEL/)).toBeInTheDocument()
    expect(screen.getByText(/summed from scorelines, not multiplied/)).toBeInTheDocument()
    expect(screen.getByText(/feature final-score-home-away-v1/)).toBeInTheDocument()
  })
})
