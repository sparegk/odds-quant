import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { rememberResearchGuideDismissal, researchGuideStorageKey, shouldShowResearchGuide } from '../lib/researchGuide'
import { FirstVisitGuide } from './FirstVisitGuide'

afterEach(() => {
  cleanup()
  window.localStorage.clear()
})

describe('FirstVisitGuide', () => {
  it('explains the four core research concepts and can be dismissed', () => {
    const dismiss = vi.fn()
    render(<FirstVisitGuide onDismiss={dismiss} />)

    expect(screen.getByText('Probability')).toBeInTheDocument()
    expect(screen.getByText('Fair odds')).toBeInTheDocument()
    expect(screen.getByText('Value gate')).toBeInTheDocument()
    expect(screen.getByText('Blocked')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss research guide' }))
    expect(dismiss).toHaveBeenCalledTimes(1)
  })

  it('persists dismissal without preventing a later manual reopen', () => {
    expect(shouldShowResearchGuide()).toBe(true)
    rememberResearchGuideDismissal()
    expect(window.localStorage.getItem(researchGuideStorageKey)).toBe('dismissed')
    expect(shouldShowResearchGuide()).toBe(false)
  })
})
