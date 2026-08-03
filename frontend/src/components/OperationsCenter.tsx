import { useState } from 'react'
import { Activity, AlertTriangle, CheckCircle2, RefreshCw, ServerCog } from 'lucide-react'

import { formatDateTime, humanizeCode } from '../lib/format'
import type { DashboardData, ReadinessCounts } from '../types'

interface RefreshEntry { at: string; status: 'completed' | 'failed'; message: string }

export function OperationsCenter({ dashboard, onRefresh }: { dashboard: DashboardData; onRefresh: () => Promise<void> }) {
  const [refreshing, setRefreshing] = useState(false)
  const [history, setHistory] = useState<RefreshEntry[]>([])
  const resourceErrors = Object.entries(dashboard.resource_errors)
  const monitoring = dashboard.monitoring
  const alerts = monitoring?.alerts ?? []
  const failedImports = dashboard.imports.filter((job) => ['failed', 'rejected'].includes(job.status))
  const failedJobs = dashboard.jobs.filter((job) => ['failed', 'rejected'].includes(job.status))
  const blockers = resourceErrors.length + alerts.length + failedImports.length + failedJobs.length
  const readiness = dashboard.readiness
  const refresh = async () => {
    setRefreshing(true)
    try {
      await onRefresh()
      const entry: RefreshEntry = { at: new Date().toISOString(), status: 'completed', message: 'Dashboard resources synchronized.' }
      setHistory((current) => [entry, ...current].slice(0, 10))
    } catch (caught) {
      const entry: RefreshEntry = { at: new Date().toISOString(), status: 'failed', message: caught instanceof Error ? caught.message : 'Refresh failed' }
      setHistory((current) => [entry, ...current].slice(0, 10))
    } finally { setRefreshing(false) }
  }

  return <div className="space-y-7">
    <div className="flex items-end justify-between gap-6"><div><p className="text-xs font-bold uppercase text-emerald-700">Desktop operations</p><h2 className="mt-1 text-lg font-bold">System status center</h2><p className="mt-1 max-w-3xl text-sm leading-6 text-zinc-500">One fail-closed view of loaded API resources, collection monitoring, import failures, provider jobs, and research-pipeline readiness.</p></div><button className="inline-flex h-10 items-center gap-2 bg-zinc-900 px-4 text-sm font-bold text-white disabled:opacity-40" disabled={refreshing} onClick={() => void refresh()} type="button"><RefreshCw aria-hidden="true" className={refreshing ? 'animate-spin' : ''} size={16} />{refreshing ? 'Refreshing…' : 'Refresh all resources'}</button></div>
    <section className={`border-l-4 p-5 ${blockers ? 'border-rose-500 bg-rose-50' : 'border-emerald-500 bg-emerald-50'}`} role={blockers ? 'alert' : 'status'}><div className="flex items-start gap-3">{blockers ? <AlertTriangle aria-hidden="true" className="text-rose-700" size={22} /> : <CheckCircle2 aria-hidden="true" className="text-emerald-700" size={22} />}<div><h3 className="font-bold">{blockers ? `${blockers} operational item${blockers === 1 ? '' : 's'} require attention` : 'Loaded operational evidence is healthy'}</h3><p className="mt-1 text-sm text-zinc-700">Phase {humanizeCode(dashboard.status.phase)} · data mode {humanizeCode(dashboard.status.data_mode)} · automated betting {dashboard.status.automated_betting ? 'unexpectedly enabled' : 'disabled'}</p></div></div></section>
    <section className="grid grid-cols-5 border border-zinc-200 bg-white"><StatusMetric label="Resource errors" value={resourceErrors.length} warning={resourceErrors.length > 0} /><StatusMetric label="Collector alerts" value={alerts.length} warning={alerts.length > 0} /><StatusMetric label="Rejected imports" value={failedImports.length} warning={failedImports.length > 0} /><StatusMetric label="Failed jobs" value={failedJobs.length} warning={failedJobs.length > 0} /><StatusMetric label="Providers" value={dashboard.providers.length} /></section>
    <section><Heading icon={<Activity aria-hidden="true" size={17} />} title="Collection and provider health" />{monitoring ? <div className="border-y border-zinc-200 bg-white"><div className="grid grid-cols-[minmax(220px,1fr)_180px_140px_140px_2fr] bg-zinc-50 px-4 py-3 text-xs font-bold uppercase text-zinc-500"><span>Provider</span><span>Latest success</span><span>Completed streak</span><span>Recent failures</span><span>Blockers</span></div>{monitoring.providers.map((provider) => <div className="grid grid-cols-[minmax(220px,1fr)_180px_140px_140px_2fr] items-center border-t border-zinc-100 px-4 py-3 text-sm" key={provider.provider_id}><div><p className="font-bold">{provider.provider}</p><p className="text-xs text-zinc-500">{provider.provider_slug}</p></div><span className="text-xs">{provider.latest_success_at ? formatDateTime(provider.latest_success_at) : 'No success stored'}</span><span className="font-mono">{provider.consecutive_completed_jobs}</span><span className={`font-mono ${provider.failures_in_recent_window ? 'text-rose-700' : ''}`}>{provider.failures_in_recent_window}</span><span className="text-xs text-rose-800">{provider.blockers.length ? provider.blockers.map(humanizeCode).join(', ') : 'None'}</span></div>)}</div> : <Empty text="Collection monitoring is unavailable." />}{alerts.length ? <div className="mt-3 space-y-2">{alerts.map((alert, index) => <div className="border border-rose-200 bg-rose-50 p-3 text-sm text-rose-900" key={`${alert.code}-${index}`}><p className="font-bold">{humanizeCode(alert.code)}</p><p className="mt-1">{alert.detail}</p></div>)}</div> : null}</section>
    <section><Heading icon={<ServerCog aria-hidden="true" size={17} />} title="Research pipeline readiness" />{readiness ? <ReadinessGrid readiness={readiness} /> : <Empty text="Readiness counts are unavailable." />}</section>
    <section className="grid grid-cols-2 gap-6"><div><Heading title="Recent ingestion failures" />{failedImports.length ? <div className="border-y border-zinc-200 bg-white">{failedImports.slice(0, 8).map((job) => <div className="border-b border-zinc-100 p-3 last:border-0" key={job.id}><div className="flex justify-between"><p className="font-bold">#{job.id} · {job.filename}</p><span className="text-xs font-bold text-rose-700">{job.status.toUpperCase()}</span></div><p className="mt-1 text-xs text-zinc-500">{job.rows_imported}/{job.rows_received} rows · {job.errors.length} stored errors · {formatDateTime(job.created_at)}</p></div>)}</div> : <Empty text="No rejected or failed imports are loaded." />}</div><div><Heading title="Manual refresh history" />{history.length ? <div className="border-y border-zinc-200 bg-white">{history.map((entry, index) => <div className="flex items-start justify-between border-b border-zinc-100 p-3 text-sm last:border-0" key={`${entry.at}-${index}`}><div><p className="font-bold">{entry.message}</p><p className="mt-1 text-xs text-zinc-500">{formatDateTime(entry.at)}</p></div><span className={entry.status === 'completed' ? 'text-emerald-700' : 'text-rose-700'}>{entry.status.toUpperCase()}</span></div>)}</div> : <Empty text="No manual refreshes in this session." />}</div></section>
    <div className="border-l-4 border-sky-500 bg-sky-50 px-4 py-3 text-sm text-sky-950">This center reports loaded stored evidence. A green state does not prove upstream data completeness beyond the configured monitoring and coverage rules.</div>
  </div>
}

function ReadinessGrid({ readiness }: { readiness: ReadinessCounts }) { const entries: Array<[keyof ReadinessCounts, string]> = [['events', 'Events'], ['odds_snapshots', 'Odds snapshots'], ['final_results', 'Final results'], ['model_versions', 'Models'], ['predictions', 'Predictions'], ['non_demo_calibrated_evaluations', 'Calibrated evaluations'], ['signals', 'Signals'], ['signal_backtests', 'Backtests'], ['bookmaker_tax_mappings', 'Tax mappings'], ['bookmaker_constraints', 'Stake constraints'], ['intelligence_records', 'Intelligence records']]; return <div className="grid grid-cols-6 border border-zinc-200 bg-white">{entries.map(([key, label]) => <StatusMetric key={key} label={label} value={readiness[key]} warning={readiness[key] === 0} />)}</div> }
function StatusMetric({ label, value, warning = false }: { label: string; value: number; warning?: boolean }) { return <div className="border-r border-b border-zinc-200 p-4"><p className="text-[10px] font-bold uppercase text-zinc-500">{label}</p><p className={`mt-2 font-mono text-xl font-bold ${warning ? 'text-amber-700' : 'text-zinc-900'}`}>{value}</p></div> }
function Heading({ title, icon }: { title: string; icon?: React.ReactNode }) { return <div className="mb-3 flex items-center gap-2">{icon}<h3 className="font-bold">{title}</h3></div> }
function Empty({ text }: { text: string }) { return <div className="border-y border-zinc-200 bg-white px-4 py-8 text-center text-sm text-zinc-500">{text}</div> }
