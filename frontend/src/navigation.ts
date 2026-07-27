import {
  Beaker,
  BookOpen,
  CalendarDays,
  CircleDollarSign,
  Database,
  FlaskConical,
  Gauge,
  GitCompareArrows,
  LineChart,
  ScanSearch,
  ShieldCheck,
  TrendingUp,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

export type ViewKey =
  | 'overview'
  | 'matchday'
  | 'opportunities'
  | 'underdogs'
  | 'arbitrage'
  | 'event'
  | 'comparison'
  | 'builder'
  | 'models'
  | 'backtests'
  | 'bankroll'
  | 'data'
  | 'methodology'

interface NavigationItem {
  key: ViewKey
  label: string
  icon: LucideIcon
}

interface NavigationGroup {
  label: string
  items: readonly NavigationItem[]
}

export const navigationGroups: readonly NavigationGroup[] = [
  {
    label: 'Matches',
    items: [
      { key: 'matchday', label: 'Matchday', icon: CalendarDays },
      { key: 'event', label: 'Event markets', icon: CalendarDays },
      { key: 'comparison', label: 'Odds comparison', icon: GitCompareArrows },
    ],
  },
  {
    label: 'Research',
    items: [
      { key: 'opportunities', label: 'Value opportunities', icon: TrendingUp },
      { key: 'underdogs', label: 'Underdog scanner', icon: ScanSearch },
      { key: 'builder', label: 'Bet Builder Lab', icon: Beaker },
    ],
  },
  {
    label: 'Analytics',
    items: [
      { key: 'overview', label: 'Research overview', icon: Gauge },
      { key: 'models', label: 'Model performance', icon: LineChart },
      { key: 'backtests', label: 'Backtesting', icon: FlaskConical },
      { key: 'bankroll', label: 'Bankroll research', icon: CircleDollarSign },
    ],
  },
  {
    label: 'Admin',
    items: [
      { key: 'arbitrage', label: 'Arbitrage', icon: ShieldCheck },
      { key: 'data', label: 'Data operations', icon: Database },
    ],
  },
  {
    label: 'About',
    items: [{ key: 'methodology', label: 'Methodology', icon: BookOpen }],
  },
]

export const navigation: readonly NavigationItem[] = navigationGroups.flatMap(
  (group) => group.items,
)

export interface SiteRoute {
  view: ViewKey
  eventId: number | null
}

export const navigationEventName = 'oddsquant:navigation'

export function eventPath(eventId: number): string {
  return `/matches/${eventId}`
}

export function readRoute(): SiteRoute {
  const candidate = window.location.hash.slice(1)
  if (navigation.some((item) => item.key === candidate)) {
    return { view: candidate as ViewKey, eventId: null }
  }

  const match = window.location.pathname.match(/^\/matches\/(\d+)\/?$/)
  const eventId = match ? Number(match[1]) : null
  if (eventId !== null && Number.isSafeInteger(eventId) && eventId > 0) {
    return { view: 'event', eventId }
  }

  return { view: 'matchday', eventId: null }
}

export function readView(): ViewKey {
  return readRoute().view
}

export function navigateToView(view: ViewKey): void {
  const target = view === 'matchday' ? '/' : `/#${view}`
  window.history.pushState(null, '', target)
  window.dispatchEvent(new Event(navigationEventName))
}

export function navigateToEvent(eventId: number): void {
  window.history.pushState(null, '', eventPath(eventId))
  window.dispatchEvent(new Event(navigationEventName))
}
