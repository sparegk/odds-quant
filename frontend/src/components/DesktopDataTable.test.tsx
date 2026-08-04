import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { DesktopDataTable } from './DesktopDataTable'

afterEach(cleanup)

describe('DesktopDataTable', () => {
  const rows = [{ id: 1, team: 'Zulu', odds: 2.4 }, { id: 2, team: 'Alpha', odds: 1.8 }]
  const columns = [{ id: 'team', label: 'Team', value: (row: typeof rows[number]) => row.team }, { id: 'odds', label: 'Odds', value: (row: typeof rows[number]) => row.odds, align: 'right' as const }]

  it('debounces search, sorts, bounds rendered rows, and exposes CSV export', async () => {
    render(<DesktopDataTable ariaLabel="Prices" columns={columns} filename="prices.csv" rowKey={(row) => row.id} rows={rows} />)
    fireEvent.change(screen.getByLabelText('Prices search'), { target: { value: 'Alpha' } })
    await waitFor(() => expect(screen.getByText('1 matching row · page 1 of 1')).toBeInTheDocument())
    expect(screen.queryByText('Zulu')).not.toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Prices search'), { target: { value: '' } })
    fireEvent.change(screen.getByLabelText('Prices sort column'), { target: { value: 'odds' } })
    const bodyRows = within(screen.getByRole('table', { name: 'Prices' })).getAllByRole('row').slice(1)
    expect(bodyRows[0]).toHaveTextContent('Alpha')
    expect(screen.getByRole('link', { name: 'Export CSV' })).toHaveAttribute('download', 'prices.csv')
  })
})
