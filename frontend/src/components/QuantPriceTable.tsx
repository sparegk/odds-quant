import { Check } from 'lucide-react'

import { formatOdds, formatPercent } from '../lib/format'
import type { MarketComparison } from '../types'
import { FreshnessBadge } from './FreshnessBadge'

interface QuantPriceTableProps {
  market: MarketComparison
}

export function QuantPriceTable({ market }: QuantPriceTableProps) {
  const best = new Map(market.best_prices.map((price) => [price.selection_code, price]))

  return (
    <div className="w-full max-w-full overflow-x-auto border-y border-zinc-200 bg-white">
      <table className="w-full min-w-[940px] border-collapse text-left text-sm">
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
                </tr>
              )
            }),
          )}
        </tbody>
      </table>
    </div>
  )
}
