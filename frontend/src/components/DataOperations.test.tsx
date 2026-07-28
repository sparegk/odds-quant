import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { CollectionMonitoring, DashboardData } from '../types'
import { DataOperations } from './DataOperations'

vi.mock('./DataCoverageAudit', () => ({ DataCoverageAudit: () => null }))

const baseDashboard: DashboardData = {
  status: { phase: 'model_baseline', sports: ['football'], data_mode: 'user_supplied', automated_betting: false },
  events: [], providers: [], imports: [], jobs: [], models: [], evaluations: [], signals: [], underdogs: [], arbitrage: [], backtests: [], resource_errors: {},
}

const healthyMonitoring: CollectionMonitoring = {
  observed_at: '2026-07-24T12:47:17Z',
  expected_poll_seconds: 900,
  recent_job_limit: 10,
  healthy: true,
  providers: [{
    provider_id: 4,
    provider: 'Odds-API.io',
    provider_slug: 'odds-api-io',
    latest_job_id: 31,
    latest_job_status: 'completed',
    latest_job_created_at: '2026-07-24T12:46:21Z',
    latest_job_finished_at: '2026-07-24T12:46:23Z',
    latest_success_at: '2026-07-24T12:46:23Z',
    consecutive_completed_jobs: 10,
    failures_in_recent_window: 0,
    running_job_age_seconds: null,
    latest_success_age_seconds: 53,
    healthy: true,
    blockers: [],
  }],
  alerts: [],
  latest_prediction_refresh: {
    provider_job_id: 64,
    provider_slug: 'odds-api-io',
    job_created_at: '2026-07-24T12:46:21Z',
    job_finished_at: '2026-07-24T12:46:23Z',
    eligible_events: 42,
    predictions_created: 3,
    predictions_reused: 0,
    events_skipped: 39,
    research_candidates_available: 5,
    skip_reasons: {
      insufficient_home_team_home_history: 33,
      insufficient_away_team_away_history: 6,
    },
  },
  coverage: {
    minimum_evaluation_results: 200,
    required_bookmakers: ['Allwyn / Pamestoixima', 'Novibet'],
    total_events: 1701,
    permitted_events: 1621,
    permitted_final_results: 1520,
    permitted_odds_snapshots: 868,
    permitted_closing_snapshots: 0,
    competitions: [],
  },
}

afterEach(cleanup)

describe('DataOperations', () => {
  it('shows atomic upload paths and stored rejection details', () => {
    const dashboard: DashboardData = { ...baseDashboard, imports: [{ id: 9, filename: 'bad.csv', status: 'rejected', rows_received: 2, rows_imported: 0, errors: [{ row: 2, message: 'snapshot outcome set is incomplete' }], created_at: '2026-07-19T12:00:00Z' }] }
    render(<DataOperations dashboard={dashboard} />)
    expect(screen.getByText('Odds snapshots')).toBeInTheDocument()
    expect(screen.getByText('Historical results')).toBeInTheDocument()
    expect(screen.getByText('Player availability')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Results CSV template' })).toHaveAttribute('href', '/templates/results.csv')
    expect(screen.getByRole('link', { name: 'Odds CSV template' })).toHaveAttribute('href', '/templates/odds.csv')
    expect(screen.getByText('REJECTED')).toBeInTheDocument()
    expect(screen.getByText(/snapshot outcome set is incomplete/)).toBeInTheDocument()
  })

  it('shows a healthy consecutive collection baseline', () => {
    render(<DataOperations dashboard={{ ...baseDashboard, monitoring: healthyMonitoring }} />)

    expect(screen.getByRole('status')).toHaveTextContent('Collection healthy')
    expect(screen.getByText('Odds-API.io')).toBeInTheDocument()
    expect(screen.getByText('#31 / Completed')).toBeInTheDocument()
    expect(screen.getByText('No collection alerts detected.')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Prediction refresh' })).toBeInTheDocument()
    expect(screen.getByText('odds-api-io job #64', { exact: false })).toBeInTheDocument()
    expect(screen.getByText('Insufficient Home Team Home History')).toBeInTheDocument()
    expect(screen.getByText('Insufficient Away Team Away History')).toBeInTheDocument()
    expect(screen.getByText('Watchlist').parentElement).toHaveTextContent('5')
    expect(screen.getByText('Reasons accounted').parentElement).toHaveTextContent('39')
  })

  it('fails closed when prediction-refresh reasons do not reconcile', () => {
    const monitoring: CollectionMonitoring = {
      ...healthyMonitoring,
      latest_prediction_refresh: {
        ...healthyMonitoring.latest_prediction_refresh!,
        events_skipped: 40,
      },
    }
    render(<DataOperations dashboard={{ ...baseDashboard, monitoring }} />)

    expect(screen.getByRole('alert')).toHaveTextContent('Skip-reason counts do not reconcile')
  })

  it('explains when no valid prediction-refresh summary is available', () => {
    render(<DataOperations dashboard={{ ...baseDashboard, monitoring: { ...healthyMonitoring, latest_prediction_refresh: null } }} />)

    expect(screen.getByText(/No valid non-demo prediction-refresh summary/)).toBeInTheDocument()
  })

  it('shows a critical provider failure', () => {
    const monitoring: CollectionMonitoring = {
      ...healthyMonitoring,
      healthy: false,
      providers: [{
        ...healthyMonitoring.providers[0]!,
        latest_job_status: 'failed',
        healthy: false,
        blockers: ['latest_provider_job_not_completed'],
      }],
      alerts: [{ code: 'provider_collection_failed', severity: 'critical', provider_slug: 'odds-api-io', competition: null, bookmaker: null, detail: 'Latest provider collection failed.' }],
    }
    render(<DataOperations dashboard={{ ...baseDashboard, monitoring }} />)

    expect(screen.getByRole('alert')).toHaveTextContent('Collection attention required')
    const alerts = screen.getByRole('list', { name: 'Collection alerts' })
    expect(alerts).toHaveTextContent('Provider Collection Failed')
    expect(alerts).toHaveTextContent('Latest provider collection failed.')
    expect(screen.getByText('Latest Provider Job Not Completed')).toBeInTheDocument()
  })

  it('identifies a bookmaker coverage regression', () => {
    const monitoring: CollectionMonitoring = {
      ...healthyMonitoring,
      healthy: false,
      alerts: [{ code: 'bookmaker_coverage_regressed', severity: 'critical', provider_slug: 'odds-api-io', competition: 'UEFA Champions League Qualification', bookmaker: 'Novibet', detail: 'Required bookmaker disappeared from the latest completed batch.' }],
    }
    render(<DataOperations dashboard={{ ...baseDashboard, monitoring }} />)

    const alerts = screen.getByRole('list', { name: 'Collection alerts' })
    expect(alerts).toHaveTextContent('Bookmaker Coverage Regressed')
    expect(alerts).toHaveTextContent('UEFA Champions League Qualification')
  })
})
