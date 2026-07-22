import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import type { ArbitrageSettings } from '../types'
import { SettingsWorkspace } from './ArbitrageSettings'

afterEach(cleanup)

const settings: ArbitrageSettings = {
  bookmakers: [{ id: 2, slug: 'beacon', name: 'Beacon', is_demo: false }],
  tax_profiles: [{ id: 3, bookmaker_id: 2, bookmaker: 'Beacon', name: 'GR terms', jurisdiction: 'GR', currency: 'EUR', stake_tax_rate: '0.010000', winnings_tax_rate: '0', payout_withholding_rate: '0', commission_rate: '0.020000', fixed_fee: '0', effective_from: '2026-07-01T00:00:00Z', effective_to: null, verified_at: '2026-07-01T00:00:00Z', source_url: null, source_label: 'Official terms', status: 'verified' }],
  constraints: [{ id: 4, bookmaker_id: 2, bookmaker: 'Beacon', currency: 'EUR', minimum_stake: '1.0000', maximum_stake: '500.0000', stake_increment: '0.0100', observed_at: '2026-07-01T00:00:00Z', source_label: 'Account observation' }],
}

describe('ArbitrageSettings', () => {
  it('shows sourced tax and constraint provenance and both entry modes', () => {
    render(<SettingsWorkspace settings={settings} onSaved={() => Promise.resolve()} />)
    expect(screen.getByText(/Stake 1.00%/)).toBeInTheDocument()
    expect(screen.getByText(/max 500.0000/)).toBeInTheDocument()
    expect(screen.getByText(/Official terms/)).toBeInTheDocument()
    fireEvent.click(screen.getByText('Stake constraints'))
    expect(screen.getByLabelText('Maximum stake')).toBeInTheDocument()
    expect(screen.getByLabelText('Source label')).toBeInTheDocument()
  })
})
