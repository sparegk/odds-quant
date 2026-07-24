import { useState } from 'react'
import { AlertTriangle, CheckCircle2, Database, Download, Upload } from 'lucide-react'

import { uploadCsv } from '../api/client'
import { formatDateTime, humanizeCode } from '../lib/format'
import type { CollectionMonitoring, DashboardData, ImportUploadResult } from '../types'
import { DataCoverageAudit } from './DataCoverageAudit'
import { IntelligenceBundleImport } from './IntelligenceBundleImport'

type UploadKind = 'odds' | 'results' | 'availability'

export function DataOperations({ dashboard, onChanged }: { dashboard: DashboardData; onChanged?: () => Promise<void> | void }) {
  const [adminKey, setAdminKey] = useState('')
  const [coverageVersion, setCoverageVersion] = useState(0)
  const handleChanged = async () => {
    setCoverageVersion((version) => version + 1)
    await onChanged?.()
  }
  return <div className="space-y-8">
    <div><p className="text-xs font-bold uppercase text-emerald-700">Atomic ingestion</p><h2 className="mt-1 text-lg font-bold">Data operations</h2><p className="mt-1 max-w-3xl text-sm leading-6 text-zinc-500">Upload complete timestamped CSV feeds. Any identity, completeness, chronology, settlement, or publication-time failure rejects the entire file.</p></div>
    <section className="border border-zinc-200 bg-white p-5"><label className="block max-w-md"><span className="mb-1.5 block text-xs font-semibold uppercase text-zinc-500">Admin key (memory only)</span><input aria-label="Import admin key" autoComplete="off" className="h-10 w-full border border-zinc-300 px-3 text-sm" type="password" value={adminKey} onChange={(event) => setAdminKey(event.target.value)} /></label><p className="mt-2 text-xs text-zinc-500">Sent only with upload requests and never persisted. Local development may leave it blank.</p><div className="mt-4 flex flex-wrap gap-2"><TemplateLink href="/templates/results.csv" label="Results CSV template" /><TemplateLink href="/templates/odds.csv" label="Odds CSV template" /></div><p className="mt-2 text-xs text-zinc-500">Templates contain headers only. Add permitted source records without changing column names.</p></section>
    <DataCoverageAudit refreshVersion={coverageVersion} />
    <CollectionMonitoringPanel monitoring={dashboard.monitoring ?? null} />
    <section className="grid gap-5 xl:grid-cols-3"><ImportPanel adminKey={adminKey} kind="odds" title="Odds snapshots" detail="Complete coherent bookmaker markets with event, settlement, price, and observed-at identity." onChanged={handleChanged} /><ImportPanel adminKey={adminKey} kind="results" title="Historical results" detail="Final scores observed no earlier than settlement; later corrections append rather than overwrite." onChanged={handleChanged} /><ImportPanel adminKey={adminKey} kind="availability" title="Player availability" detail="Timestamped availability evidence with original publication and observation times." onChanged={handleChanged} /></section>
    <IntelligenceBundleImport adminKey={adminKey} onChanged={handleChanged} />
    <section><Heading eyebrow="Sources" title="Provider status" />{dashboard.providers.length ? <div className="overflow-x-auto border-y border-zinc-200 bg-white"><table className="w-full min-w-[700px] text-left text-sm"><thead className="bg-zinc-50 text-xs uppercase text-zinc-500"><tr><th className="px-4 py-3">Provider</th><th className="px-4 py-3">Kind</th><th className="px-4 py-3 text-right">Events</th><th className="px-4 py-3 text-right">Snapshots</th><th className="px-4 py-3">Classification</th></tr></thead><tbody>{dashboard.providers.map((provider) => <tr key={provider.id} className="border-t border-zinc-100"><td className="px-4 py-3"><p className="font-semibold">{provider.name}</p><p className="text-xs text-zinc-500">{provider.slug}</p></td><td className="px-4 py-3">{humanizeCode(provider.kind)}</td><td className="px-4 py-3 text-right font-mono">{provider.event_count}</td><td className="px-4 py-3 text-right font-mono">{provider.snapshot_count}</td><td className="px-4 py-3"><Badge status={provider.is_demo ? 'demo' : 'external'} /></td></tr>)}</tbody></table></div> : <Empty text="No providers registered." />}</section>
    <section className="grid gap-7 xl:grid-cols-2"><div><Heading eyebrow="Ingestion" title="Recent import jobs" />{dashboard.imports.length ? <div className="border-y border-zinc-200 bg-white">{dashboard.imports.map((job) => <details key={job.id} className="border-b border-zinc-100 px-4 py-3 last:border-0"><summary className="cursor-pointer list-none"><div className="flex items-start justify-between gap-3"><div><p className="text-sm font-semibold">#{job.id} · {job.filename}</p><p className="mt-1 text-xs text-zinc-500">{job.rows_imported}/{job.rows_received} rows · {formatDateTime(job.created_at)}</p></div><Badge status={job.status} /></div></summary>{job.errors.length ? <div className="mt-3 border-t border-zinc-100 pt-3"><p className="mb-2 text-xs font-bold uppercase text-rose-700">Rejection details</p>{job.errors.map((error, index) => <pre key={index} className="mt-2 overflow-x-auto whitespace-pre-wrap bg-rose-50 p-3 text-xs text-rose-900">{JSON.stringify(error, null, 2)}</pre>)}</div> : <p className="mt-3 border-t border-zinc-100 pt-3 text-xs text-zinc-500">No row errors recorded.</p>}</details>)}</div> : <Empty text="No import jobs recorded." />}</div><div><Heading eyebrow="Scheduler" title="Provider jobs" />{dashboard.jobs.length ? <div className="border-y border-zinc-200 bg-white">{dashboard.jobs.map((job) => <div key={job.id} className="flex items-start justify-between gap-3 border-b border-zinc-100 px-4 py-3 last:border-0"><div><p className="text-sm font-semibold">{job.provider} · {humanizeCode(job.job_type)}</p><p className="mt-1 text-xs text-zinc-500">{job.message || 'No provider message'} · {formatDateTime(job.created_at)}</p>{job.finished_at ? <p className="mt-1 text-xs text-zinc-400">Finished {formatDateTime(job.finished_at)}</p> : null}</div><Badge status={job.status} /></div>)}</div> : <Empty text="No provider jobs recorded." />}</div></section>
    <div className="flex gap-3 border-l-4 border-sky-500 bg-sky-50 px-4 py-3 text-sm leading-6 text-sky-950"><Database aria-hidden="true" className="mt-0.5 shrink-0" size={18} />Uploads are research ingestion only. Production requires the configured administrative key and provider terms must permit the submitted data.</div>
  </div>
}

function CollectionMonitoringPanel({ monitoring }: { monitoring: CollectionMonitoring | null }) {
  if (!monitoring) {
    return <section><Heading eyebrow="Scheduler" title="Collection monitoring" /><Empty text="Collection monitoring is unavailable." /></section>
  }
  const healthy = monitoring.healthy && monitoring.alerts.length === 0
  return <section>
    <Heading eyebrow="Scheduler" title="Collection monitoring" />
    <div className={`border-l-4 px-5 py-4 ${healthy ? 'border-emerald-500 bg-emerald-50' : 'border-rose-500 bg-rose-50'}`} role={healthy ? 'status' : 'alert'}>
      <div className="flex items-start gap-3">
        {healthy ? <CheckCircle2 aria-hidden="true" className="mt-0.5 shrink-0 text-emerald-700" size={20} /> : <AlertTriangle aria-hidden="true" className="mt-0.5 shrink-0 text-rose-700" size={20} />}
        <div className="min-w-0 flex-1">
          <h3 className={`font-bold ${healthy ? 'text-emerald-950' : 'text-rose-950'}`}>{healthy ? 'Collection healthy' : 'Collection attention required'}</h3>
          <p className="mt-1 text-xs text-zinc-600">Observed {formatDateTime(monitoring.observed_at)} / target cadence {Math.round(monitoring.expected_poll_seconds / 60)} minutes / {monitoring.alerts.length} alerts</p>
        </div>
      </div>
    </div>
    <div className="mt-3 grid gap-3 lg:grid-cols-2">
      {monitoring.providers.map((provider) => <article className="border border-zinc-200 bg-white p-4" key={provider.provider_id}>
        <div className="flex items-start justify-between gap-3">
          <div><p className="font-semibold">{provider.provider}</p><p className="mt-1 text-xs text-zinc-500">{provider.provider_slug}</p></div>
          <Badge status={provider.healthy ? 'completed' : 'failed'} />
        </div>
        <dl className="mt-4 grid grid-cols-2 gap-3 text-xs">
          <div><dt className="font-semibold uppercase text-zinc-500">Latest success</dt><dd className="mt-1 text-zinc-700">{provider.latest_success_at ? formatDateTime(provider.latest_success_at) : 'None'}</dd></div>
          <div><dt className="font-semibold uppercase text-zinc-500">Latest job</dt><dd className="mt-1 text-zinc-700">{provider.latest_job_id ? `#${provider.latest_job_id} / ${humanizeCode(provider.latest_job_status ?? 'unknown')}` : 'None'}</dd></div>
          <div><dt className="font-semibold uppercase text-zinc-500">Completed streak</dt><dd className="mt-1 font-mono text-zinc-700">{provider.consecutive_completed_jobs}</dd></div>
          <div><dt className="font-semibold uppercase text-zinc-500">Recent failures</dt><dd className="mt-1 font-mono text-zinc-700">{provider.failures_in_recent_window}</dd></div>
        </dl>
        {provider.blockers.length ? <div className="mt-3 text-xs text-rose-800">{provider.blockers.map((blocker) => <p key={blocker}>{humanizeCode(blocker)}</p>)}</div> : null}
      </article>)}
    </div>
    {monitoring.alerts.length ? <div className="mt-3 space-y-2" role="list" aria-label="Collection alerts">{monitoring.alerts.map((alert, index) => <article className="border border-rose-200 bg-white p-4 text-sm" key={`${alert.code}-${alert.provider_slug}-${alert.competition ?? 'all'}-${alert.bookmaker ?? 'all'}-${index}`} role="listitem">
      <div className="flex flex-wrap items-center justify-between gap-2"><p className="font-bold text-rose-900">{humanizeCode(alert.code)}</p><Badge status={alert.severity} /></div>
      <p className="mt-2 text-zinc-700">{alert.detail}</p>
      <p className="mt-1 text-xs text-zinc-500">{[alert.provider_slug, alert.competition, alert.bookmaker].filter(Boolean).join(' / ')}</p>
    </article>)}</div> : <p className="mt-3 text-xs text-zinc-500">No collection alerts detected.</p>}
  </section>
}

function ImportPanel({ adminKey, kind, title, detail, onChanged }: { adminKey: string; kind: UploadKind; title: string; detail: string; onChanged?: () => Promise<void> | void }) {
  const [file, setFile] = useState<File | null>(null); const [sourceKey, setSourceKey] = useState(''); const [providerSlug, setProviderSlug] = useState(''); const [providerName, setProviderName] = useState(''); const [result, setResult] = useState<ImportUploadResult | null>(null); const [error, setError] = useState<string | null>(null); const [submitting, setSubmitting] = useState(false)
  const submit = async () => { if (!file) return; setSubmitting(true); setError(null); setResult(null); try { setResult(await uploadCsv(kind, file, { adminKey: adminKey || undefined, sourceKey, providerSlug, providerName })); await onChanged?.() } catch (caught) { setError(caught instanceof Error ? caught.message : 'Upload failed') } finally { setSubmitting(false) } }
  const availabilityReady = kind !== 'availability' || Boolean(sourceKey && providerSlug && providerName)
  return <article className="border border-zinc-200 bg-white p-5"><Upload aria-hidden="true" className="text-emerald-700" size={22} /><h3 className="mt-3 font-bold">{title}</h3><p className="mt-1 min-h-16 text-sm leading-6 text-zinc-500">{detail}</p><label className="mt-4 block"><span className="mb-1.5 block text-xs font-semibold uppercase text-zinc-500">CSV file</span><input accept=".csv,text/csv" aria-label={`${title} CSV file`} className="block w-full text-xs" type="file" onChange={(event) => setFile(event.target.files?.[0] ?? null)} /></label>{kind === 'availability' ? <div className="mt-4 grid gap-3"><TextInput label="Source key" value={sourceKey} onChange={setSourceKey} /><TextInput label="Provider slug" value={providerSlug} onChange={setProviderSlug} /><TextInput label="Provider name" value={providerName} onChange={setProviderName} /></div> : null}<button className="mt-5 rounded-[5px] bg-zinc-900 px-4 py-2 text-sm font-bold text-white disabled:opacity-40" disabled={!file || !availabilityReady || submitting} onClick={() => void submit()} type="button">{submitting ? 'Uploading…' : `Import ${kind}`}</button>{result ? <div className="mt-4 flex gap-2 border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900" role="status"><CheckCircle2 aria-hidden="true" className="shrink-0" size={18} /><div><p className="font-bold">Job #{result.job_id} {result.status}</p><p className="text-xs">{result.rows_imported}/{result.rows_received} rows imported atomically.</p></div></div> : null}{error ? <div className="mt-4 flex gap-2 border border-rose-200 bg-rose-50 p-3 text-sm text-rose-900" role="alert"><AlertTriangle aria-hidden="true" className="shrink-0" size={18} /><span>{error}</span></div> : null}</article>
}

function TextInput({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) { return <label><span className="mb-1 block text-xs font-semibold uppercase text-zinc-500">{label}</span><input aria-label={label} className="h-9 w-full border border-zinc-300 px-3 text-sm" value={value} onChange={(event) => onChange(event.target.value)} /></label> }
function TemplateLink({ href, label }: { href: string; label: string }) { return <a className="inline-flex items-center gap-2 rounded-[5px] border border-zinc-300 px-3 py-2 text-xs font-bold text-zinc-700 hover:border-zinc-500" download href={href}><Download aria-hidden="true" size={15} />{label}</a> }
function Heading({ eyebrow, title }: { eyebrow: string; title: string }) { return <div className="mb-3"><p className="text-xs font-bold uppercase text-emerald-700">{eyebrow}</p><h3 className="mt-1 text-lg font-bold">{title}</h3></div> }
function Badge({ status }: { status: string }) { const good = ['completed', 'external'].includes(status); const bad = ['failed', 'rejected', 'critical'].includes(status); return <span className={`rounded-[4px] border px-2 py-1 text-xs font-bold ${good ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : bad ? 'border-rose-200 bg-rose-50 text-rose-800' : 'border-amber-200 bg-amber-50 text-amber-800'}`}>{status.toUpperCase()}</span> }
function Empty({ text }: { text: string }) { return <div className="border-y border-zinc-200 bg-white px-4 py-8 text-center text-sm text-zinc-500">{text}</div> }
