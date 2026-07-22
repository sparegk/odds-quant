import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { loadDataCoverage } from '../api/client'
import { DataCoverageAudit } from './DataCoverageAudit'

vi.mock('../api/client', () => ({ loadDataCoverage: vi.fn() }))

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('DataCoverageAudit', () => {
  it('excludes demo data and explains each evaluation blocker', async () => {
    vi.mocked(loadDataCoverage).mockResolvedValue({
      minimum_evaluation_results: 200, required_bookmakers: ['Allwyn / Pamestoixima', 'Novibet'], total_events: 72, permitted_events: 0,
      permitted_final_results: 0, permitted_odds_snapshots: 0, permitted_closing_snapshots: 0,
      competitions: [{ competition_id: 1, competition: 'Demo League', country: 'GB', season: '2025/26', total_events: 72, permitted_events: 0, permitted_teams: 0, permitted_final_results: 0, permitted_odds_snapshots: 0, permitted_closing_snapshots: 0, covered_required_bookmakers: [], missing_required_bookmakers: ['Allwyn / Pamestoixima', 'Novibet'], first_result_kickoff_at: null, last_result_kickoff_at: null, closing_event_coverage: 0, evaluation_ready: false, blockers: ['no_permitted_events', 'fewer_than_200_final_results', 'no_closing_prices', 'missing_required_bookmakers'] }],
    })
    render(<DataCoverageAudit />)
    expect(await screen.findByText('Demo records are excluded. Import licensed or user-supplied events, results, and timestamped odds before evaluating models.')).toBeInTheDocument()
    expect(screen.getByText('No Permitted Events · Fewer Than 200 Final Results · No Closing Prices · Missing Required Bookmakers')).toBeInTheDocument()
    expect(screen.getByText('BLOCKED')).toBeInTheDocument()
    expect(screen.getByText('Missing: Allwyn / Pamestoixima, Novibet')).toBeInTheDocument()
  })
})
