import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { DashboardData } from '../types'
import { OperationsCenter } from './OperationsCenter'

const dashboard = { status: { phase: 'research', sports: ['football'], data_mode: 'external', automated_betting: false }, events: [], providers: [], imports: [], jobs: [], models: [], evaluations: [], signals: [], underdogs: [], arbitrage: [], backtests: [], readiness: { events: 0, odds_snapshots: 0, final_results: 0, model_versions: 0, predictions: 0, non_demo_calibrated_evaluations: 0, signals: 0, signal_backtests: 0, bookmaker_tax_mappings: 0, bookmaker_constraints: 0, intelligence_records: 0 }, resource_errors: {} } satisfies DashboardData

afterEach(cleanup)

describe('OperationsCenter', () => {
  it('reports loaded health and records a manual refresh', async () => {
    const refresh = vi.fn().mockResolvedValue(undefined)
    render(<OperationsCenter dashboard={dashboard} onRefresh={refresh} />)
    expect(screen.getByRole('status')).toHaveTextContent('Loaded operational evidence is healthy')
    fireEvent.click(screen.getByRole('button', { name: 'Refresh all resources' }))
    await waitFor(() => expect(refresh).toHaveBeenCalled())
    expect(await screen.findByText('Dashboard resources synchronized.')).toBeInTheDocument()
  })
})
