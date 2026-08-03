import { ArrowRight, CheckCircle2, CircleAlert } from 'lucide-react'

import type { DashboardData, ReadinessCounts } from '../types'

interface Requirement { key: keyof ReadinessCounts; label: string; action: string; target: string }

const requirementsByView: Record<string, Requirement[]> = {
  overview: [
    req('odds_snapshots', 'Import fixtures and odds', 'Import complete odds snapshots', 'data'),
    req('final_results', 'Import historical results', 'Import timestamped results', 'data'),
    req('model_versions', 'Train a model', 'Train a leakage-safe model', 'models'),
    req('non_demo_calibrated_evaluations', 'Evaluate calibration', 'Run a qualifying evaluation', 'models'),
    req('predictions', 'Persist predictions', 'Persist pre-kickoff predictions', 'models'),
    req('signals', 'Generate signals', 'Generate calibrated signals', 'models'),
    req('signal_backtests', 'Replay settled signals', 'Run a settled signal replay', 'backtests'),
  ],
  matchday: [req('events', 'Imported fixtures', 'Import fixture/odds data', 'data'), req('odds_snapshots', 'Timestamped odds', 'Import complete odds snapshots', 'data')],
  event: [req('events', 'Imported events', 'Import event data', 'data'), req('odds_snapshots', 'Market snapshots', 'Import complete odds snapshots', 'data'), req('predictions', 'Stored predictions', 'Run model prediction', 'models')],
  comparison: [req('odds_snapshots', 'Comparable prices', 'Import complete odds snapshots', 'data')],
  opportunities: signalRequirements(), underdogs: signalRequirements(),
  arbitrage: [req('odds_snapshots', 'Complete odds markets', 'Import odds snapshots', 'data'), req('bookmaker_tax_mappings', 'Verified tax mappings', 'Record sourced tax terms', 'arbitrage'), req('bookmaker_constraints', 'Observed stake limits', 'Record bookmaker constraints', 'arbitrage')],
  builder: [req('model_versions', 'Trained model', 'Train a model version', 'models'), req('predictions', 'Pre-kickoff prediction', 'Persist an event prediction', 'models')],
  models: [req('final_results', 'Historical results', 'Import timestamped results', 'data'), req('model_versions', 'Trained model', 'Use model operations below', 'models')],
  backtests: [req('final_results', 'Settled results', 'Import historical results', 'data'), req('signals', 'Stored signals', 'Generate calibrated signals', 'models')],
  bankroll: [req('signal_backtests', 'Signal return backtest', 'Run a settled signal replay', 'backtests')],
  data: [req('intelligence_records', 'Football intelligence', 'Import availability or a full bundle', 'data')],
}

export function WorkflowReadiness({ dashboard, view, onNavigate }: { dashboard: DashboardData; view: string; onNavigate: (target: string) => void }) {
  const requirements = requirementsByView[view] ?? []
  if (!requirements.length) return null
  const counts = dashboard.readiness ?? fallbackCounts(dashboard)
  const blocked = requirements.filter((item) => counts[item.key] === 0)
  const next = blocked[0]
  const isOverview = view === 'overview'
  return <section className={`mb-6 border-l-4 px-4 py-4 ${blocked.length ? 'border-amber-400 bg-amber-50' : 'border-emerald-500 bg-emerald-50'}`} aria-label="Workflow readiness"><div className="flex items-start gap-3">{blocked.length ? <CircleAlert aria-hidden="true" className="mt-0.5 shrink-0 text-amber-800" size={19} /> : <CheckCircle2 aria-hidden="true" className="mt-0.5 shrink-0 text-emerald-800" size={19} />}<div className="min-w-0 flex-1"><div className="flex items-start justify-between gap-6"><div><p className="font-bold">{isOverview ? 'Research workflow' : blocked.length ? `${blocked.length} prerequisite${blocked.length === 1 ? '' : 's'} missing` : 'Workflow prerequisites available'}</p>{isOverview ? <p className="mt-1 text-xs leading-5 text-zinc-600">Complete each timestamp-safe stage in order. The first incomplete stage is always the recommended next action.</p> : null}</div>{isOverview && next ? <button className="inline-flex shrink-0 items-center gap-2 bg-zinc-900 px-3 py-2 text-xs font-bold text-white" onClick={() => onNavigate(next.target)} type="button">Next: {next.label}<ArrowRight aria-hidden="true" size={14} /></button> : null}</div><ol className={`mt-3 grid gap-2 ${isOverview ? 'grid-cols-7' : 'grid-cols-3'}`}>{requirements.map((item, index) => { const ready = counts[item.key] > 0; const current = item === next; return <li key={item.key} className={`flex min-h-20 items-start justify-between gap-3 border px-3 py-2 text-xs ${current ? 'border-amber-500 bg-white' : 'border-black/10 bg-white/70'}`}><div><div className="mb-2 flex items-center gap-2"><span className={`grid h-5 w-5 place-items-center rounded-full text-[10px] font-bold ${ready ? 'bg-emerald-700 text-white' : current ? 'bg-amber-500 text-zinc-950' : 'bg-zinc-200 text-zinc-600'}`}>{ready ? '✓' : index + 1}</span>{current ? <span className="font-bold uppercase text-amber-800">Next</span> : null}</div><p className="font-bold">{item.label}</p><p className={ready ? 'mt-1 text-emerald-700' : 'mt-1 text-zinc-500'}>{ready ? `${counts[item.key]} stored` : item.action}</p></div>{!ready && !isOverview ? <button aria-label={`Go to ${item.action}`} className="grid h-7 w-7 shrink-0 place-items-center border border-zinc-300 bg-white" onClick={() => onNavigate(item.target)} type="button"><ArrowRight aria-hidden="true" size={14} /></button> : null}</li> })}</ol>{blocked.length && !isOverview ? <p className="mt-3 text-xs leading-5 text-amber-900">This screen remains usable for inspection, but evidence-dependent outputs stay blocked until every required layer is stored.</p> : null}{isOverview && !blocked.length ? <p className="mt-3 text-xs font-semibold text-emerald-900">The complete research chain is available for inspection. Re-run stages only when new timestamped evidence is imported.</p> : null}</div></div></section>
}

function signalRequirements(): Requirement[] { return [req('odds_snapshots', 'Compatible odds', 'Import complete odds snapshots', 'data'), req('model_versions', 'Trained model', 'Train a model version', 'models'), req('non_demo_calibrated_evaluations', 'Non-demo calibration', 'Run a qualifying evaluation', 'models'), req('predictions', 'Stored predictions', 'Persist pre-kickoff predictions', 'models'), req('signals', 'Generated signals', 'Generate signals from predictions', 'models')] }
function req(key: keyof ReadinessCounts, label: string, action: string, target: string): Requirement { return { key, label, action, target } }
function fallbackCounts(dashboard: DashboardData): ReadinessCounts { return { events: dashboard.events.length, odds_snapshots: dashboard.providers.reduce((sum, provider) => sum + provider.snapshot_count, 0), final_results: 0, model_versions: dashboard.models.length, predictions: 0, non_demo_calibrated_evaluations: dashboard.evaluations.filter((run) => !run.is_demo && run.evaluation_status === 'calibrated').length, signals: dashboard.signals.length, signal_backtests: dashboard.backtests.length, bookmaker_tax_mappings: 0, bookmaker_constraints: 0, intelligence_records: 0 } }
