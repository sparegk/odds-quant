import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { useResearchPreference } from './researchPreferences'

function Harness() {
  const [value, setValue] = useResearchPreference('competition', 'ALL')
  return <button onClick={() => setValue('Premier League')} type="button">{value}</button>
}

afterEach(() => { cleanup(); localStorage.clear(); history.replaceState(null, '', '/') })

describe('useResearchPreference', () => {
  it('writes shareable query state and restores it before local storage', () => {
    render(<Harness />)
    fireEvent.click(screen.getByRole('button'))
    expect(location.search).toBe('?competition=Premier+League')
    expect(localStorage.getItem('oddsquant:preference:competition')).toBe('Premier League')
    cleanup()
    history.replaceState(null, '', '/?competition=Champions+League')
    render(<Harness />)
    expect(screen.getByRole('button')).toHaveTextContent('Champions League')
  })
})
