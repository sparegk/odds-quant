import { ArrowRight, CheckCircle2, CircleAlert } from 'lucide-react'

import type { DashboardData, ReadinessCounts } from '../types'

interface Requirement { key: keyof ReadinessCounts; label: string; action: string; target: string }

const requirementsByView: Record<string, Requirement[]> = {
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
  return <section className={`mb-6 border-l-4 px-4 py-4 ${blocked.length ? 'border-amber-400 bg-amber-50' : 'border-emerald-500 bg-emerald-50'}`} aria-label="Workflow readiness"><div className="flex items-start gap-3">{blocked.length ? <CircleAlert aria-hidden="true" className="mt-0.5 shrink-0 text-amber-800" size={19} /> : <CheckCircle2 aria-hidden="true" className="mt-0.5 shrink-0 text-emerald-800" size={19} />}<div className="min-w-0 flex-1"><p className="font-bold">{blocked.length ? `${blocked.length} prerequisite${blocked.length === 1 ? '' : 's'} missing` : 'Workflow prerequisites available'}</p><div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-3">{requirements.map((item) => { const ready = counts[item.key] > 0; return <div key={item.key} className="flex items-center justify-between gap-3 border border-black/10 bg-white/70 px-3 py-2 text-xs"><div><p className="font-bold">{item.label}</p><p className={ready ? 'text-emerald-700' : 'text-amber-800'}>{ready ? `${counts[item.key]} stored` : item.action}</p></div>{!ready ? <button aria-label={`Go to ${item.action}`} className="grid h-7 w-7 shrink-0 place-items-center border border-zinc-300 bg-white" onClick={() => onNavigate(item.target)} type="button"><ArrowRight aria-hidden="true" size={14} /></button> : null}</div> })}</div>{blocked.length ? <p className="mt-3 text-xs leading-5 text-amber-900">This screen remains usable for inspection, but evidence-dependent outputs stay blocked until every required layer is stored.</p> : null}</div></div></section>
}

function signalRequirements(): Requirement[] { return [req('odds_snapshots', 'Compatible odds', 'Import complete odds snapshots', 'data'), req('model_versions', 'Trained model', 'Train a model version', 'models'), req('non_demo_calibrated_evaluations', 'Non-demo calibration', 'Run a qualifying evaluation', 'models'), req('predictions', 'Stored predictions', 'Persist pre-kickoff predictions', 'models'), req('signals', 'Generated signals', 'Generate signals from predictions', 'models')] }
function req(key: keyof ReadinessCounts, label: string, action: string, target: string): Requirement { return { key, label, action, target } }
function fallbackCounts(dashboard: DashboardData): ReadinessCounts { return { events: dashboard.events.length, odds_snapshots: dashboard.providers.reduce((sum, provider) => sum + provider.snapshot_count, 0), final_results: 0, model_versions: dashboard.models.length, predictions: 0, non_demo_calibrated_evaluations: dashboard.evaluations.filter((run) => !run.is_demo && run.evaluation_status === 'calibrated').length, signals: dashboard.signals.length, signal_backtests: dashboard.backtests.length, bookmaker_tax_mappings: 0, bookmaker_constraints: 0, intelligence_records: 0 } }
