import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { loadMarketEdgeCoverage } from '../api/client'
import { MarketEdgeCoverageAudit } from './MarketEdgeCoverageAudit'

vi.mock('../api/client', () => ({ loadMarketEdgeCoverage: vi.fn() }))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('MarketEdgeCoverageAudit', () => {
  it('shows separate bookmaker coverage and keeps replay locked by bounded blockers', async () => {
    vi.mocked(loadMarketEdgeCoverage).mockResolvedValue({
      contract_version: 'cold-start-v2-market-edge-validation-v1',
      cohort_selection_id: 'premier-league-2026-27-post-activation-full-season',
      observed_at: '2026-08-12T09:30:00Z',
      activated_model_id: 12,
      activated_model_version: 'pqc2-c5-202606020000-7917411c',
      expected_events: 380,
      stored_events: 30,
      final_result_events: 0,
      prediction_events: 1,
      permitted_snapshots: 1750,
      decision_window_events: 0,
      two_bookmaker_events: 0,
      explicit_closing_events: 0,
      qualifying_bookmaker_event_pairs: 0,
      cost_profile_bookmaker_event_pairs: 0,
      decision_window_coverage: 0,
      two_bookmaker_coverage: 0,
      closing_coverage: 0,
      cost_profile_coverage: 0,
      minimum_market_observations: 160,
      minimum_market_coverage: 0.8,
      minimum_closing_coverage: 0.8,
      bookmakers: [
        { bookmaker_id: 3, bookmaker: 'Allwyn / Pamestoixima', permitted_snapshots: 1750, permitted_snapshot_events: 10, decision_window_events: 0, explicit_closing_events: 0, cost_profile_events: 0 },
        { bookmaker_id: 4, bookmaker: 'Novibet', permitted_snapshots: 0, permitted_snapshot_events: 0, decision_window_events: 0, explicit_closing_events: 0, cost_profile_events: 0 },
      ],
      acquisition_ready: false,
      replay_authorized: false,
      blockers: ['incomplete_candidate_universe', 'insufficient_explicit_closing_coverage'],
    })

    render(<MarketEdgeCoverageAudit />)

    expect(await screen.findByText('Acquisition incomplete; fixed replay locked')).toBeInTheDocument()
    expect(screen.getByText('30 / 380')).toBeInTheDocument()
    expect(screen.getByText('Allwyn / Pamestoixima')).toBeInTheDocument()
    expect(screen.getByText('Novibet')).toBeInTheDocument()
    expect(screen.getByText('Incomplete Candidate Universe')).toBeInTheDocument()
    expect(screen.getByText('Insufficient Explicit Closing Coverage')).toBeInTheDocument()
    expect(screen.queryByText(/ROI|CLV|profit|return/i)).not.toBeInTheDocument()
  })

  it('fails closed when the audit endpoint is unavailable', async () => {
    vi.mocked(loadMarketEdgeCoverage).mockRejectedValue(new Error('API request failed: 503'))

    render(<MarketEdgeCoverageAudit />)

    expect(await screen.findByRole('alert')).toHaveTextContent('API request failed: 503')
    expect(screen.queryByText(/replay authorized/i)).not.toBeInTheDocument()
  })
})
