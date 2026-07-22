import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { DashboardData, EventSummary, MarketComparison } from '../types'
import { EventMarkets } from './EventMarkets'

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

const event: EventSummary = { id: 7, provider_event_key: 'event-7', competition: 'Research League', country: 'GB', season: '2026', home_team: 'Northbridge FC', away_team: 'Harbour Athletic', kickoff_at: '2026-07-20T18:00:00Z', status: 'scheduled', is_demo: false, latest_odds_at: '2026-07-19T12:00:00Z' }
const dashboard: DashboardData = { status: { phase: 'model_baseline', sports: ['football'], data_mode: 'user_supplied', automated_betting: false }, events: [event], providers: [], imports: [], jobs: [], models: [], evaluations: [], signals: [], underdogs: [], arbitrage: [], backtests: [], resource_errors: {} }
const markets: MarketComparison[] = [{ market_id: 1, market_type: 'MATCH_RESULT', line: null, period: 'FULL_TIME', currency: 'EUR', settlement_rule_key: 'standard_90_minutes', best_prices: [{ selection_code: 'HOME', selection_name: 'Home win', bookmaker: 'Beacon', decimal_odds: 2.5, observed_at: '2026-07-19T12:00:00Z', freshness_seconds: 30 }], snapshots: [{ snapshot_id: 2, bookmaker_id: 3, bookmaker: 'Beacon', provider: 'licensed-feed', observed_at: '2026-07-19T12:00:00Z', source_updated_at: null, is_closing: false, is_demo: false, source_label: 'Licensed', freshness_seconds: 30, is_stale: false, overround: 1.04, bookmaker_margin: 0.04, prices: [{ selection_code: 'HOME', selection_name: 'Home win', decimal_odds: 2.5, raw_implied_probability: 0.4, proportional_fair_probability: 0.38, proportional_fair_odds: 2.63, power_fair_probability: 0.37, power_fair_odds: 2.7 }] }] }]

describe('EventMarkets', () => {
  it('combines event, settlement, bookmaker, freshness, and prediction evidence', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response('[]', { status: 200 }))))
    render(<EventMarkets dashboard={dashboard} events={[event]} selectedEventId={7} markets={markets} loading={false} error={null} onSelectEvent={() => undefined} onOpenComparison={() => undefined} />)
    expect(screen.getByText('Northbridge FC vs Harbour Athletic')).toBeInTheDocument()
    expect(screen.getByText('standard_90_minutes')).toBeInTheDocument()
    expect(screen.getByText('BEST')).toBeInTheDocument()
    expect(screen.getByText(/FRESH · 30s/)).toBeInTheDocument()
    expect(await screen.findByText('No pre-kickoff prediction')).toBeInTheDocument()
  })
})
