import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { DashboardData, ValueSignal } from './types'
import { SignalResearch } from './App'

const valueSignal: ValueSignal = {
  id: 1,
  event_id: 7,
  output_id: 11,
  model_version_id: 3,
  model_version: 'poisson-v1',
  evaluation_run_id: 5,
  prediction_id: 13,
  market_id: 17,
  market_type: 'MATCH_RESULT',
  line: null,
  selection_id: 19,
  selection_code: 'AWAY',
  selection_name: 'Harbour Athletic win',
  bookmaker_id: 23,
  bookmaker: 'Beacon',
  odds_snapshot_id: 29,
  signal_type: 'VALUE',
  offered_odds: 3.4,
  raw_implied_probability: 0.2941,
  market_fair_probability: 0.28,
  model_probability: 0.35,
  lower_probability: 0.31,
  expected_value: 0.19,
  lower_expected_value: 0.054,
  probability_edge: 0.07,
  confidence: 0.82,
  calibration_error: 0.025,
  odds_age_minutes: 2,
  bookmaker_count: 4,
  odds_move_ratio: 0.01,
  implied_move_points: 0.003,
  generated_at: '2026-07-19T12:00:00Z',
  reasons: ['The calibrated model probability exceeds compatible market consensus.'],
  risks: ['Price acceptance is not guaranteed.'],
}

const dashboard: DashboardData = {
  status: {
    phase: 'model_baseline',
    sports: ['football'],
    data_mode: 'user_supplied',
    automated_betting: false,
  },
  events: [
    {
      id: 7,
      provider_event_key: 'event-7',
      competition: 'Research League',
      country: 'GB',
      season: '2026',
      home_team: 'Northbridge FC',
      away_team: 'Harbour Athletic',
      kickoff_at: '2026-07-20T18:00:00Z',
      status: 'scheduled',
      is_demo: false,
      latest_odds_at: '2026-07-19T12:00:00Z',
    },
  ],
  providers: [],
  imports: [],
  jobs: [],
  models: [],
  evaluations: [],
  signals: [valueSignal],
  underdogs: [valueSignal],
}

describe('SignalResearch', () => {
  it('shows distinct model, market, edge, EV, provenance, and risk evidence', () => {
    render(<SignalResearch dashboard={dashboard} mode="value" />)

    expect(screen.getByText('Explainable price signals')).toBeInTheDocument()
    const row = screen.getByText('Northbridge FC vs Harbour Athletic').closest('tr')
    expect(row).not.toBeNull()
    const cells = within(row as HTMLTableRowElement)
    expect(cells.getByText('35.0%')).toBeInTheDocument()
    expect(cells.getByText('28.0%')).toBeInTheDocument()
    expect(cells.getByText('+7.0%')).toBeInTheDocument()
    expect(cells.getByText('+19.0%')).toBeInTheDocument()
    expect(cells.getByText('+5.4%')).toBeInTheDocument()
    expect(cells.getByText(/Eval #5 \/ 4 books \/ 2m old/)).toBeInTheDocument()
    expect(cells.getByText('Price acceptance is not guaranteed.')).toBeInTheDocument()
  })

  it('fails closed when no qualified underdog signals exist', () => {
    render(<SignalResearch dashboard={{ ...dashboard, underdogs: [] }} mode="underdog" />)

    expect(screen.getByText('No qualified underdogs')).toBeInTheDocument()
    expect(screen.getByText(/Long odds and demo prices are never treated as value/)).toBeInTheDocument()
  })
})
