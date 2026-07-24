import { describe, expect, it } from 'vitest'

import type { EventSummary } from '../types'
import { nextGoodMatchdayDate } from './matchdays'

function event(overrides: Partial<EventSummary>): EventSummary {
  return {
    id: 1,
    provider_event_key: 'event-1',
    competition: 'Premier League',
    country: 'England',
    season: '2026/27',
    home_team: 'Home',
    away_team: 'Away',
    kickoff_at: '2026-07-28T18:00:00Z',
    status: 'scheduled',
    is_demo: false,
    latest_odds_at: '2026-07-24T10:00:00Z',
    ...overrides,
  }
}

describe('nextGoodMatchdayDate', () => {
  it('prefers the next priced featured matchday over nearer demo fixtures', () => {
    const events = [
      event({
        id: 1,
        competition: 'Synthetic Premier Division',
        kickoff_at: '2026-07-25T18:00:00Z',
        is_demo: true,
      }),
      event({
        id: 2,
        competition: 'UEFA Champions League Qualification',
        kickoff_at: '2026-07-28T18:00:00Z',
      }),
    ]

    expect(
      nextGoodMatchdayDate(events, 'Europe/Athens', new Date('2026-07-24T12:00:00Z')),
    ).toBe('2026-07-28')
  })

  it('falls back to the earliest future imported fixture when no featured price exists', () => {
    const events = [
      event({
        id: 1,
        competition: 'Regional Cup',
        kickoff_at: '2026-07-25T21:30:00Z',
        latest_odds_at: null,
      }),
      event({
        id: 2,
        competition: 'Regional Cup',
        kickoff_at: '2026-07-26T18:00:00Z',
        latest_odds_at: null,
      }),
    ]

    expect(
      nextGoodMatchdayDate(events, 'Europe/Athens', new Date('2026-07-24T12:00:00Z')),
    ).toBe('2026-07-26')
  })

  it('returns null when every imported fixture is in the past', () => {
    expect(
      nextGoodMatchdayDate(
        [event({ kickoff_at: '2026-07-20T18:00:00Z' })],
        'Europe/Athens',
        new Date('2026-07-24T12:00:00Z'),
      ),
    ).toBeNull()
  })
})
