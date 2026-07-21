import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import type { DashboardData, ValueSignal } from './types'
import { ArbitrageResearch, BacktestResearch, InlineError, InlineLoading, ResourceErrors, SignalResearch } from './App'

afterEach(cleanup)

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
  arbitrage: [],
  backtests: [],
  resource_errors: {},
}

describe('SignalResearch', () => {
  it('shows distinct model, market, edge, EV, provenance, and risk evidence', () => {
    render(<SignalResearch dashboard={dashboard} mode="value" />)

    expect(screen.getByText('Immutable value recommendations')).toBeInTheDocument()
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

describe('ArbitrageResearch', () => {
  it('shows worst-case economics, costs, provenance, and execution warnings', () => {
    render(
      <ArbitrageResearch
        dashboard={{
          ...dashboard,
          arbitrage: [
            {
              id: 31,
              event_id: 7,
              market_id: 17,
              market_type: 'MATCH_RESULT',
              line: null,
              period: 'FULL_TIME',
              settlement_rule_key: 'standard_90_minutes',
              calculated_at: '2026-07-19T12:01:00Z',
              fingerprint: 'abcdef1234567890',
              status: 'executable',
              inverse_sum: 0.97,
              budget: 100,
              total_cash_outlay: 99.98,
              minimum_net_payout: 102.5,
              net_profit: 2.52,
              net_roi: 0.0252,
              tax_status: 'verified',
              constraint_status: 'verified',
              freshness_status: 'fresh',
              currency: 'EUR',
              risks: ['Recheck every price immediately before submitting any leg.'],
              legs: [
                {
                  id: 37,
                  selection_id: 19,
                  selection_code: 'HOME',
                  selection_name: 'Northbridge FC win',
                  bookmaker_id: 23,
                  bookmaker: 'Beacon',
                  odds_snapshot_id: 29,
                  tax_profile_id: 41,
                  bookmaker_constraint_id: 43,
                  decimal_odds: 3.1,
                  stake: 33.2,
                  cash_outlay: 33.2,
                  gross_payout: 102.92,
                  win_deductions: 0.42,
                  taxes_and_fees: 0.42,
                  net_payout: 102.5,
                },
              ],
            },
          ],
        }}
      />,
    )

    expect(screen.getAllByText('EXECUTABLE')).toHaveLength(1)
    expect(screen.getByText('EUR 99.98')).toBeInTheDocument()
    expect(screen.getAllByText('EUR 102.50')).toHaveLength(2)
    expect(screen.getAllByText('EUR 2.52')).toHaveLength(2)
    expect(screen.getByText('+2.5%')).toBeInTheDocument()
    expect(screen.getByText('Snapshot #29 / tax #41 / limit #43')).toBeInTheDocument()
    expect(screen.getByText('Recheck every price immediately before submitting any leg.')).toBeInTheDocument()
    expect(screen.getByText(/never a guarantee that every bookmaker leg/)).toBeInTheDocument()
  })

  it('explains why no gross calculation is displayed as executable by default', () => {
    render(<ArbitrageResearch dashboard={dashboard} />)

    expect(screen.getByText('No stored arbitrage calculations')).toBeInTheDocument()
    expect(screen.getByText(/Missing or stale tax rules/)).toBeInTheDocument()
  })
})

describe('dashboard resource states', () => {
  it('keeps partial API failures and comparison failures visible', () => {
    render(
      <>
        <ResourceErrors errors={{ signals: 'API request failed: 503', arbitrage: 'API request failed: 502' }} />
        <InlineError message="API request failed: 504" />
        <InlineLoading text="Loading price comparison" />
      </>,
    )

    expect(screen.getByText('Some dashboard resources are unavailable')).toBeInTheDocument()
    expect(screen.getByText(/Signals, Arbitrage/)).toBeInTheDocument()
    expect(screen.getByText(/API request failed: 504/)).toBeInTheDocument()
    expect(screen.getByText('Loading price comparison')).toBeInTheDocument()
  })
})

describe('BacktestResearch', () => {
  it('shows settled return evidence separately from calibration', () => {
    render(<BacktestResearch dashboard={{
      ...dashboard,
      backtests: [{
        id: 44,
        model_version_id: 3,
        model_version: 'poisson-v1',
        status: 'completed',
        evaluation_start: '2026-01-01T00:00:00Z',
        evaluation_end: '2026-06-01T00:00:00Z',
        fingerprint: 'abcdef1234567890',
        evaluation_status: 'research_only',
        is_demo: false,
        config: {},
        policy: { profitability_claim_allowed: false },
        metrics: { bet_count: 24, net_profit_units: 3.2, roi: 0.1333, maximum_drawdown_units: 4.5 },
        observations: [],
        created_at: '2026-07-19T12:00:00Z',
      }],
    }} />)

    expect(screen.getByText('#44 / poisson-v1')).toBeInTheDocument()
    expect(screen.getByText('Research Only')).toBeInTheDocument()
    expect(screen.getByText('+13.3%')).toBeInTheDocument()
    expect(screen.getByText('No chronological evaluations')).toBeInTheDocument()
  })
})
