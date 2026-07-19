import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { FreshnessBadge } from './FreshnessBadge'

describe('FreshnessBadge', () => {
  it('labels recent odds as fresh', () => {
    render(<FreshnessBadge seconds={42} stale={false} />)
    expect(screen.getByLabelText('Fresh odds, 42s old')).toHaveTextContent('42s')
  })

  it('labels old odds as stale', () => {
    render(<FreshnessBadge seconds={7200} stale />)
    expect(screen.getByLabelText('Stale odds, 2h old')).toHaveTextContent('2h')
  })
})
