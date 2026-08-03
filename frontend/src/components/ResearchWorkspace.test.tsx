import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { DashboardData } from '../types'
import { ResearchWorkspace } from './ResearchWorkspace'

const dashboard = { status: { phase: 'research', sports: ['football'], data_mode: 'external', automated_betting: false }, events: [{ id: 7, provider_event_key: 'e7', competition_id: 1, competition: 'League', country: 'GB', season: '2026', home_team: 'North', away_team: 'South', kickoff_at: '2026-08-10T18:00:00Z', status: 'scheduled', is_demo: false, latest_odds_at: null }], providers: [], imports: [], jobs: [], models: [], evaluations: [], signals: [], underdogs: [], arbitrage: [], backtests: [], resource_errors: {} } satisfies DashboardData

afterEach(() => { cleanup(); localStorage.clear() })

describe('ResearchWorkspace', () => {
  it('persists bookmarks and notes and opens the stored event', () => {
    const open = vi.fn()
    const { unmount } = render(<ResearchWorkspace dashboard={dashboard} onOpenEvent={open} />)
    fireEvent.click(screen.getByRole('button', { name: 'Save to workspace' }))
    fireEvent.change(screen.getByLabelText('Note for North vs South'), { target: { value: 'Check availability timestamp.' } })
    fireEvent.click(screen.getByRole('button', { name: 'Open event' }))
    expect(open).toHaveBeenCalledWith(7)
    unmount()
    render(<ResearchWorkspace dashboard={dashboard} onOpenEvent={open} />)
    expect(screen.getByDisplayValue('Check availability timestamp.')).toBeInTheDocument()
  })
})
