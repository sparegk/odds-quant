import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { MarketComparison } from '../types'
import { QuantPriceTable } from './QuantPriceTable'

const market: MarketComparison = {
  market_id: 1,
  market_type: 'MATCH_RESULT',
  line: null,
  period: 'FULL_TIME',
  currency: 'EUR',
  settlement_rule_key: 'standard_90_minutes',
  best_prices: [
    {
      selection_code: 'HOME',
      selection_name: 'Home win',
      bookmaker: 'Beacon',
      decimal_odds: 2.2,
      observed_at: '2026-07-19T12:00:00Z',
      freshness_seconds: 30,
    },
  ],
  snapshots: [
    {
      snapshot_id: 10,
      bookmaker_id: 2,
      bookmaker: 'Beacon',
      provider: 'Demo provider',
      observed_at: '2026-07-19T12:00:00Z',
      source_updated_at: '2026-07-19T12:00:00Z',
      is_closing: false,
      is_demo: true,
      source_label: 'DEMO DATA',
      freshness_seconds: 30,
      is_stale: false,
      overround: 1.05,
      bookmaker_margin: 0.05,
      prices: [
        {
          selection_code: 'HOME',
          selection_name: 'Home win',
          decimal_odds: 2.2,
          raw_implied_probability: 1 / 2.2,
          proportional_fair_probability: 0.43,
          proportional_fair_odds: 1 / 0.43,
          power_fair_probability: 0.42,
          power_fair_odds: 1 / 0.42,
        },
      ],
    },
  ],
}

describe('QuantPriceTable', () => {
  it('renders distinct raw, vig-free, fair, margin, and best-price fields', () => {
    render(<QuantPriceTable market={market} />)
    const row = screen.getByText('Beacon').closest('tr')
    expect(row).not.toBeNull()
    const cells = within(row as HTMLTableRowElement)
    expect(cells.getByText('2.20')).toBeInTheDocument()
    expect(cells.getByText('45.5%')).toBeInTheDocument()
    expect(cells.getByText('43.0%')).toBeInTheDocument()
    expect(cells.getByText('2.33')).toBeInTheDocument()
    expect(cells.getByText('5.0%')).toBeInTheDocument()
    expect(cells.getByLabelText('Best available price')).toBeInTheDocument()
  })
})
