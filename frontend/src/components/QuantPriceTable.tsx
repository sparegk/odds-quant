import { Check } from 'lucide-react'

import { formatDateTime, formatOdds, formatPercent } from '../lib/format'
import type { MarketComparison } from '../types'
import { FreshnessBadge } from './FreshnessBadge'

interface QuantPriceTableProps {
  market: MarketComparison
}

export function QuantPriceTable({ market }: QuantPriceTableProps) {
  const best = new Map(market.best_prices.map((price) => [price.selection_code, price]))
  const bookmakerCount = new Set(market.snapshots.map((snapshot) => snapshot.bookmaker_id)).size
  const staleCount = market.snapshots.filter((snapshot) => snapshot.is_stale).length
  const closingCount = market.snapshots.filter((snapshot) => snapshot.is_closing).length

  return (
    <div className="w-full max-w-full border-y border-zinc-200 bg-white">
      <dl aria-label="Market evidence summary" className="grid grid-cols-2 border-b border-zinc-200 bg-zinc-50 text-xs sm:grid-cols-4">
        <EvidenceSummary label="Bookmakers" value={String(bookmakerCount)} />
        <EvidenceSummary label="Snapshots" value={String(market.snapshots.length)} />
        <EvidenceSummary label="Stale" value={String(staleCount)} warning={staleCount > 0} />
        <EvidenceSummary label="Explicit closing" value={String(closingCount)} warning={closingCount === 0} />
      </dl>
      <div className="overflow-x-auto">
      <table className="w-full min-w-[1180px] border-collapse text-left text-sm">
        <thead className="bg-zinc-50 text-xs font-semibold uppercase text-zinc-500">
          <tr>
            <th className="px-4 py-3">Bookmaker</th>
            <th className="px-4 py-3">Selection</th>
            <th className="px-4 py-3 text-right">Offered</th>
            <th className="px-4 py-3 text-right">Raw implied</th>
            <th className="px-4 py-3 text-right">Vig-free</th>
            <th className="px-4 py-3 text-right">Fair odds</th>
            <th className="px-4 py-3 text-right">Margin</th>
            <th className="px-4 py-3">Freshness</th>
            <th className="px-4 py-3">Observed / source</th>
            <th className="px-4 py-3">Evidence</th>
          </tr>
        </thead>
        <tbody>
          {market.snapshots.flatMap((snapshot) =>
            snapshot.prices.map((price) => {
              const isBest = best.get(price.selection_code)?.bookmaker === snapshot.bookmaker
              return (
                <tr key={`${snapshot.snapshot_id}-${price.selection_code}`} className="border-t border-zinc-100">
                  <td className="px-4 py-3 font-medium text-zinc-900">{snapshot.bookmaker}</td>
                  <td className="px-4 py-3 text-zinc-700">{price.selection_name}</td>
                  <td className="px-4 py-3 text-right font-mono font-semibold text-zinc-950">
                    <span className="inline-flex items-center justify-end gap-1.5">
                      {formatOdds(price.decimal_odds)}
                      {isBest ? <Check aria-label="Best available price" className="text-emerald-600" size={15} /> : null}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-zinc-700">
                    {formatPercent(price.raw_implied_probability)}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-zinc-700">
                    {formatPercent(price.proportional_fair_probability)}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-zinc-700">
                    {formatOdds(price.proportional_fair_odds)}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-zinc-700">
                    {formatPercent(snapshot.bookmaker_margin)}
                  </td>
                  <td className="px-4 py-3">
                    <FreshnessBadge seconds={snapshot.freshness_seconds} stale={snapshot.is_stale} />
                  </td>
                  <td className="px-4 py-3 text-xs text-zinc-600"><p>{formatDateTime(snapshot.observed_at)}</p><p className="mt-1 text-zinc-400">Source {snapshot.source_updated_at ? formatDateTime(snapshot.source_updated_at) : 'timestamp unavailable'}</p></td>
                  <td className="px-4 py-3 text-xs"><p className="font-semibold">{snapshot.provider}</p><p className="mt-1 text-zinc-500">{snapshot.source_label}</p><span className={`mt-1 inline-block border px-1.5 py-0.5 font-bold ${snapshot.is_closing ? 'border-sky-200 bg-sky-50 text-sky-800' : 'border-zinc-200 bg-zinc-50 text-zinc-600'}`}>{snapshot.is_closing ? 'EXPLICIT CLOSING' : 'NON-CLOSING'}</span></td>
                </tr>
              )
            }),
          )}
        </tbody>
      </table>
      </div>
      {!closingCount ? <p className="border-t border-amber-200 bg-amber-50 px-4 py-3 text-xs leading-5 text-amber-900">No snapshot carries explicit closing provenance. Do not infer closing price or CLV from the latest observed row.</p> : null}
    </div>
  )
}

function EvidenceSummary({ label, value, warning = false }: { label: string; value: string; warning?: boolean }) {
  return <div className="border-r border-zinc-200 px-3 py-2"><dt className="font-semibold uppercase text-zinc-500">{label}</dt><dd className={`mt-1 font-mono font-bold ${warning ? 'text-amber-700' : 'text-zinc-800'}`}>{value}</dd></div>
}
