import {
  Beaker,
  Bookmark,
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
  | 'workspace'
  | 'models'
  | 'backtests'
  | 'bankroll'
  | 'data'
  | 'methodology'

export interface NavigationItem {
  key: ViewKey
  label: string
  icon: LucideIcon
  path: string
}

interface NavigationGroup {
  label: string
  items: readonly NavigationItem[]
}

export const navigationGroups: readonly NavigationGroup[] = [
  {
    label: 'Matches',
    items: [
      { key: 'matchday', label: 'Matchday', icon: CalendarDays, path: '/' },
      { key: 'event', label: 'Match detail', icon: CalendarDays, path: '/matches' },
      { key: 'comparison', label: 'Odds comparison', icon: GitCompareArrows, path: '/odds' },
    ],
  },
  {
    label: 'Research',
    items: [
      { key: 'opportunities', label: 'Value opportunities', icon: TrendingUp, path: '/research/value' },
      { key: 'underdogs', label: 'Underdog scanner', icon: ScanSearch, path: '/research/underdogs' },
      { key: 'builder', label: 'Bet Builder Lab', icon: Beaker, path: '/research/builder' },
      { key: 'workspace', label: 'Research workspace', icon: Bookmark, path: '/research/workspace' },
    ],
  },
  {
    label: 'Analytics',
    items: [
      { key: 'overview', label: 'Research overview', icon: Gauge, path: '/analytics' },
      { key: 'models', label: 'Model performance', icon: LineChart, path: '/analytics/models' },
      { key: 'backtests', label: 'Backtesting', icon: FlaskConical, path: '/analytics/backtests' },
      { key: 'bankroll', label: 'Bankroll research', icon: CircleDollarSign, path: '/analytics/bankroll' },
    ],
  },
  {
    label: 'Admin',
    items: [
      { key: 'arbitrage', label: 'Arbitrage', icon: ShieldCheck, path: '/admin/arbitrage' },
      { key: 'data', label: 'Data operations', icon: Database, path: '/admin/data' },
    ],
  },
  {
    label: 'About',
    items: [{ key: 'methodology', label: 'Methodology', icon: BookOpen, path: '/methodology' }],
  },
]

export const navigation: readonly NavigationItem[] = navigationGroups.flatMap(
  (group) => group.items,
)

export interface SiteRoute {
  view: ViewKey
  eventId: number | null
  notFound: boolean
}

export const navigationEventName = 'oddsquant:navigation'

export function eventPath(eventId: number): string {
  return `/matches/${eventId}`
}

export function readRoute(): SiteRoute {
  const match = window.location.pathname.match(/^\/matches\/(\d+)\/?$/)
  const eventId = match ? Number(match[1]) : null
  if (eventId !== null && Number.isSafeInteger(eventId) && eventId > 0) {
    return { view: 'event', eventId, notFound: false }
  }

  const path = normalizePath(window.location.pathname)
  const item = navigation.find((candidate) => candidate.path === path)
  if (item) return { view: item.key, eventId: null, notFound: false }
  return { view: 'matchday', eventId: null, notFound: true }
}

export function readView(): ViewKey {
  return readRoute().view
}

export function navigateToView(view: ViewKey): void {
  const target = navigation.find((item) => item.key === view)?.path ?? '/'
  window.history.pushState(null, '', target)
  window.dispatchEvent(new Event(navigationEventName))
}

export function navigationContext(view: ViewKey): { group: string; label: string } {
  for (const group of navigationGroups) {
    const item = group.items.find((candidate) => candidate.key === view)
    if (item) return { group: group.label, label: item.label }
  }
  return { group: 'OddsQuant', label: 'Not found' }
}

function normalizePath(path: string): string {
  if (path === '/') return path
  return path.replace(/\/+$/, '')
}

export function navigateToEvent(eventId: number): void {
  window.history.pushState(null, '', eventPath(eventId))
  window.dispatchEvent(new Event(navigationEventName))
}
