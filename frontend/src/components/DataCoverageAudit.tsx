import { useEffect, useState } from 'react'
import { AlertTriangle, CheckCircle2 } from 'lucide-react'

import { loadDataCoverage } from '../api/client'
import { formatDateTime, humanizeCode } from '../lib/format'
import type { DataCoverage } from '../types'
import { DesktopDataTable, type DesktopColumn } from './DesktopDataTable'

export function DataCoverageAudit({ refreshVersion = 0 }: { refreshVersion?: number }) {
  const [coverage, setCoverage] = useState<DataCoverage | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    loadDataCoverage()
      .then((data) => { if (active) { setCoverage(data); setError(null) } })
      .catch((caught) => { if (active) setError(caught instanceof Error ? caught.message : 'Coverage audit failed') })
    return () => { active = false }
  }, [refreshVersion])

  return <section>
    <div className="mb-3"><p className="text-xs font-bold uppercase text-emerald-700">Provenance gate</p><h3 className="mt-1 text-lg font-bold">Permitted data coverage</h3><p className="mt-1 max-w-3xl text-sm leading-6 text-zinc-500">Only non-demo events, providers, bookmakers, results, and timestamped prices count toward evaluation readiness.</p></div>
    {error ? <div className="flex gap-2 border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900" role="alert"><AlertTriangle aria-hidden="true" className="shrink-0" size={18} /><span>{error}</span></div> : null}
    {!coverage && !error ? <div className="border-y border-zinc-200 bg-white px-4 py-8 text-center text-sm text-zinc-500">Auditing permitted data…</div> : null}
    {coverage ? <>
      <div className="grid gap-px border border-zinc-200 bg-zinc-200 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="Events" value={coverage.permitted_events} /><Metric label="Final results" value={coverage.permitted_final_results} /><Metric label="Odds snapshots" value={coverage.permitted_odds_snapshots} /><Metric label="Closing snapshots" value={coverage.permitted_closing_snapshots} />
      </div>
      {coverage.permitted_events === 0 ? <div className="mt-3 flex gap-2 border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950"><AlertTriangle aria-hidden="true" className="mt-0.5 shrink-0" size={18} /><span>Demo records are excluded. Import licensed or user-supplied events, results, and timestamped odds before evaluating models.</span></div> : null}
      <div className="mt-4">{coverage.competitions.length ? <DesktopDataTable ariaLabel="Permitted competition coverage" columns={coverageColumns(coverage)} filename="permitted-data-coverage.csv" rowKey={(item) => item.competition_id} rows={coverage.competitions} /> : <div className="border-y border-zinc-200 bg-white px-4 py-8 text-center text-sm text-zinc-500">No competitions are available to audit.</div>}</div>
    </> : null}
  </section>
}

function coverageColumns(coverage: DataCoverage): DesktopColumn<DataCoverage['competitions'][number]>[] { return [
  { id: 'competition', label: 'Competition', value: (item) => item.competition + ' ' + item.country + ' ' + item.season, render: (item) => <><p className="font-semibold">{item.competition}</p><p className="text-xs text-zinc-500">{item.country} · {item.season}</p>{item.first_result_kickoff_at ? <p className="mt-1 text-xs text-zinc-400">{formatDateTime(item.first_result_kickoff_at)} – {formatDateTime(item.last_result_kickoff_at)}</p> : null}</> },
  { id: 'events', label: 'Events / teams', value: (item) => item.permitted_events, render: (item) => <span className="font-mono">{item.permitted_events} / {item.permitted_teams}</span>, align: 'right' },
  { id: 'results', label: 'Final results', value: (item) => item.permitted_final_results, render: (item) => <span className="font-mono">{item.permitted_final_results} / {coverage.minimum_evaluation_results}</span>, align: 'right' },
  { id: 'odds', label: 'Odds', value: (item) => item.permitted_odds_snapshots, align: 'right' },
  { id: 'books', label: 'Target books', value: (item) => item.covered_required_bookmakers.length, render: (item) => <><p className="font-mono">{item.covered_required_bookmakers.length} / {coverage.required_bookmakers.length}</p><p className="mt-1 max-w-52 text-xs leading-5 text-zinc-500">{item.missing_required_bookmakers.length ? `Missing: ${item.missing_required_bookmakers.join(', ')}` : 'All required books covered'}</p></> },
  { id: 'closing', label: 'Closing coverage', value: (item) => item.closing_event_coverage, render: (item) => <><span className="font-mono">{item.permitted_closing_snapshots}</span><p className="text-xs text-zinc-500">{(item.closing_event_coverage * 100).toFixed(1)}% events</p></>, align: 'right' },
  { id: 'gate', label: 'Evaluation gate', value: (item) => item.evaluation_ready ? 'ready' : 'blocked ' + item.blockers.join(' '), render: (item) => item.evaluation_ready ? <span className="inline-flex items-center gap-1 text-xs font-bold text-emerald-800"><CheckCircle2 aria-hidden="true" size={16} />READY</span> : <><span className="text-xs font-bold text-amber-800">BLOCKED</span><p className="mt-1 max-w-xs text-xs leading-5 text-zinc-500">{item.blockers.map(humanizeCode).join(' · ')}</p></> },
] }

function Metric({ label, value }: { label: string; value: number }) {
  return <div className="bg-white p-4"><p className="text-xs font-semibold uppercase text-zinc-500">{label}</p><p className="mt-1 font-mono text-2xl font-bold">{value}</p></div>
}
