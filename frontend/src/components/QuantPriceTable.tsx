import { Check } from 'lucide-react'

import { formatDateTime, formatOdds, formatPercent } from '../lib/format'
import type { MarketComparison } from '../types'
import type { DesktopColumn } from './DesktopDataTable'
import { DesktopDataTable } from './DesktopDataTable'
import { FreshnessBadge } from './FreshnessBadge'

interface QuantPriceTableProps {
  market: MarketComparison
}

export function QuantPriceTable({ market }: QuantPriceTableProps) {
  const best = new Map(market.best_prices.map((price) => [price.selection_code, price]))
  const bookmakerCount = new Set(market.snapshots.map((snapshot) => snapshot.bookmaker_id)).size
  const staleCount = market.snapshots.filter((snapshot) => snapshot.is_stale).length
  const closingCount = market.snapshots.filter((snapshot) => snapshot.is_closing).length
  const rows = market.snapshots.flatMap((snapshot) => snapshot.prices.map((price) => ({ id: `${snapshot.snapshot_id}-${price.selection_code}`, snapshot, price, isBest: best.get(price.selection_code)?.bookmaker === snapshot.bookmaker })))
  type PriceRow = typeof rows[number]
  const columns: DesktopColumn<PriceRow>[] = [
    { id: 'bookmaker', label: 'Bookmaker', value: (row) => row.snapshot.bookmaker, render: (row) => <span className="font-medium text-zinc-900">{row.snapshot.bookmaker}</span> },
    { id: 'selection', label: 'Selection', value: (row) => row.price.selection_name },
    { id: 'offered', label: 'Offered', value: (row) => row.price.decimal_odds, align: 'right', render: (row) => <span className="inline-flex items-center justify-end gap-1.5 font-mono font-semibold text-zinc-950">{formatOdds(row.price.decimal_odds)}{row.isBest ? <Check aria-label="Best available price" className="text-emerald-600" size={15} /> : null}</span> },
    { id: 'raw', label: 'Raw implied', value: (row) => row.price.raw_implied_probability, align: 'right', render: (row) => <span className="font-mono">{formatPercent(row.price.raw_implied_probability)}</span> },
    { id: 'vig_free', label: 'Vig-free', value: (row) => row.price.proportional_fair_probability, align: 'right', render: (row) => <span className="font-mono">{formatPercent(row.price.proportional_fair_probability)}</span> },
    { id: 'fair_odds', label: 'Fair odds', value: (row) => row.price.proportional_fair_odds, align: 'right', render: (row) => <span className="font-mono">{formatOdds(row.price.proportional_fair_odds)}</span> },
    { id: 'margin', label: 'Margin', value: (row) => row.snapshot.bookmaker_margin, align: 'right', render: (row) => <span className="font-mono">{formatPercent(row.snapshot.bookmaker_margin)}</span> },
    { id: 'freshness', label: 'Freshness', value: (row) => row.snapshot.freshness_seconds, render: (row) => <FreshnessBadge seconds={row.snapshot.freshness_seconds} stale={row.snapshot.is_stale} /> },
    { id: 'observed', label: 'Observed / source', value: (row) => row.snapshot.observed_at, render: (row) => <span className="text-xs"><span className="block">{formatDateTime(row.snapshot.observed_at)}</span><span className="mt-1 block text-zinc-400">Source {row.snapshot.source_updated_at ? formatDateTime(row.snapshot.source_updated_at) : 'timestamp unavailable'}</span></span> },
    { id: 'evidence', label: 'Evidence', value: (row) => `${row.snapshot.provider} ${row.snapshot.source_label}`, render: (row) => <span className="text-xs"><span className="block font-semibold">{row.snapshot.provider}</span><span className="mt-1 block text-zinc-500">{row.snapshot.source_label}</span><span className={`mt-1 inline-block border px-1.5 py-0.5 font-bold ${row.snapshot.is_closing ? 'border-sky-200 bg-sky-50 text-sky-800' : 'border-zinc-200 bg-zinc-50 text-zinc-600'}`}>{row.snapshot.is_closing ? 'EXPLICIT CLOSING' : 'NON-CLOSING'}</span></span> },
  ]

  return (
    <div className="w-full max-w-full border-y border-zinc-200 bg-white">
      <dl aria-label="Market evidence summary" className="grid grid-cols-2 border-b border-zinc-200 bg-zinc-50 text-xs sm:grid-cols-4">
        <EvidenceSummary label="Bookmakers" value={String(bookmakerCount)} />
        <EvidenceSummary label="Snapshots" value={String(market.snapshots.length)} />
        <EvidenceSummary label="Stale" value={String(staleCount)} warning={staleCount > 0} />
        <EvidenceSummary label="Explicit closing" value={String(closingCount)} warning={closingCount === 0} />
      </dl>
      <DesktopDataTable ariaLabel={`${market.market_type} price evidence`} columns={columns} filename={`odds-market-${market.market_id}.csv`} rowKey={(row) => row.id} rows={rows} />
      {!closingCount ? <p className="border-t border-amber-200 bg-amber-50 px-4 py-3 text-xs leading-5 text-amber-900">No snapshot carries explicit closing provenance. Do not infer closing price or CLV from the latest observed row.</p> : null}
    </div>
  )
}

function EvidenceSummary({ label, value, warning = false }: { label: string; value: string; warning?: boolean }) {
  return <div className="border-r border-zinc-200 px-3 py-2"><dt className="font-semibold uppercase text-zinc-500">{label}</dt><dd className={`mt-1 font-mono font-bold ${warning ? 'text-amber-700' : 'text-zinc-800'}`}>{value}</dd></div>
}
