import { useMemo, useState } from 'react'
import { AlertTriangle, LineChart } from 'lucide-react'

import { formatDateTime, humanizeCode } from '../lib/format'
import type { DashboardData, EvaluationRun } from '../types'
import { ModelOperations } from './ModelOperations'

export function ModelPerformance({ dashboard }: { dashboard: DashboardData }) {
  const [selectedId, setSelectedId] = useState<number | null>(dashboard.models[0]?.id ?? null)
  const selected = dashboard.models.find((model) => model.id === selectedId) ?? dashboard.models[0]
  const evaluations = useMemo(() => selected ? dashboard.evaluations.filter((run) => run.model_version_id === selected.id) : [], [dashboard.evaluations, selected])
  const latest = evaluations[0]

  if (!selected) return <div className="space-y-5"><ModelOperations dashboard={dashboard} /><ModelEmpty title="No trained model versions" detail="Import timestamped historical results and train the Poisson baseline to populate this registry." /><EvidenceWarning /></div>

  return <div className="space-y-7">
    <ModelOperations dashboard={dashboard} />
    <div><p className="text-xs font-bold uppercase text-emerald-700">Versioned evidence registry</p><h2 className="mt-1 text-lg font-bold">Model performance and audit</h2><p className="mt-1 max-w-2xl text-sm leading-6 text-zinc-500">Compare immutable training versions with their own chronological evaluation evidence. Training fit is never shown as validation.</p></div>
    <div className="grid gap-6 xl:grid-cols-[300px_minmax(0,1fr)]">
      <aside><h3 className="mb-3 text-xs font-bold uppercase text-zinc-500">Model versions</h3><div className="border-y border-zinc-200 bg-white">{dashboard.models.map((model) => <button key={model.id} className={`w-full border-b border-zinc-100 p-4 text-left last:border-0 ${selected.id === model.id ? 'bg-emerald-50' : 'hover:bg-zinc-50'}`} onClick={() => setSelectedId(model.id)} type="button"><div className="flex items-start justify-between gap-2"><div><p className="font-bold">{model.version}</p><p className="mt-1 text-xs text-zinc-500">{model.kind} · {model.sample_size} matches</p></div><Status status={model.evaluation_status} /></div></button>)}</div></aside>
      <div className="space-y-7">
        <section className="border border-zinc-200 bg-white"><div className="flex flex-wrap items-start justify-between gap-4 p-5"><div><p className="text-xs font-bold uppercase text-emerald-700">{selected.name}</p><h3 className="mt-1 text-xl font-bold">{selected.version}</h3><p className="mt-1 text-sm text-zinc-500">{selected.is_demo ? 'DEMO TRAINING DATA' : 'PERMITTED EXTERNAL HISTORY'}</p></div><Status status={selected.evaluation_status} /></div><div className="grid grid-cols-2 border-t border-zinc-200 md:grid-cols-4"><Metric label="Training matches" value={selected.sample_size.toString()} /><Metric label="Feature version" value={selected.feature_version} /><Metric label="Evaluations" value={evaluations.length.toString()} /><Metric label="Registry status" value={humanizeCode(selected.status)} /></div><div className="grid gap-2 border-t border-zinc-200 px-5 py-4 text-xs text-zinc-500 sm:grid-cols-2"><p>Training window: {formatDateTime(selected.training_start)} to {formatDateTime(selected.training_end)}</p><p>Created: {formatDateTime(selected.created_at)}</p><p className="font-mono">Data fingerprint: {selected.data_fingerprint}</p><p>Model ID #{selected.id}</p></div></section>
        <EvaluationSummary run={latest} />
        <Calibration run={latest} />
        <section><Heading eyebrow="Immutable history" title="Evaluation runs" />{evaluations.length ? <div className="overflow-x-auto border-y border-zinc-200 bg-white"><table className="w-full min-w-[760px] text-left text-sm"><thead className="bg-zinc-50 text-xs uppercase text-zinc-500"><tr><th className="px-4 py-3">Window end</th><th className="px-4 py-3">Evidence</th><th className="px-4 py-3 text-right">Matches</th><th className="px-4 py-3 text-right">Brier</th><th className="px-4 py-3 text-right">Log loss</th><th className="px-4 py-3">Status</th><th className="px-4 py-3">Fingerprint</th></tr></thead><tbody>{evaluations.map((run) => <tr key={run.id} className="border-t border-zinc-100"><td className="px-4 py-3">{formatDateTime(run.evaluation_end)}</td><td className="px-4 py-3">{run.is_demo ? 'DEMO ONLY' : 'EXTERNAL HISTORY'}</td><td className="px-4 py-3 text-right font-mono">{numberMetric(run, 'evaluated_events', 0)}</td><td className="px-4 py-3 text-right font-mono">{score(run, 'brier_score')}</td><td className="px-4 py-3 text-right font-mono">{score(run, 'log_loss')}</td><td className="px-4 py-3"><Status status={run.evaluation_status} /></td><td className="px-4 py-3 font-mono text-xs">{run.fingerprint.slice(0, 12)}</td></tr>)}</tbody></table></div> : <ModelEmpty title="No linked chronological evaluations" detail="Evaluate this exact model version with expanding-window cutoffs before interpreting its forecasts." />}</section>
      </div>
    </div>
    <EvidenceWarning />
  </div>
}

function EvaluationSummary({ run }: { run: EvaluationRun | undefined }) {
  if (!run) return <ModelEmpty title="Performance is not established" detail="This trained version has no chronological held-out evaluation. It cannot unlock calibrated value signals." />
  const brier = value(run, 'brier_score'); const uniform = benchmark(run, 'uniform', 'brier_score'); const market = benchmark(run, 'market_consensus', 'brier_score')
  return <section><Heading eyebrow="Latest chronological replay" title="Proper-score performance" /><div className="grid grid-cols-2 border border-zinc-200 bg-white md:grid-cols-4"><Metric label="1X2 Brier" value={format(brier)} /><Metric label="Log loss" value={score(run, 'log_loss')} /><Metric label="Calibration error" value={percent(value(run, 'expected_calibration_error'))} /><Metric label="Coverage" value={`${numberMetric(run, 'evaluated_events', 0)} / ${numberMetric(run, 'candidate_events', 0)}`} /></div><div className="mt-4 grid gap-4 md:grid-cols-2"><Benchmark label="Uniform benchmark" model={brier} benchmark={uniform} missing="Uniform score unavailable" /><Benchmark label="Market consensus" model={brier} benchmark={market} missing="No compatible historical closing prices" /></div></section>
}

function Calibration({ run }: { run: EvaluationRun | undefined }) {
  if (!run?.calibration.length) return null
  return <section><Heading eyebrow="Reliability" title="Calibration buckets" /><div className="border-y border-zinc-200 bg-white p-5"><div className="space-y-4">{run.calibration.map((bucket) => <div key={`${bucket.selection_code}-${bucket.bucket_index}`} className="grid gap-2 sm:grid-cols-[120px_1fr_150px]"><div><p className="text-sm font-semibold">{humanizeCode(bucket.selection_code)}</p><p className="text-xs text-zinc-500">{(bucket.lower_bound * 100).toFixed(0)}–{(bucket.upper_bound * 100).toFixed(0)}% · n={bucket.count}</p></div><div className="relative h-3 self-center bg-zinc-100"><div className="absolute inset-y-0 left-0 bg-emerald-500" style={{ width: `${Math.min(100, bucket.mean_predicted * 100)}%` }} /><span className="absolute inset-y-[-3px] w-0.5 bg-zinc-900" style={{ left: `${Math.min(100, bucket.observed_frequency * 100)}%` }} /></div><p className="text-xs text-zinc-500 sm:text-right">Forecast {(bucket.mean_predicted * 100).toFixed(1)}% · observed {(bucket.observed_frequency * 100).toFixed(1)}%</p></div>)}</div><p className="mt-4 text-xs text-zinc-500">Green bar: mean forecast. Black marker: observed frequency. Buckets are one-vs-rest and retain their original sample counts.</p></div></section>
}

function Benchmark({ label, model, benchmark: comparison, missing }: { label: string; model: number | null; benchmark: number | null; missing: string }) { const beats = model !== null && comparison !== null && model < comparison; return <div className="border border-zinc-200 bg-white p-4"><div className="flex items-center justify-between gap-2"><p className="text-sm font-bold">{label}</p><span className={`rounded-[4px] border px-2 py-1 text-xs font-bold ${beats ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-amber-200 bg-amber-50 text-amber-800'}`}>{comparison === null ? 'MISSING' : beats ? 'BEAT' : 'NOT BEATEN'}</span></div><p className="mt-2 text-sm text-zinc-500">{comparison === null ? missing : `Model ${format(model)} vs benchmark ${format(comparison)}`}</p></div> }
function EvidenceWarning() { return <div className="flex gap-3 border-l-4 border-amber-400 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-950"><AlertTriangle aria-hidden="true" className="mt-0.5 shrink-0" size={18} />A trained baseline or demo evaluation is software evidence only. Promotion requires adequate non-demo chronological history and the fixed evidence policy.</div> }
function Status({ status }: { status: string }) { const ready = status === 'calibrated'; return <span className={`rounded-[4px] border px-2 py-1 text-xs font-bold ${ready ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-amber-200 bg-amber-50 text-amber-800'}`}>{humanizeCode(status)}</span> }
function Heading({ eyebrow, title }: { eyebrow: string; title: string }) { return <div className="mb-3"><p className="text-xs font-bold uppercase text-emerald-700">{eyebrow}</p><h3 className="mt-1 text-lg font-bold">{title}</h3></div> }
function Metric({ label, value: text }: { label: string; value: string }) { return <div className="min-w-0 border-r border-b border-zinc-200 p-4"><p className="text-xs font-semibold uppercase text-zinc-500">{label}</p><p className="mt-2 truncate font-mono text-lg font-bold" title={text}>{text}</p></div> }
function ModelEmpty({ title, detail }: { title: string; detail: string }) { return <div className="border-y border-zinc-200 bg-white px-6 py-10 text-center"><LineChart aria-hidden="true" className="mx-auto text-zinc-400" size={26} /><h3 className="mt-3 font-bold">{title}</h3><p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-zinc-500">{detail}</p></div> }
function value(run: EvaluationRun, key: string): number | null { const item = run.metrics[key]; return typeof item === 'number' && Number.isFinite(item) ? item : null }
function numberMetric(run: EvaluationRun, key: string, fallback: number): number { return value(run, key) ?? fallback }
function benchmark(run: EvaluationRun, name: string, key: string): number | null { const item = run.benchmarks[name]?.[key]; return typeof item === 'number' && Number.isFinite(item) ? item : null }
function format(item: number | null): string { return item === null ? '—' : item.toFixed(4) }
function score(run: EvaluationRun, key: string): string { return format(value(run, key)) }
function percent(item: number | null): string { return item === null ? '—' : `${(item * 100).toFixed(1)}%` }
