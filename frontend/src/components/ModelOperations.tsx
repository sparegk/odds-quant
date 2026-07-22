import { useMemo, useState } from 'react'
import { AlertTriangle, CheckCircle2, Cog, LineChart, Sparkles, Target } from 'lucide-react'

import { evaluateModel, generateSignals, predictEvent, trainPoissonModel } from '../api/client'
import type { DashboardData, EvaluationRun, ModelOutput, ModelVersion, SignalBatch } from '../types'

type Operation = 'train' | 'evaluate' | 'predict' | 'signals'

export function ModelOperations({ dashboard }: { dashboard: DashboardData }) {
  const competitionOptions = useMemo(() => Array.from(new Map(dashboard.events.filter((event) => event.competition_id).map((event) => [event.competition_id as number, event.competition])).entries()), [dashboard.events])
  const [operation, setOperation] = useState<Operation>('train')
  const [adminKey, setAdminKey] = useState('')
  const [modelId, setModelId] = useState(String(dashboard.models[0]?.id ?? ''))
  const [eventId, setEventId] = useState(String(dashboard.events.find((event) => event.latest_odds_at)?.id ?? dashboard.events[0]?.id ?? ''))
  const [outputId, setOutputId] = useState('')
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  const [asOf, setAsOf] = useState('')
  const [competitionId, setCompetitionId] = useState(String(competitionOptions[0]?.[0] ?? ''))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<ModelVersion | EvaluationRun | ModelOutput | SignalBatch | null>(null)

  const execute = async () => {
    setBusy(true); setError(null); setResult(null)
    try {
      if (operation === 'train') {
        const created = await trainPoissonModel({ competition_id: Number(competitionId), training_start: iso(start), training_end: iso(end), minimum_matches: 20, minimum_team_matches: 3, shrinkage_matches: 5 }, adminKey || undefined)
        setModelId(String(created.id)); setResult(created)
      } else if (operation === 'evaluate') {
        setResult(await evaluateModel(Number(modelId), { evaluation_start: iso(start), evaluation_end: iso(end), prediction_lead_minutes: 60, minimum_training_matches: 20, calibration_bins: 10 }, adminKey || undefined))
      } else if (operation === 'predict') {
        const created = await predictEvent(Number(modelId), { event_id: Number(eventId), ...(asOf ? { predicted_at: iso(asOf), inputs_as_of: iso(asOf) } : {}) }, adminKey || undefined)
        setOutputId(String(created.id)); setResult(created)
      } else {
        setResult(await generateSignals({ output_id: Number(outputId), ...(asOf ? { generated_at: iso(asOf) } : {}) }, adminKey || undefined))
      }
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'Operation failed') } finally { setBusy(false) }
  }

  const ready = operation === 'train' ? Boolean(competitionId && start && end) : operation === 'evaluate' ? Boolean(modelId && start && end) : operation === 'predict' ? Boolean(modelId && eventId) : Boolean(outputId)
  return <section className="border border-zinc-200 bg-white"><div className="border-b border-zinc-200 p-5"><p className="text-xs font-bold uppercase text-emerald-700">Protected workflow</p><h2 className="mt-1 text-lg font-bold">Model operations</h2><p className="mt-1 text-sm text-zinc-500">Run each timestamped stage explicitly. A successful training or prediction carries its ID into the next stage.</p></div>
    <div className="flex overflow-x-auto border-b border-zinc-200">{([['train', Cog, '1. Train'], ['evaluate', LineChart, '2. Evaluate'], ['predict', Target, '3. Predict'], ['signals', Sparkles, '4. Signals']] as const).map(([key, Icon, label]) => <button key={key} className={`flex min-w-32 items-center justify-center gap-2 border-r border-zinc-200 px-4 py-3 text-sm font-bold ${operation === key ? 'bg-zinc-900 text-white' : 'hover:bg-zinc-50'}`} onClick={() => { setOperation(key); setError(null); setResult(null) }} type="button"><Icon aria-hidden="true" size={16} />{label}</button>)}</div>
    <div className="p-5"><div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {operation === 'train' ? <Select label="Competition" value={competitionId} onChange={setCompetitionId} options={competitionOptions.map(([id, name]) => [String(id), `${name} (#${id})`])} /> : null}
      {operation === 'evaluate' || operation === 'predict' ? <Select label="Model version" value={modelId} onChange={setModelId} options={dashboard.models.map((model) => [String(model.id), `${model.version} (#${model.id})`])} /> : null}
      {operation === 'predict' ? <Select label="Target event" value={eventId} onChange={setEventId} options={dashboard.events.map((event) => [String(event.id), `${event.home_team} vs ${event.away_team}`])} /> : null}
      {operation === 'signals' ? <Text label="Prediction output ID" value={outputId} onChange={setOutputId} type="number" /> : null}
      {operation === 'train' || operation === 'evaluate' ? <><Text label={operation === 'train' ? 'Training start' : 'Evaluation start'} value={start} onChange={setStart} type="datetime-local" /><Text label={operation === 'train' ? 'Training end' : 'Evaluation end'} value={end} onChange={setEnd} type="datetime-local" /></> : null}
      {operation === 'predict' || operation === 'signals' ? <Text label={operation === 'predict' ? 'Prediction/input cutoff (optional)' : 'Generated at (optional)'} value={asOf} onChange={setAsOf} type="datetime-local" /> : null}
      <Text label="Admin key (memory only)" value={adminKey} onChange={setAdminKey} type="password" />
    </div><div className="mt-5 flex flex-wrap items-center gap-3"><button className="rounded-[5px] bg-emerald-700 px-4 py-2 text-sm font-bold text-white disabled:opacity-40" disabled={!ready || busy} onClick={() => void execute()} type="button">{busy ? 'Running…' : operation === 'train' ? 'Train model' : operation === 'evaluate' ? 'Run evaluation' : operation === 'predict' ? 'Persist prediction' : 'Generate signals'}</button><p className="text-xs text-zinc-500">The backend rejects future cutoffs, leakage, inadequate samples, and missing calibration.</p></div>
    {result ? <Result operation={operation} result={result} /> : null}{error ? <div className="mt-4 flex gap-2 border border-rose-200 bg-rose-50 p-3 text-sm text-rose-900" role="alert"><AlertTriangle aria-hidden="true" className="shrink-0" size={18} />{error}</div> : null}</div>
  </section>
}

function Result({ operation, result }: { operation: Operation; result: ModelVersion | EvaluationRun | ModelOutput | SignalBatch }) {
  const id = 'signals' in result ? result.output_id : result.id
  const status = 'signals' in result ? `${result.signals.length} classifications` : 'evidence_class' in result ? result.evidence_class : result.evaluation_status
  return <div className="mt-4 flex gap-2 border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900" role="status"><CheckCircle2 aria-hidden="true" size={18} /><div><p className="font-bold">{operation} completed - #{id}</p><p className="text-xs">{status}. Refresh dashboard data to update all registry views.</p></div></div>
}
function Select({ label, value, options, onChange }: { label: string; value: string; options: string[][]; onChange: (value: string) => void }) { return <label><span className="mb-1.5 block text-xs font-semibold uppercase text-zinc-500">{label}</span><select aria-label={label} className="h-10 w-full border border-zinc-300 bg-white px-3 text-sm" value={value} onChange={(event) => onChange(event.target.value)}><option disabled value="">Select</option>{options.map(([key, text]) => <option key={key} value={key}>{text}</option>)}</select></label> }
function Text({ label, value, onChange, type }: { label: string; value: string; onChange: (value: string) => void; type: string }) { return <label><span className="mb-1.5 block text-xs font-semibold uppercase text-zinc-500">{label}</span><input aria-label={label} autoComplete="off" className="h-10 w-full border border-zinc-300 px-3 text-sm" type={type} value={value} onChange={(event) => onChange(event.target.value)} /></label> }
function iso(value: string): string { return new Date(value).toISOString() }
