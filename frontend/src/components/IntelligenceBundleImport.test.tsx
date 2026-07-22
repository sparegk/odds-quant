import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { IntelligenceBundleImport } from './IntelligenceBundleImport'

afterEach(cleanup)

describe('IntelligenceBundleImport', () => {
  it('provides the full strict bundle template and catches invalid JSON locally', async () => {
    render(<IntelligenceBundleImport adminKey="" />)
    const editor = screen.getByLabelText('Intelligence bundle JSON')
    expect(editor).toHaveDisplayValue(/player_statistics/)
    expect(editor).toHaveDisplayValue(/coach_tenures/)
    expect(editor).toHaveDisplayValue(/lineups/)
    fireEvent.change(editor, { target: { value: '{bad json' } })
    fireEvent.click(screen.getByText('Import intelligence bundle'))
    expect(await screen.findByRole('alert')).toHaveTextContent(/JSON/)
  })
})
