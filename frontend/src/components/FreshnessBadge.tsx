import { Clock3 } from 'lucide-react'

interface FreshnessBadgeProps {
  seconds: number
  stale: boolean
}

function formatAge(seconds: number): string {
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`
  return `${Math.floor(seconds / 86400)}d`
}

export function FreshnessBadge({ seconds, stale }: FreshnessBadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-[4px] border px-2 py-1 text-xs font-semibold ${
        stale
          ? 'border-amber-300 bg-amber-50 text-amber-800'
          : 'border-emerald-200 bg-emerald-50 text-emerald-800'
      }`}
      aria-label={stale ? `Stale odds, ${formatAge(seconds)} old` : `Fresh odds, ${formatAge(seconds)} old`}
    >
      <Clock3 aria-hidden="true" size={13} />
      {formatAge(seconds)}
    </span>
  )
}
