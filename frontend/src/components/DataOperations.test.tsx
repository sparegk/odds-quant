import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { DashboardData } from '../types'
import { DataOperations } from './DataOperations'

vi.mock('./DataCoverageAudit', () => ({ DataCoverageAudit: () => null }))

afterEach(cleanup)

describe('DataOperations', () => {
  it('shows atomic upload paths and stored rejection details', () => {
    const dashboard: DashboardData = { status: { phase: 'model_baseline', sports: ['football'], data_mode: 'user_supplied', automated_betting: false }, events: [], providers: [], imports: [{ id: 9, filename: 'bad.csv', status: 'rejected', rows_received: 2, rows_imported: 0, errors: [{ row: 2, message: 'snapshot outcome set is incomplete' }], created_at: '2026-07-19T12:00:00Z' }], jobs: [], models: [], evaluations: [], signals: [], underdogs: [], arbitrage: [], backtests: [], resource_errors: {} }
    render(<DataOperations dashboard={dashboard} />)
    expect(screen.getByText('Odds snapshots')).toBeInTheDocument()
    expect(screen.getByText('Historical results')).toBeInTheDocument()
    expect(screen.getByText('Player availability')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Results CSV template' })).toHaveAttribute('href', '/templates/results.csv')
    expect(screen.getByRole('link', { name: 'Odds CSV template' })).toHaveAttribute('href', '/templates/odds.csv')
    expect(screen.getByText('REJECTED')).toBeInTheDocument()
    expect(screen.getByText(/snapshot outcome set is incomplete/)).toBeInTheDocument()
  })
})
