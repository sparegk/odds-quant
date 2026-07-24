import type { EventSummary } from '../types'

const featuredCompetitionTerms = [
  'champions league',
  'premier league',
  'la liga',
  'primera division',
  'bundesliga',
  'ligue 1',
  'europa league',
  'conference league',
  'fa cup',
  'efl cup',
  'league cup',
  'carabao cup',
  'copa del rey',
  'dfb pokal',
  'coupe de france',
  'coppa italia',
  'uefa super cup',
  'world cup',
  'european championship',
  'uefa euro',
  'copa america',
  'nations league',
  'club world cup',
]

function dateInTimezone(value: Date, timezone: string): string {
  const parts = new Intl.DateTimeFormat('en-GB', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    timeZone: timezone,
  }).formatToParts(value)
  const part = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((item) => item.type === type)?.value ?? ''
  return `${part('year')}-${part('month')}-${part('day')}`
}

function isFeaturedCompetition(name: string): boolean {
  const normalized = name.toLocaleLowerCase()
  return featuredCompetitionTerms.some((term) => normalized.includes(term))
}

export function nextGoodMatchdayDate(
  events: EventSummary[],
  timezone: string,
  now = new Date(),
): string | null {
  const upcoming = events
    .filter((event) => new Date(event.kickoff_at).getTime() >= now.getTime())
    .sort((left, right) => {
      const kickoffDifference =
        new Date(left.kickoff_at).getTime() - new Date(right.kickoff_at).getTime()
      return kickoffDifference || left.id - right.id
    })

  const preferred =
    upcoming.find(
      (event) =>
        !event.is_demo &&
        event.latest_odds_at !== null &&
        isFeaturedCompetition(event.competition),
    ) ??
    upcoming.find((event) => !event.is_demo && event.latest_odds_at !== null) ??
    upcoming.find((event) => !event.is_demo) ??
    upcoming[0]

  return preferred ? dateInTimezone(new Date(preferred.kickoff_at), timezone) : null
}
