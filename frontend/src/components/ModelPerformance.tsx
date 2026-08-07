import { useMemo } from 'react'
import { AlertTriangle, LineChart } from 'lucide-react'

import { formatDateTime, humanizeCode } from '../lib/format'
import { useResearchPreference } from '../lib/researchPreferences'
import type { DashboardData, EvaluationRun } from '../types'
import { ModelOperations } from './ModelOperations'

export function ModelPerformance({ dashboard, onChanged }: { dashboard: DashboardData; onChanged?: () => Promise<void> | void }) {
  const [selectedPreference, setSelectedPreference] = useResearchPreference('model_version', dashboard.models[0] ? String(dashboard.models[0].id) : '', (value) => value === '' || /^\d+$/.test(value))
  const selectedId = selectedPreference ? Number(selectedPreference) : null
  const setSelectedId = (id: number | null) => setSelectedPreference(id === null ? '' : String(id))
  const selected = dashboard.models.find((model) => model.id === selectedId) ?? dashboard.models[0]
  const evaluations = useMemo(() => selected ? dashboard.evaluations.filter((run) => run.model_version_id === selected.id) : [], [dashboard.evaluations, selected])
  const latest = evaluations[0]

  if (!selected) return <div className="space-y-5"><ModelOperations dashboard={dashboard} onChanged={onChanged} /><ModelEmpty title="No trained model versions" detail="Import timestamped historical results and train the Poisson baseline to populate this registry." /><EvidenceWarning /></div>

  return <div className="min-w-0 space-y-7">
    <ModelOperations dashboard={dashboard} onChanged={onChanged} />
    <div><p className="text-xs font-bold uppercase text-emerald-700">Versioned evidence registry</p><h2 className="mt-1 text-lg font-bold">Model performance and audit</h2><p className="mt-1 max-w-2xl text-sm leading-6 text-zinc-500">Compare immutable training versions with their own chronological evaluation evidence. Training fit is never shown as validation.</p></div>
    <div className="grid min-w-0 gap-6 xl:grid-cols-[300px_minmax(0,1fr)]">
      <aside><h3 className="mb-3 text-xs font-bold uppercase text-zinc-500">Model versions</h3><div className="border-y border-zinc-200 bg-white">{dashboard.models.map((model) => <button key={model.id} className={`w-full border-b border-zinc-100 p-4 text-left last:border-0 ${selected.id === model.id ? 'bg-emerald-50' : 'hover:bg-zinc-50'}`} onClick={() => setSelectedId(model.id)} type="button"><div className="flex items-start justify-between gap-2"><div><p className="font-bold">{model.version}</p><p className="mt-1 text-xs text-zinc-500">{model.kind} · {model.sample_size} matches</p></div><ValidationStatuses probability={model.probability_evaluation_status} market={model.evaluation_status} /></div></button>)}</div></aside>
      <div className="min-w-0 space-y-7">
        <section className="border border-zinc-200 bg-white"><div className="flex flex-wrap items-start justify-between gap-4 p-5"><div><p className="text-xs font-bold uppercase text-emerald-700">{selected.name}</p><h3 className="mt-1 text-xl font-bold">{selected.version}</h3><p className="mt-1 text-sm text-zinc-500">{selected.is_demo ? 'DEMO TRAINING DATA' : 'PERMITTED EXTERNAL HISTORY'}</p></div><ValidationStatuses probability={selected.probability_evaluation_status} market={selected.evaluation_status} /></div><div className="grid grid-cols-2 border-t border-zinc-200 md:grid-cols-4"><Metric label="Training matches" value={selected.sample_size.toString()} /><Metric label="Feature version" value={selected.feature_version} /><Metric label="Evaluations" value={evaluations.length.toString()} /><Metric label="Registry status" value={humanizeCode(selected.status)} /></div><div className="grid gap-2 border-t border-zinc-200 px-5 py-4 text-xs text-zinc-500 sm:grid-cols-2"><p>Training window: {formatDateTime(selected.training_start)} to {formatDateTime(selected.training_end)}</p><p>Created: {formatDateTime(selected.created_at)}</p><p className="font-mono">Data fingerprint: {selected.data_fingerprint}</p><p>Model ID #{selected.id}</p></div></section>
        <EvaluationSummary run={latest} />
        <ExternalValidationEvidence run={latest} />
        <ExperimentComparison anchor={latest} evaluations={dashboard.evaluations} />
        <PromotionReadiness run={latest} />
        <EvaluationDiagnosis run={latest} />
        <Calibration run={latest} />
        <section><Heading eyebrow="Immutable history" title="Evaluation runs" />{evaluations.length ? <div className="overflow-x-auto border-y border-zinc-200 bg-white"><table className="w-full min-w-[900px] text-left text-sm"><thead className="bg-zinc-50 text-xs uppercase text-zinc-500"><tr><th className="px-4 py-3">Window end</th><th className="px-4 py-3">Evidence</th><th className="px-4 py-3 text-right">Matches</th><th className="px-4 py-3 text-right">Brier</th><th className="px-4 py-3 text-right">Log loss</th><th className="px-4 py-3">Probability</th><th className="px-4 py-3">Market / value</th><th className="px-4 py-3">Fingerprint</th></tr></thead><tbody>{evaluations.map((run) => <tr key={run.id} className="border-t border-zinc-100"><td className="px-4 py-3">{formatDateTime(run.evaluation_end)}</td><td className="px-4 py-3">{run.is_demo ? 'DEMO ONLY' : 'EXTERNAL HISTORY'}</td><td className="px-4 py-3 text-right font-mono">{numberMetric(run, 'evaluated_events', 0)}</td><td className="px-4 py-3 text-right font-mono">{score(run, 'brier_score')}</td><td className="px-4 py-3 text-right font-mono">{score(run, 'log_loss')}</td><td className="px-4 py-3"><Status status={run.probability_evaluation_status} /></td><td className="px-4 py-3"><Status status={run.evaluation_status} /></td><td className="px-4 py-3 font-mono text-xs">{run.fingerprint.slice(0, 12)}</td></tr>)}</tbody></table></div> : <ModelEmpty title="No linked chronological evaluations" detail="Evaluate this exact model version with expanding-window cutoffs before interpreting its forecasts." />}</section>
      </div>
    </div>
    <EvidenceWarning />
  </div>
}

function EvaluationSummary({ run }: { run: EvaluationRun | undefined }) {
  if (!run) return <ModelEmpty title="Performance is not established" detail="This trained version has no chronological held-out evaluation. It cannot unlock calibrated value signals." />
  return <section><Heading eyebrow="Latest chronological replay" title="Proper-score performance" /><div className="grid grid-cols-2 border border-zinc-200 bg-white md:grid-cols-4"><Metric label="1X2 Brier" value={formatScoreInterval(run.metrics, 'brier_score')} /><Metric label="Log loss" value={formatScoreInterval(run.metrics, 'log_loss')} /><Metric label="Calibration error" value={percent(value(run, 'expected_calibration_error'))} /><Metric label="Coverage" value={`${numberMetric(run, 'evaluated_events', 0)} / ${numberMetric(run, 'candidate_events', 0)}`} /></div><BenchmarkComparison run={run} /></section>
}

function ExternalValidationEvidence({ run }: { run: EvaluationRun | undefined }) {
  const receipt = run?.external_validation
  if (!receipt) return null
  const passed = receipt.probability_decision === 'probability_validated'
  return <section aria-labelledby={'external-validation-title'}>
    <Heading eyebrow={'Pre-registered external holdout'} title={'External validation receipt'} />
    <div className={`border-l-4 p-5 ${passed ? 'border-emerald-500 bg-emerald-50' : 'border-amber-400 bg-amber-50'}`}>
      <div className={'flex flex-wrap items-start justify-between gap-4'}>
        <div><h4 className={'font-bold'} id={'external-validation-title'}>{receipt.display_name}</h4><p className={'mt-1 text-xs text-zinc-600'}>{humanizeCode(receipt.evidence_role)} · {receipt.experiment_id}</p></div>
        <span className={'border border-black/10 bg-white px-2 py-1 text-xs font-bold'}>{receipt.examined ? 'EXAMINED' : 'LOCKED'} · {humanizeCode(receipt.probability_decision).toUpperCase()}</span>
      </div>
      <div className={'mt-4 grid gap-2 text-xs sm:grid-cols-2 lg:grid-cols-4'}>
        <p><span className={'font-bold'}>Specification frozen</span><br />{formatDateTime(receipt.specification_frozen_at)}</p>
        <p><span className={'font-bold'}>Replay executed</span><br />{formatDateTime(receipt.executed_at)}</p>
        <p><span className={'font-bold'}>Retuning</span><br />{receipt.retuning_permitted ? 'Permitted' : 'Not permitted'}</p>
        <p><span className={'font-bold'}>Market validation</span><br />{receipt.market_validation_authorized ? 'Authorized' : 'Not authorized'}</p>
      </div>
      <p className={'mt-4 break-all font-mono text-xs text-zinc-600'}>Evaluation fingerprint: {receipt.evaluation_fingerprint}</p>
      <p className={'mt-3 text-xs leading-5 text-zinc-700'}>This label is attached only by an exact fingerprint match to the checked-in receipt. Examined external evidence cannot be retuned and replayed as untouched validation.</p>
    </div>
  </section>
}

interface ExperimentRow {
  key: string
  label: string
  source: string
  metrics: Record<string, unknown>
  configuration: string
  evidence: ComparisonEvidence
}

function ExperimentComparison({ anchor, evaluations }: { anchor: EvaluationRun | undefined; evaluations: EvaluationRun[] }) {
  if (!anchor) return null
  const alignedRuns = evaluations.filter((run) => run.evaluation_start === anchor.evaluation_start && run.evaluation_end === anchor.evaluation_end && run.is_demo === anchor.is_demo)
  const represented = new Set<string>()
  const benchmarkLabels: Record<string, string> = { poisson: 'Poisson', poisson_cold_start: 'Poisson cold-start', elo: 'Chronological Elo', dixon_coles: 'Dixon-Coles', nested_selected: 'Nested selected', chronological_ensemble: 'Chronological ensemble' }
  const rows: ExperimentRow[] = alignedRuns.map((run) => {
    const primary = primaryBenchmark(run)
    represented.add(primary)
    return { key: `run:${run.id}`, label: benchmarkLabels[primary] ?? humanizeCode(primary), source: `Primary run #${run.id} / ${run.model_version}`, metrics: run.metrics, configuration: experimentConfiguration(primary, run.metrics, run), evidence: run.id === anchor.id ? 'REFERENCE' : 'NO INTERVAL' }
  })
  for (const [key, label] of Object.entries(benchmarkLabels)) {
    const metrics = anchor.benchmarks[key]
    if (!metrics || represented.has(key)) continue
    rows.push({ key: `benchmark:${key}`, label, source: `Aligned benchmark in run #${anchor.id}`, metrics, configuration: experimentConfiguration(key, metrics, anchor), evidence: comparisonEvidence(metrics) })
  }
  if (rows.length < 2) return null
  const observationCounts = new Set(rows.map((row) => recordValue(row.metrics, 'observations')).filter((value) => value !== null))
  const aligned = observationCounts.size <= 1
  return <section aria-labelledby="experiment-comparison-title">
    <Heading eyebrow="Aligned experiments" title="Model and configuration comparison" />
    <div className="border border-zinc-200 bg-white">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-zinc-200 p-4"><div><h4 className="font-bold" id="experiment-comparison-title">Identical evaluation window</h4><p className="mt-1 text-xs text-zinc-500">{formatDateTime(anchor.evaluation_start)} to {formatDateTime(anchor.evaluation_end)} · only exact-window evidence is included.</p></div><span className={`border px-2 py-1 text-xs font-bold ${aligned ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-amber-200 bg-amber-50 text-amber-800'}`}>{aligned ? 'OBSERVATIONS ALIGNED' : 'CHECK COVERAGE'}</span></div>
      <div className="overflow-x-auto"><table className="w-full min-w-[1080px] text-left text-sm"><thead className="bg-zinc-50 text-xs uppercase text-zinc-500"><tr><th className="px-4 py-3">Experiment</th><th className="px-4 py-3">Source</th><th className="px-4 py-3 text-right">Brier</th><th className="px-4 py-3 text-right">Log loss</th><th className="px-4 py-3 text-right">ECE</th><th className="px-4 py-3 text-right">Observations</th><th className="px-4 py-3">Configuration / selections</th><th className="px-4 py-3">Evidence</th></tr></thead><tbody>{rows.map((row) => <tr className="border-t border-zinc-100 align-top" key={row.key}><td className="px-4 py-3 font-bold">{row.label}</td><td className="px-4 py-3 text-xs text-zinc-600">{row.source}</td><td className="px-4 py-3 text-right font-mono">{format(recordValue(row.metrics, 'brier_score'))}</td><td className="px-4 py-3 text-right font-mono">{format(recordValue(row.metrics, 'log_loss'))}</td><td className="px-4 py-3 text-right font-mono">{percent(recordValue(row.metrics, 'expected_calibration_error'))}</td><td className="px-4 py-3 text-right font-mono">{formatCount(recordValue(row.metrics, 'observations'))}</td><td className="max-w-sm px-4 py-3 text-xs leading-5 text-zinc-600">{row.configuration}</td><td className="px-4 py-3"><span className={`rounded-[4px] border px-2 py-1 text-xs font-bold ${comparisonClass(row.evidence)}`}>{row.evidence}</span></td></tr>)}</tbody></table></div>
      <p className="border-t border-zinc-200 px-4 py-3 text-xs leading-5 text-zinc-500">This matrix compares predictive evidence only. A point estimate or selected configuration does not promote a challenger unless its paired uncertainty and the independent probability policy pass on untouched outcomes.</p>
    </div>
  </section>
}

function PromotionReadiness({ run }: { run: EvaluationRun | undefined }) {
  if (!run) return null
  const evaluated = numberMetric(run, 'evaluated_events', 0)
  const candidates = numberMetric(run, 'candidate_events', 0)
  const uniformEvidence = comparisonEvidence(run.benchmarks.uniform)
  const probabilityReady = run.probability_evaluation_status === 'probability_validated'
  const marketReady = run.evaluation_status === 'calibrated'
  const gates = [
    ['Permitted external history', !run.is_demo, run.is_demo ? 'Demo evidence cannot promote a model.' : 'Non-demo evaluation provenance retained.'],
    ['Complete replay coverage', evaluated > 0 && evaluated === candidates, `${evaluated} of ${candidates} candidate events evaluated.`],
    ['Probability policy', probabilityReady, `Stored status: ${humanizeCode(run.probability_evaluation_status)}.`],
    ['Market / value policy', marketReady, `Stored status: ${humanizeCode(run.evaluation_status)}.`],
    ['Uniform benchmark', uniformEvidence === 'POISSON BETTER', `Paired interval verdict: ${uniformEvidence}.`],
  ] as const
  return <section><Heading eyebrow="Independent evidence tracks" title="Validation readiness" /><div className={`border-l-4 p-4 ${probabilityReady ? 'border-emerald-500 bg-emerald-50' : 'border-amber-400 bg-amber-50'}`}><div className="flex items-center justify-between gap-3"><p className="font-bold">{probabilityReady ? 'Probability research validated' : 'Probability validation blocked'}</p><span className="border border-black/10 bg-white px-2 py-1 text-xs font-bold">{probabilityReady ? 'RESEARCH READY' : 'BLOCKED'}</span></div><div className="mt-3 grid gap-2 md:grid-cols-2">{gates.map(([label, passed, detail]) => <div className="border border-black/10 bg-white/70 p-3 text-xs" key={label}><div className="flex items-center justify-between gap-2"><p className="font-bold">{label}</p><span className={passed ? 'text-emerald-700' : 'text-amber-800'}>{passed ? 'PASS' : 'BLOCKED'}</span></div><p className="mt-1 text-zinc-600">{detail}</p></div>)}</div><p className="mt-3 text-xs leading-5">Probability validation authorizes model research only. Market/value status is {humanizeCode(run.evaluation_status)}; value signals remain blocked unless it is calibrated, and neither track proves profitability.</p></div></section>
}

function EvaluationDiagnosis({ run }: { run: EvaluationRun | undefined }) {
  if (!run) return null
  const probabilityChecks = recordObject(run.policy, 'probability_checks')
  const allChecks = recordObject(run.policy, 'checks')
  const checks = allChecks ?? probabilityChecks
  const gates = Object.entries(checks ?? {}).filter((entry): entry is [string, boolean] => typeof entry[1] === 'boolean')
  const recalibration = run.benchmarks.temperature_scaled
  const raw = recordObject(recalibration, 'raw_subset_metrics')
  const finalCalibrator = recordObject(recalibration, 'final_calibrator')
  const development = recordObject(recalibration, 'development_selection')
  const selectedMethod = textValue(recalibration, 'method') ?? textValue(development ?? undefined, 'selected_method')
  const failedProbability = Object.entries(probabilityChecks ?? {}).filter(([, passed]) => passed === false).map(([key]) => key)
  const failedAll = gates.filter(([, passed]) => !passed).map(([key]) => key)
  const nextAction = diagnosisNextAction(run, failedProbability, failedAll)
  return <section aria-labelledby="evaluation-diagnosis-title">
    <Heading eyebrow="Run diagnosis" title="Why this evaluation is blocked" />
    <div className="border border-zinc-200 bg-white">
      <div className="grid gap-4 border-b border-zinc-200 p-5 lg:grid-cols-[1fr_auto]">
        <div><h4 className="font-bold" id="evaluation-diagnosis-title">Evaluation #{run.id} / {humanizeCode(run.probability_evaluation_status)}</h4><p className="mt-1 text-sm leading-6 text-zinc-600">Every stored promotion gate is shown below. A persisted run is evidence, but only all passing probability gates make it research-qualified.</p></div>
        <div className="text-right text-xs text-zinc-500"><p>Policy {textValue(run.policy, 'version') ?? 'unknown'}</p><p className="mt-1 font-mono">{run.fingerprint.slice(0, 16)}</p></div>
      </div>
      {gates.length ? <div className="grid gap-px bg-zinc-200 sm:grid-cols-2 xl:grid-cols-3">{gates.map(([key, passed]) => <div className="bg-white p-4 text-xs" key={key}><div className="flex items-start justify-between gap-3"><p className="font-bold">{humanizeCode(key)}</p><span className={passed ? 'font-bold text-emerald-700' : 'font-bold text-amber-800'}>{passed ? 'PASS' : 'BLOCKED'}</span></div><p className="mt-2 leading-5 text-zinc-600">{gateEvidence(run, key)}</p></div>)}</div> : <p className="p-5 text-sm text-amber-800">This legacy run has no typed gate-level policy evidence.</p>}
      <div className="border-t border-zinc-200 bg-amber-50 p-4 text-sm text-amber-950"><p className="font-bold">Next valid action</p><p className="mt-1 leading-6">{nextAction}</p></div>
    </div>
    <div className="mt-4 border border-zinc-200 bg-white">
      <div className="border-b border-zinc-200 p-4"><p className="font-bold">Calibration decision</p><p className="mt-1 text-xs text-zinc-500">Development chooses the transform; the later untouched partition verifies non-degradation.</p></div>
      {recalibration ? <><div className="grid grid-cols-2 border-b border-zinc-200 md:grid-cols-4"><Metric label="Selected method" value={selectedMethod ? humanizeCode(selectedMethod) : 'Unknown'} /><Metric label="Development rows" value={formatCount(recordValue(recalibration, 'development_observations'))} /><Metric label="Untouched rows" value={formatCount(recordValue(recalibration, 'validation_observations'))} /><Metric label="Activation" value={humanizeCode(textValue(recalibration, 'activation_status') ?? 'unknown')} /></div><div className="overflow-x-auto"><table className="w-full min-w-[650px] text-left text-sm"><thead className="bg-zinc-50 text-xs uppercase text-zinc-500"><tr><th className="px-4 py-3">Metric</th><th className="px-4 py-3 text-right">Raw untouched</th><th className="px-4 py-3 text-right">Selected method</th><th className="px-4 py-3 text-right">Delta</th></tr></thead><tbody>{(['brier_score', 'log_loss', 'expected_calibration_error'] as const).map((key) => { const rawValue = recordValue(raw ?? undefined, key); const selectedValue = recordValue(recalibration, key); return <tr className="border-t border-zinc-100" key={key}><td className="px-4 py-3 font-semibold">{humanizeCode(key)}</td><td className="px-4 py-3 text-right font-mono">{format(rawValue)}</td><td className="px-4 py-3 text-right font-mono">{format(selectedValue)}</td><td className="px-4 py-3 text-right font-mono">{rawValue === null || selectedValue === null ? '—' : formatSigned(selectedValue - rawValue)}</td></tr> })}</tbody></table></div><div className="grid gap-2 border-t border-zinc-200 bg-zinc-50 p-4 text-xs text-zinc-600 sm:grid-cols-2"><p>Fit through: {formatOptionalDateTime(textValue(finalCalibrator ?? undefined, 'fit_through'))}</p><p>Sample: {formatCount(recordValue(finalCalibrator ?? undefined, 'sample_size'))}</p><p className="font-mono sm:col-span-2">Calibrator fingerprint: {textValue(finalCalibrator ?? undefined, 'input_fingerprint') ?? '—'}</p></div></> : <p className="p-5 text-sm text-amber-800">No adequate chronological recalibration evidence is stored for this run.</p>}
    </div>
  </section>
}

function BenchmarkComparison({ run }: { run: EvaluationRun }) {
  const primary = primaryBenchmark(run)
  const labels: Record<string, string> = { poisson: 'Poisson', elo: 'Chronological Elo' }
  const benchmarkRows: Array<[string, Record<string, unknown> | undefined, boolean]> = [
    [labels[primary] ?? humanizeCode(primary), run.metrics, true],
    ['Poisson', run.benchmarks.poisson, false],
    ['Dixon-Coles', run.benchmarks.dixon_coles, false],
    ['Chronological Elo', run.benchmarks.elo, false],
    ['Nested selected', run.benchmarks.nested_selected, false],
    ['Chronological ensemble', run.benchmarks.chronological_ensemble, false],
    ['Uniform', run.benchmarks.uniform, false],
    ['Market consensus', run.benchmarks.market_consensus, false],
  ]
  const rows = benchmarkRows.filter(([label, , reference]) => reference || label !== (labels[primary] ?? humanizeCode(primary)))
  return <div className="mt-4 overflow-x-auto border border-zinc-200 bg-white">
    <table className="w-full min-w-[1040px] text-left text-sm">
      <thead className="bg-zinc-50 text-xs uppercase text-zinc-500"><tr>
        <th className="px-4 py-3">Benchmark</th>
        <th className="px-4 py-3 text-right">Brier (95% CI)</th>
        <th className="px-4 py-3 text-right">Log loss (95% CI)</th>
        <th className="px-4 py-3 text-right">Paired Brier difference</th>
        <th className="px-4 py-3 text-right">Paired log-loss difference</th>
        <th className="px-4 py-3 text-right">Observations</th>
        <th className="px-4 py-3">Poisson evidence</th>
      </tr></thead>
      <tbody>{rows.map(([label, metrics, reference]) => {
        const evidence = comparisonEvidence(metrics, reference)
        return <tr key={label} className="border-t border-zinc-100">
          <td className="px-4 py-3 font-semibold">{label}</td>
          <td className="px-4 py-3 text-right font-mono text-xs">{formatScoreInterval(metrics, 'brier_score')}</td>
          <td className="px-4 py-3 text-right font-mono text-xs">{formatScoreInterval(metrics, 'log_loss')}</td>
          <td className="px-4 py-3 text-right font-mono text-xs">{formatPairedInterval(metrics, 'brier_score')}</td>
          <td className="px-4 py-3 text-right font-mono text-xs">{formatPairedInterval(metrics, 'log_loss')}</td>
          <td className="px-4 py-3 text-right font-mono">{formatCount(recordValue(metrics, 'observations'))}</td>
          <td className="px-4 py-3"><span className={`rounded-[4px] border px-2 py-1 text-xs font-bold ${comparisonClass(evidence)}`}>{evidence}</span></td>
        </tr>
      })}</tbody>
    </table>
    <p className="border-t border-zinc-100 px-4 py-3 text-xs leading-5 text-zinc-500">Intervals use the stored chronological moving-block bootstrap. Paired differences are Poisson loss minus benchmark loss on identical events: a wholly negative 95% interval favors Poisson, a wholly positive interval favors the benchmark, and an interval crossing zero is inconclusive. Market coverage may be partial.</p>
  </div>
}

function Calibration({ run }: { run: EvaluationRun | undefined }) {
  if (!run?.calibration.length) return null
  return <section><Heading eyebrow="Reliability" title="Calibration buckets" /><div className="border-y border-zinc-200 bg-white p-5"><div className="space-y-4">{run.calibration.map((bucket) => <div key={`${bucket.selection_code}-${bucket.bucket_index}`} className="grid gap-2 sm:grid-cols-[120px_1fr_150px]"><div><p className="text-sm font-semibold">{humanizeCode(bucket.selection_code)}</p><p className="text-xs text-zinc-500">{(bucket.lower_bound * 100).toFixed(0)}–{(bucket.upper_bound * 100).toFixed(0)}% · n={bucket.count}</p></div><div className="relative h-3 self-center bg-zinc-100"><div className="absolute inset-y-0 left-0 bg-emerald-500" style={{ width: `${Math.min(100, bucket.mean_predicted * 100)}%` }} /><span className="absolute inset-y-[-3px] w-0.5 bg-zinc-900" style={{ left: `${Math.min(100, bucket.observed_frequency * 100)}%` }} /></div><p className="text-xs text-zinc-500 sm:text-right">Forecast {(bucket.mean_predicted * 100).toFixed(1)}% · observed {(bucket.observed_frequency * 100).toFixed(1)}%</p></div>)}</div><p className="mt-4 text-xs text-zinc-500">Green bar: mean forecast. Black marker: observed frequency. Buckets are one-vs-rest and retain their original sample counts.</p></div></section>
}

function EvidenceWarning() { return <div className="flex gap-3 border-l-4 border-amber-400 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-950"><AlertTriangle aria-hidden="true" className="mt-0.5 shrink-0" size={18} />A trained baseline or demo evaluation is software evidence only. Promotion requires adequate non-demo chronological history and the fixed evidence policy.</div> }
function ValidationStatuses({ probability, market }: { probability: string; market: string }) { return <div className="flex flex-col items-end gap-1"><span className="text-[10px] font-bold uppercase text-zinc-400">Probability</span><Status status={probability} /><span className="text-[10px] font-bold uppercase text-zinc-400">Market / value</span><Status status={market} /></div> }
function Status({ status }: { status: string }) { const ready = status === 'calibrated' || status === 'probability_validated'; return <span className={`rounded-[4px] border px-2 py-1 text-xs font-bold ${ready ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-amber-200 bg-amber-50 text-amber-800'}`}>{humanizeCode(status)}</span> }
function Heading({ eyebrow, title }: { eyebrow: string; title: string }) { return <div className="mb-3"><p className="text-xs font-bold uppercase text-emerald-700">{eyebrow}</p><h3 className="mt-1 text-lg font-bold">{title}</h3></div> }
function Metric({ label, value: text }: { label: string; value: string }) { return <div className="min-w-0 border-r border-b border-zinc-200 p-4"><p className="text-xs font-semibold uppercase text-zinc-500">{label}</p><p className="mt-2 truncate font-mono text-lg font-bold" title={text}>{text}</p></div> }
function ModelEmpty({ title, detail }: { title: string; detail: string }) { return <div className="border-y border-zinc-200 bg-white px-6 py-10 text-center"><LineChart aria-hidden="true" className="mx-auto text-zinc-400" size={26} /><h3 className="mt-3 font-bold">{title}</h3><p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-zinc-500">{detail}</p></div> }
type ComparisonEvidence = 'REFERENCE' | 'POISSON BETTER' | 'BENCHMARK BETTER' | 'INCONCLUSIVE' | 'NO INTERVAL'

type NumericInterval = {
  estimate: number
  lower: number
  upper: number
  confidence_level: number
  observations: number
}

function comparisonEvidence(metrics: Record<string, unknown> | undefined, reference = false): ComparisonEvidence {
  if (reference) return 'REFERENCE'
  const brier = pairedInterval(metrics, 'brier_score')
  const logLoss = pairedInterval(metrics, 'log_loss')
  if (!brier || !logLoss) return 'NO INTERVAL'
  if (brier.upper < 0 && logLoss.upper < 0) return 'POISSON BETTER'
  if (brier.lower > 0 && logLoss.lower > 0) return 'BENCHMARK BETTER'
  return 'INCONCLUSIVE'
}

function comparisonClass(evidence: ComparisonEvidence): string {
  if (evidence === 'POISSON BETTER') return 'border-emerald-200 bg-emerald-50 text-emerald-800'
  if (evidence === 'BENCHMARK BETTER') return 'border-rose-200 bg-rose-50 text-rose-800'
  if (evidence === 'REFERENCE') return 'border-sky-200 bg-sky-50 text-sky-800'
  return 'border-amber-200 bg-amber-50 text-amber-800'
}

function formatScoreInterval(metrics: Record<string, unknown> | undefined, key: string): string {
  const interval = scoreInterval(metrics, key)
  if (!interval) return format(recordValue(metrics, key))
  return `${format(interval.estimate)} [${format(interval.lower)}, ${format(interval.upper)}]`
}

function formatPairedInterval(metrics: Record<string, unknown> | undefined, key: string): string {
  const interval = pairedInterval(metrics, key)
  if (!interval) return '—'
  return `${formatSigned(interval.estimate)} [${formatSigned(interval.lower)}, ${formatSigned(interval.upper)}]`
}

function scoreInterval(metrics: Record<string, unknown> | undefined, key: string): NumericInterval | null {
  return numericInterval(recordObject(metrics, 'score_intervals'), key)
}

function pairedInterval(metrics: Record<string, unknown> | undefined, key: string): NumericInterval | null {
  return numericInterval(recordObject(metrics, 'paired_loss_difference'), key)
}

function numericInterval(container: Record<string, unknown> | null, key: string): NumericInterval | null {
  const candidate = recordObject(container ?? undefined, key)
  if (!candidate) return null
  const estimate = finiteNumber(candidate.estimate)
  const lower = finiteNumber(candidate.lower)
  const upper = finiteNumber(candidate.upper)
  const confidenceLevel = finiteNumber(candidate.confidence_level)
  const observations = finiteNumber(candidate.observations)
  if (estimate === null || lower === null || upper === null || confidenceLevel === null || observations === null) return null
  return { estimate, lower, upper, confidence_level: confidenceLevel, observations }
}

function recordObject(values: Record<string, unknown> | undefined, key: string): Record<string, unknown> | null {
  const item = values?.[key]
  return typeof item === 'object' && item !== null && !Array.isArray(item) ? item as Record<string, unknown> : null
}

function finiteNumber(item: unknown): number | null {
  return typeof item === 'number' && Number.isFinite(item) ? item : null
}

function primaryBenchmark(run: EvaluationRun): string {
  const configured = textValue(run.config, 'primary_benchmark')
  if (configured) return configured
  return run.model_version.toLowerCase().includes('elo') ? 'elo' : 'poisson'
}

function experimentConfiguration(key: string, metrics: Record<string, unknown>, run: EvaluationRun): string {
  if (key === 'poisson_cold_start') return `League-prior development benchmark · ${formatCount(recordValue(metrics, 'evaluated_events'))} / ${formatCount(recordValue(metrics, 'candidate_events'))} coverage · ${formatCount(recordValue(metrics, 'below_minimum_venue_history_events'))} cold-start events.`
  if (key === 'nested_selected') {
    const counts = recordObject(metrics, 'selection_counts')
    return counts ? `Selections: ${Object.entries(counts).map(([name, count]) => `${humanizeCode(name)} ${String(count)}`).join(' · ')}` : 'Pre-registered nested candidate grid.'
  }
  if (key === 'chronological_ensemble') {
    const counts = recordObject(metrics, 'weight_counts')
    return counts ? `Weights: ${Object.entries(counts).map(([name, count]) => `${name} (${String(count)})`).join(' · ')}` : 'Pre-registered multi-model simplex grid.'
  }
  if (key === 'dixon_coles') {
    const config = recordObject(run.config, 'dixon_coles_benchmark')
    return `Decay ${format(recordValue(config ?? undefined, 'decay_rate'))} · ${textValue(metrics, 'version') ?? 'time-decayed benchmark'}`
  }
  if (key === 'elo') return 'Point-in-time Davidson Elo benchmark.'
  if (key === 'poisson') return textValue(run.config, 'evaluation_method_version') ?? 'Venue-specific shrunk Poisson benchmark.'
  return textValue(metrics, 'version') ?? 'Stored aligned benchmark specification.'
}

function textValue(values: Record<string, unknown> | undefined, key: string): string | null {
  const item = values?.[key]
  return typeof item === 'string' && item ? item : null
}

function formatOptionalDateTime(value: string | null): string {
  return value ? formatDateTime(value) : '—'
}

function gateEvidence(run: EvaluationRun, key: string): string {
  const market = run.benchmarks.market_consensus
  const recalibration = run.benchmarks.temperature_scaled
  if (key === 'non_demo_data') return run.is_demo ? 'Run contains demo evidence.' : 'Permitted non-demo evidence retained.'
  if (key === 'minimum_observations') return `${formatCount(recordValue(run.metrics, 'observations'))} observed / ${formatCount(recordValue(run.policy, 'minimum_observations'))} required.`
  if (key === 'minimum_coverage') return `${percent(recordValue(run.metrics, 'coverage'))} coverage / ${percent(recordValue(run.policy, 'minimum_coverage'))} required.`
  if (key === 'maximum_expected_calibration_error') return `${percent(recordValue(run.metrics, 'expected_calibration_error'))} ECE / ${percent(recordValue(run.policy, 'maximum_expected_calibration_error'))} maximum.`
  if (key === 'uniform_brier_upper_difference_below_zero') return `Upper paired Brier difference ${format(pairedInterval(run.benchmarks.uniform, 'brier_score')?.upper ?? null)}; must be below zero.`
  if (key === 'uniform_log_loss_upper_difference_below_zero') return `Upper paired log-loss difference ${format(pairedInterval(run.benchmarks.uniform, 'log_loss')?.upper ?? null)}; must be below zero.`
  if (key === 'chronological_recalibration_accepted') return `Stored recalibration activation: ${humanizeCode(textValue(recalibration, 'activation_status') ?? 'missing')}.`
  if (key === 'market_benchmark_available') return market ? 'Compatible market benchmark is stored.' : 'No compatible historical market benchmark is stored.'
  if (key === 'minimum_market_observations') return `${formatCount(recordValue(market, 'observations'))} market observations / ${formatCount(recordValue(run.policy, 'minimum_market_observations'))} required.`
  if (key === 'minimum_market_coverage') return `${percent(recordValue(market, 'coverage'))} market coverage / ${percent(recordValue(run.policy, 'minimum_market_coverage'))} required.`
  if (key === 'market_brier_upper_difference_below_zero') return `Upper paired market Brier difference ${format(pairedInterval(market, 'brier_score')?.upper ?? null)}; must be below zero.`
  if (key === 'market_log_loss_upper_difference_below_zero') return `Upper paired market log-loss difference ${format(pairedInterval(market, 'log_loss')?.upper ?? null)}; must be below zero.`
  return 'Stored boolean policy decision.'
}

function diagnosisNextAction(run: EvaluationRun, failedProbability: string[], failedAll: string[]): string {
  if (run.is_demo) return 'Import permitted timestamped final results and run a non-demo chronological replay.'
  if (failedProbability.includes('chronological_recalibration_accepted')) return 'Wait for a genuinely new untouched result window, then verify the frozen calibration rule; do not retune on this examined holdout.'
  if (failedProbability.length) return `Acquire new untouched chronological results and re-evaluate the frozen model specification. Failed probability gates: ${failedProbability.map(humanizeCode).join(', ')}.`
  if (failedAll.some((key) => key.startsWith('market_') || key.includes('market'))) return 'Import compatible timestamped historical bookmaker and closing-price evidence before market/value validation.'
  return 'No blocking gate is stored. Inspect the immutable run provenance before using it for research.'
}

function formatSigned(item: number): string {
  return `${item > 0 ? '+' : ''}${item.toFixed(4)}`
}
function value(run: EvaluationRun, key: string): number | null { const item = run.metrics[key]; return typeof item === 'number' && Number.isFinite(item) ? item : null }
function numberMetric(run: EvaluationRun, key: string, fallback: number): number { return value(run, key) ?? fallback }
function recordValue(values: Record<string, unknown> | undefined, key: string): number | null { const item = values?.[key]; return typeof item === 'number' && Number.isFinite(item) ? item : null }
function formatCount(item: number | null): string { return item === null ? '—' : item.toFixed(0) }
function format(item: number | null): string { return item === null ? '—' : item.toFixed(4) }
function score(run: EvaluationRun, key: string): string { return format(value(run, key)) }
function percent(item: number | null): string { return item === null ? '—' : `${(item * 100).toFixed(1)}%` }
