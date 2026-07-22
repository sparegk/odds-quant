import type { EventSummary } from '../types'

export function chooseDefaultEventId(events: EventSummary[]): number | null {
  return events.find((event) => event.latest_odds_at !== null)?.id ?? events[0]?.id ?? null
}
