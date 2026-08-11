import { useEffect, useState } from 'react'
import { AlertTriangle, CheckCircle2, LockKeyhole } from 'lucide-react'

import { loadMarketEdgeCoverage } from '../api/client'
import { formatDateTime, humanizeCode } from '../lib/format'
import type { MarketEdgeCoverage } from '../types'
import { DesktopDataTable, type DesktopColumn } from './DesktopDataTable'

export function MarketEdgeCoverageAudit({ refreshVersion = 0 }: { refreshVersion?: number }) {
  const [coverage, setCoverage] = useState<MarketEdgeCoverage | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    loadMarketEdgeCoverage()
      .then((data) => {
        if (active) {
          setCoverage(data)
          setError(null)
        }
      })
      .catch((caught) => {
        if (active) setError(caught instanceof Error ? caught.message : 'Market-edge audit failed')
      })
    return () => { active = false }
  }, [refreshVersion])

  return <section aria-labelledby="market-edge-coverage-title">
    <div className="mb-3">
      <p className="text-xs font-bold uppercase text-emerald-700">Frozen prospective cohort</p>
      <h3 className="mt-1 text-lg font-bold" id="market-edge-coverage-title">Market-edge acquisition audit</h3>
      <p className="mt-1 max-w-3xl text-sm leading-6 text-zinc-500">Outcome-blind collection coverage for the fixed Premier League 2026/27 validation contract. Replay remains locked until every acquisition blocker clears.</p>
    </div>
    {error ? <div className="flex gap-2 border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900" role="alert"><AlertTriangle aria-hidden="true" className="shrink-0" size={18} /><span>{error}</span></div> : null}
    {!coverage && !error ? <div className="border-y border-zinc-200 bg-white px-4 py-8 text-center text-sm text-zinc-500">Auditing frozen-cohort acquisition…</div> : null}
    {coverage ? <CoverageReceipt coverage={coverage} /> : null}
  </section>
}

function CoverageReceipt({ coverage }: { coverage: MarketEdgeCoverage }) {
  const ready = coverage.acquisition_ready && coverage.replay_authorized && coverage.blockers.length === 0
  return <>
    <div className={`flex gap-3 border-l-4 px-4 py-3 text-sm ${ready ? 'border-emerald-500 bg-emerald-50 text-emerald-950' : 'border-amber-500 bg-amber-50 text-amber-950'}`} role={ready ? 'status' : 'alert'}>
      {ready ? <CheckCircle2 aria-hidden="true" className="mt-0.5 shrink-0" size={18} /> : <LockKeyhole aria-hidden="true" className="mt-0.5 shrink-0" size={18} />}
      <div>
        <p className="font-bold">{ready ? 'Acquisition complete; fixed replay authorized' : 'Acquisition incomplete; fixed replay locked'}</p>
        <p className="mt-1 text-xs">Observed {formatDateTime(coverage.observed_at)} · contract {coverage.contract_version}</p>
      </div>
    </div>
    <div className="mt-3 grid gap-px border border-zinc-200 bg-zinc-200 sm:grid-cols-2 xl:grid-cols-6">
      <Metric label="Stored events" value={`${coverage.stored_events} / ${coverage.expected_events}`} />
      <Metric label="Predictions" value={coverage.prediction_events} />
      <Metric label="Decision window" value={coverage.decision_window_events} detail={percent(coverage.decision_window_coverage)} />
      <Metric label="Two bookmakers" value={coverage.two_bookmaker_events} detail={percent(coverage.two_bookmaker_coverage)} />
      <Metric label="Explicit closing" value={coverage.explicit_closing_events} detail={percent(coverage.closing_coverage)} />
      <Metric label="Final results" value={coverage.final_result_events} />
    </div>
    <div className="mt-4">
      <DesktopDataTable ariaLabel="Market-edge bookmaker acquisition coverage" columns={bookmakerColumns} filename="market-edge-bookmaker-coverage.csv" rowKey={(item) => item.bookmaker_id} rows={coverage.bookmakers} />
    </div>
    {coverage.blockers.length ? <div className="mt-3 border border-amber-200 bg-white p-4">
      <p className="text-xs font-bold uppercase text-amber-800">Acquisition blockers</p>
      <ul className="mt-2 grid gap-2 text-sm text-zinc-700 md:grid-cols-2">
        {coverage.blockers.map((blocker) => <li className="flex gap-2" key={blocker}><AlertTriangle aria-hidden="true" className="mt-0.5 shrink-0 text-amber-700" size={15} /><span>{humanizeCode(blocker)}</span></li>)}
      </ul>
    </div> : null}
    <p className="mt-3 text-xs leading-5 text-zinc-500">This receipt reports aggregate collection readiness only. It cannot authorize replay while any listed blocker remains.</p>
  </>
}

const bookmakerColumns: DesktopColumn<MarketEdgeCoverage['bookmakers'][number]>[] = [
  { id: 'bookmaker', label: 'Bookmaker', value: (item) => item.bookmaker, render: (item) => <p className="font-semibold">{item.bookmaker}</p> },
  { id: 'snapshots', label: 'Complete snapshots', value: (item) => item.permitted_snapshots, align: 'right' },
  { id: 'events', label: 'Snapshot events', value: (item) => item.permitted_snapshot_events, align: 'right' },
  { id: 'decision', label: 'Decision window', value: (item) => item.decision_window_events, align: 'right' },
  { id: 'closing', label: 'Explicit closing', value: (item) => item.explicit_closing_events, align: 'right' },
  { id: 'costs', label: 'Cost profile', value: (item) => item.cost_profile_events, align: 'right' },
]

function Metric({ label, value, detail }: { label: string; value: number | string; detail?: string }) {
  return <div className="bg-white p-4"><p className="text-xs font-semibold uppercase text-zinc-500">{label}</p><p className="mt-1 font-mono text-xl font-bold">{value}</p>{detail ? <p className="mt-1 text-xs text-zinc-500">{detail}</p> : null}</div>
}

function percent(value: number): string {
  return `${(value * 100).toFixed(1)}% coverage`
}
