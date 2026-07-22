import type { EventSummary } from '../types'

export function chooseDefaultEventId(events: EventSummary[]): number | null {
  return events.find((event) => event.latest_odds_at !== null)?.id ?? events[0]?.id ?? null
}

export function preserveSelectedEventId(events: EventSummary[], current: number | null): number | null {
  return current !== null && events.some((event) => event.id === current)
    ? current
    : chooseDefaultEventId(events)
}
