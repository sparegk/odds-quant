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

export function readView(): ViewKey {
  const candidate = window.location.hash.slice(1)
  return navigation.some((item) => item.key === candidate)
    ? (candidate as ViewKey)
    : 'matchday'
}
