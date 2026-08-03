import {
  Activity,
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  HelpCircle,
  RefreshCw,
  X,
} from 'lucide-react'
import { lazy, Suspense, useCallback, useEffect, useState } from 'react'
import type { FormEvent } from 'react'

import { calculateArbitrage, loadComparison, loadDashboard, runSignalBacktest } from './api/client'
import { FreshnessBadge } from './components/FreshnessBadge'
import { FirstVisitGuide } from './components/FirstVisitGuide'
import { WorkflowReadiness } from './components/WorkflowReadiness'
import { QuantPriceTable } from './components/QuantPriceTable'
import { Methodology } from './components/Methodology'

export { Methodology }
import { formatDateTime, humanizeCode } from './lib/format'
import { rememberResearchGuideDismissal, shouldShowResearchGuide } from './lib/researchGuide'
import { chooseDefaultEventId, preserveSelectedEventId } from './lib/events'
import {
  navigateToEvent,
  navigateToView,
  navigation,
  navigationContext,
  navigationEventName,
  navigationGroups,
  readRoute,
} from './navigation'
import type { ViewKey } from './navigation'
import type { DashboardData, EvaluationRun, EventSummary, MarketComparison, ValueSignal } from './types'

const BestPriceChart = lazy(async () => {
  const module = await import('./components/BestPriceChart')
  return { default: module.BestPriceChart }
})

const BetBuilderLab = lazy(async () => ({ default: (await import('./components/BetBuilderLab')).BetBuilderLab }))
const BankrollResearch = lazy(async () => ({ default: (await import('./components/BankrollResearch')).BankrollResearch }))
const MatchdayResearch = lazy(async () => ({ default: (await import('./components/MatchdayResearch')).MatchdayResearch }))
const UnderdogScanner = lazy(async () => ({ default: (await import('./components/UnderdogScanner')).UnderdogScanner }))
const ValueOpportunities = lazy(async () => ({ default: (await import('./components/ValueOpportunities')).ValueOpportunities }))
const MatchDetailPage = lazy(async () => ({ default: (await import('./components/MatchDetailPage')).MatchDetailPage }))
const ModelPerformance = lazy(async () => ({ default: (await import('./components/ModelPerformance')).ModelPerformance }))
const DataOperations = lazy(async () => ({ default: (await import('./components/DataOperations')).DataOperations }))
const ArbitrageSettings = lazy(async () => ({ default: (await import('./components/ArbitrageSettings')).ArbitrageSettings }))
const ResearchWorkspace = lazy(async () => ({ default: (await import('./components/ResearchWorkspace')).ResearchWorkspace }))
const OperationsCenter = lazy(async () => ({ default: (await import('./components/OperationsCenter')).OperationsCenter }))

const DASHBOARD_OPENED_AT = Date.now()

function navigateTo(view: ViewKey) {
  if (view !== 'event') navigateToView(view)
}

function App() {
  const [view, setView] = useState<ViewKey>(() => readRoute().view)
  const [routeNotFound, setRouteNotFound] = useState(() => readRoute().notFound)
  const [dashboard, setDashboard] = useState<DashboardData | null>(null)
  const [selectedEventId, setSelectedEventId] = useState<number | null>(() => readRoute().eventId)
  const [markets, setMarkets] = useState<MarketComparison[]>([])
  const [comparisonLoading, setComparisonLoading] = useState(false)
  const [comparisonError, setComparisonError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [researchGuideOpen, setResearchGuideOpen] = useState(shouldShowResearchGuide)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const loaded = await loadDashboard()
      setDashboard(loaded)
      setSelectedEventId((current) => preserveSelectedEventId(loaded.events, current))
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to reach the OddsQuant API')
    } finally {
      setLoading(false)
    }
  }, [])

  const synchronize = useCallback(async () => {
    await refresh()
    setNotice('Changes saved and dashboard resources synchronized.')
  }, [refresh])

  useEffect(() => {
    let active = true
    void loadDashboard()
      .then((loaded) => {
        if (!active) return
        setDashboard(loaded)
        setSelectedEventId((current) => current ?? chooseDefaultEventId(loaded.events))
      })
      .catch((caught: unknown) => {
        if (active) setError(caught instanceof Error ? caught.message : 'Unable to reach the OddsQuant API')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    const synchronizeRoute = () => {
      const route = readRoute()
      setView(route.view)
      setRouteNotFound(route.notFound)
      if (route.eventId !== null) setSelectedEventId(route.eventId)
    }
    window.addEventListener('hashchange', synchronizeRoute)
    window.addEventListener('popstate', synchronizeRoute)
    window.addEventListener(navigationEventName, synchronizeRoute)
    return () => {
      window.removeEventListener('hashchange', synchronizeRoute)
      window.removeEventListener('popstate', synchronizeRoute)
      window.removeEventListener(navigationEventName, synchronizeRoute)
    }
  }, [])

  useEffect(() => {
    const context = navigationContext(view)
    document.title = routeNotFound ? 'Page not found | OddsQuant' : `${context.label} | OddsQuant`
  }, [routeNotFound, view])

  useEffect(() => {
    if (selectedEventId === null) {
      return
    }
    let active = true
    void Promise.resolve()
      .then(() => {
        if (active) {
          setComparisonLoading(true)
          setComparisonError(null)
        }
        return loadComparison(selectedEventId)
      })
      .then((result) => {
        if (active) setMarkets(result)
      })
      .catch((caught: unknown) => {
        if (active) {
          setMarkets([])
          setComparisonError(caught instanceof Error ? caught.message : 'Unable to load odds comparison')
        }
      })
      .finally(() => {
        if (active) setComparisonLoading(false)
      })
    return () => {
      active = false
    }
  }, [selectedEventId])

  const selectView = (next: ViewKey) => {
    navigateToView(next)
    setView(next)
    setRouteNotFound(false)
  }

  const openEvent = (eventId: number) => {
    setSelectedEventId(eventId)
    navigateToEvent(eventId)
    setView('event')
    setRouteNotFound(false)
  }

  const selectEvent = (eventId: number) => {
    setSelectedEventId(eventId)
    if (view === 'event') navigateToEvent(eventId)
  }

  return (
    <div className="min-h-screen bg-[#f4f6f5] text-zinc-900">
      <aside className="fixed inset-y-0 left-0 z-20 flex w-64 flex-col border-r border-zinc-800 bg-[#15191e] text-zinc-100">
        <div className="flex h-16 items-center gap-3 border-b border-zinc-800 px-5">
          <span className="grid h-9 w-9 place-items-center rounded-[6px] bg-emerald-400 text-zinc-950">
            <Activity aria-hidden="true" size={21} strokeWidth={2.5} />
          </span>
          <div>
            <div className="text-base font-bold">OddsQuant</div>
            <div className="text-xs text-zinc-400">Football intelligence</div>
          </div>
        </div>
        <nav className="flex-1 overflow-y-auto px-3 py-4" aria-label="Primary navigation">
          {navigationGroups.map((group) => (
            <div className='mb-5 last:mb-0' key={group.label}>
              <p className='mb-1.5 px-3 text-[10px] font-bold uppercase tracking-[0.16em] text-zinc-400'>{group.label}</p>
              {group.items.map((item) => {
                const Icon = item.icon
                const active = view === item.key
                return (
              <button
                aria-current={active ? 'page' : undefined}
                key={item.key}
                className={`mb-1 flex h-10 w-full items-center gap-3 rounded-[5px] px-3 text-left text-sm transition-colors ${
                  active ? 'bg-zinc-100 font-semibold text-zinc-950' : 'text-zinc-400 hover:bg-zinc-800 hover:text-white'
                }`}
                onClick={() => selectView(item.key)}
                type="button"
              >
                <Icon aria-hidden="true" size={17} />
                {item.label}
              </button>
                )
              })}
            </div>
          ))}
        </nav>
        <div className="border-t border-zinc-800 p-4 text-xs leading-5 text-zinc-400">
          <p className="font-bold uppercase tracking-[0.12em] text-zinc-400">Evidence key</p>
          <div aria-label="Evidence state legend" className="mt-2 grid grid-cols-3 gap-2 text-[10px]">
            <span className="border border-emerald-800 bg-emerald-950/50 px-2 py-1 text-emerald-300">Qualified</span>
            <span className="border border-amber-800 bg-amber-950/40 px-2 py-1 text-amber-300">Blocked</span>
            <span className="border border-sky-800 bg-sky-950/40 px-2 py-1 text-sky-300">Demo</span>
          </div>
          <p className="mt-3">Desktop research only. No automated betting.</p>
        </div>
      </aside>

      <div className="pl-64">
        {notice ? <SuccessNotice message={notice} onDismiss={() => setNotice(null)} /> : null}
        <header className="sticky top-0 z-10 border-b border-zinc-200 bg-white/95 backdrop-blur">
          <div className="flex h-16 items-center justify-between gap-4 px-8">
            <div className="min-w-0 flex-1">
              <p className="truncate text-[10px] font-bold uppercase tracking-[0.14em] text-zinc-600">{routeNotFound ? 'OddsQuant' : navigationContext(view).group}</p>
              <h1 className="truncate text-lg font-bold">{routeNotFound ? 'Page not found' : navigation.find((item) => item.key === view)?.label}</h1>
            </div>
            <div className="flex items-center gap-2">
              <DataModeBadge mode={dashboard?.status.data_mode} />
              <button
                aria-label='Open research guide'
                className='grid h-9 w-9 place-items-center rounded-[5px] border border-zinc-300 bg-white text-zinc-700 hover:bg-zinc-50'
                onClick={() => setResearchGuideOpen(true)}
                title='Open research guide'
                type='button'
              >
                <HelpCircle aria-hidden='true' size={16} />
              </button>
              <button
                aria-label="Refresh dashboard data"
                className="grid h-9 w-9 place-items-center rounded-[5px] border border-zinc-300 bg-white text-zinc-700 hover:bg-zinc-50 disabled:opacity-50"
                disabled={loading}
                onClick={() => void refresh()}
                title="Refresh dashboard data"
                type="button"
              >
                <RefreshCw aria-hidden="true" className={loading ? 'animate-spin' : ''} size={16} />
              </button>
            </div>
          </div>
        </header>

        {researchGuideOpen ? <FirstVisitGuide onDismiss={() => { rememberResearchGuideDismissal(); setResearchGuideOpen(false) }} /> : null}

        <main className="px-8 py-7">
          {error ? <ConnectionError message={error} onRetry={() => void refresh()} /> : null}
          {!error && dashboard ? (
            <>
              <ResourceErrors errors={dashboard.resource_errors} />
              {!routeNotFound ? <WorkflowReadiness dashboard={dashboard} view={view} onNavigate={(target) => selectView(target as ViewKey)} /> : null}
              {routeNotFound ? <NotFound onNavigate={() => selectView('matchday')} /> : <Suspense fallback={<LoadingState />}><ActiveView
                comparisonError={comparisonError}
                comparisonLoading={comparisonLoading}
                dashboard={dashboard}
                markets={markets}
                onOpenEvent={openEvent}
                onSelectEvent={selectEvent}
                onRefresh={synchronize}
                selectedEventId={selectedEventId}
                view={view}
              /></Suspense>}
            </>
          ) : null}
          {!error && !dashboard ? <LoadingState /> : null}
        </main>

        <footer className="border-t border-zinc-200 bg-white px-8 py-4 text-xs leading-5 text-zinc-500">
          Statistical edges can disappear. Historical results do not ensure future performance. Odds change rapidly. Follow local laws, age restrictions, and bookmaker terms; set strict financial limits and never chase losses.
        </footer>
      </div>
    </div>
  )
}

interface ActiveViewProps {
  view: ViewKey
  dashboard: DashboardData
  markets: MarketComparison[]
  comparisonLoading: boolean
  comparisonError: string | null
  selectedEventId: number | null
  onOpenEvent: (eventId: number) => void
  onSelectEvent: (eventId: number) => void
  onRefresh: () => Promise<void>
}

function NotFound({ onNavigate }: { onNavigate: () => void }) {
  return <section className="grid min-h-[520px] place-items-center border border-zinc-200 bg-white text-center"><div><p className="text-xs font-bold uppercase tracking-[0.14em] text-emerald-700">404</p><h2 className="mt-2 text-2xl font-bold">This research page does not exist</h2><p className="mt-2 text-sm text-zinc-500">Use the desktop navigation or return to the current matchday.</p><button className="mt-5 bg-zinc-900 px-4 py-2 text-sm font-bold text-white" onClick={onNavigate} type="button">Return to matchday</button></div></section>
}

function DataModeBadge({ mode }: { mode: string | undefined }) {
  const demo = mode === 'demo_or_user_supplied' || mode === 'demo'
  const external = mode === 'external' || mode === 'user_supplied'
  const label = demo ? 'Demo / user data' : external ? mode === 'external' ? 'External data' : 'User-supplied data' : mode ? humanizeCode(mode) : 'Connecting'
  const tone = demo ? 'border-sky-300 bg-sky-50 text-sky-900' : external ? 'border-emerald-300 bg-emerald-50 text-emerald-900' : 'border-zinc-300 bg-zinc-50 text-zinc-700'
  return <span className={`inline-flex items-center gap-2 rounded-[4px] border px-2.5 py-1 text-xs font-bold ${tone}`}><span aria-hidden="true" className={`h-1.5 w-1.5 rounded-full ${demo ? 'bg-sky-600' : external ? 'bg-emerald-600' : 'bg-zinc-500'}`} />{label}</span>
}

function ActiveView(props: ActiveViewProps) {
  switch (props.view) {
    case 'overview':
      return <Overview dashboard={props.dashboard} onNavigate={navigateToView} onSelectEvent={props.onOpenEvent} />
    case 'matchday':
      return <MatchdayResearch events={props.dashboard.events} onSelectEvent={props.onSelectEvent} />
    case 'event':
      return <MatchDetailPage events={props.dashboard.events} selectedEventId={props.selectedEventId} onSelectEvent={props.onSelectEvent} onOpenBuilder={() => navigateToView('builder')} onOpenComparison={() => navigateToView('comparison')} />
    case 'comparison':
      return <OddsComparison {...props} />
    case 'data':
      return <DataOperations dashboard={props.dashboard} onChanged={props.onRefresh} />
    case 'status':
      return <OperationsCenter dashboard={props.dashboard} onRefresh={props.onRefresh} />
    case 'methodology':
      return <Methodology />
    case 'opportunities':
      return <ValueOpportunities dashboard={props.dashboard} onOpenEvent={props.onOpenEvent} />
    case 'underdogs':
      return <UnderdogScanner dashboard={props.dashboard} onOpenEvent={props.onOpenEvent} />
    case 'arbitrage':
      return <ArbitrageResearch dashboard={props.dashboard} onChanged={props.onRefresh} />
    case 'builder':
      return <BetBuilderLab events={props.dashboard.events} onSelectEvent={props.onSelectEvent} selectedEventId={props.selectedEventId} />
    case 'workspace':
      return <ResearchWorkspace dashboard={props.dashboard} onOpenEvent={props.onOpenEvent} />
    case 'models':
      return <ModelPerformance dashboard={props.dashboard} onChanged={props.onRefresh} />
    case 'backtests':
      return <BacktestResearch dashboard={props.dashboard} onChanged={props.onRefresh} />
    case 'bankroll':
      return <BankrollResearch backtests={props.dashboard.backtests} />
  }
}

export function Overview({ dashboard, onSelectEvent, onNavigate }: { dashboard: DashboardData; onSelectEvent: (eventId: number) => void; onNavigate: (view: ViewKey) => void }) {
  const snapshotCount = dashboard.providers.reduce((sum, provider) => sum + provider.snapshot_count, 0)
  const latestOdds = dashboard.events
    .map((event) => event.latest_odds_at)
    .filter((value): value is string => value !== null)
    .sort()
    .at(-1)
  const latestEvaluation = dashboard.evaluations[0]
  const readiness = dashboard.readiness
  const monitoring = dashboard.monitoring
  const coverage = monitoring?.coverage
  const resourceErrorCount = Object.keys(dashboard.resource_errors).length
  const actions: Array<{ title: string; detail: string; target: ViewKey; targetLabel: string }> = []

  if (resourceErrorCount) actions.push({ title: 'Restore unavailable resources', detail: `${resourceErrorCount} dashboard resource${resourceErrorCount === 1 ? '' : 's'} failed to load.`, target: 'data', targetLabel: 'Data operations' })
  if (!monitoring || !monitoring.healthy || monitoring.alerts.length) actions.push({ title: 'Resolve collection monitoring', detail: monitoring ? `${monitoring.alerts.length} active alert${monitoring.alerts.length === 1 ? '' : 's'} across scheduled providers.` : 'No collection monitoring evidence is available.', target: 'data', targetLabel: 'Data operations' })
  if (coverage && coverage.permitted_final_results < coverage.minimum_evaluation_results) actions.push({ title: 'Complete historical coverage', detail: `${coverage.permitted_final_results} of at least ${coverage.minimum_evaluation_results} permitted final results are stored.`, target: 'data', targetLabel: 'Data operations' })
  if ((readiness?.model_versions ?? dashboard.models.length) === 0) actions.push({ title: 'Train a leakage-safe baseline', detail: 'No immutable model version is available.', target: 'models', targetLabel: 'Model performance' })
  if ((readiness?.predictions ?? 0) === 0) actions.push({ title: 'Persist pre-kickoff predictions', detail: 'Upcoming events have no stored cutoff-safe prediction evidence.', target: 'models', targetLabel: 'Model performance' })
  if ((readiness?.non_demo_calibrated_evaluations ?? dashboard.evaluations.filter((run) => !run.is_demo && run.evaluation_status === 'calibrated').length) === 0) actions.push({ title: 'Establish non-demo calibration', detail: 'Value and underdog outputs remain blocked without a qualifying chronological evaluation.', target: 'models', targetLabel: 'Model performance' })
  if ((readiness?.signals ?? dashboard.signals.length) === 0) actions.push({ title: 'Generate gated signals', detail: 'No immutable calibrated signals are stored.', target: 'models', targetLabel: 'Model performance' })
  if ((readiness?.signal_backtests ?? dashboard.backtests.length) === 0) actions.push({ title: 'Run a settled signal replay', detail: 'Bankroll research has no timestamp-valid backtest input.', target: 'backtests', targetLabel: 'Backtesting' })

  return (
    <div className="space-y-6">
      <section className="grid grid-cols-2 border border-zinc-200 bg-white md:grid-cols-4">
        <Metric label="Tracked events" value={dashboard.events.length.toString()} />
        <Metric label="Odds snapshots" value={snapshotCount.toString()} />
        <Metric label="Data providers" value={dashboard.providers.length.toString()} />
        <Metric
          label="Model status"
          value={dashboard.models.length ? "Baseline available" : "Untrained"}
          tone={dashboard.models.length ? "default" : "amber"}
        />
      </section>

      <section aria-labelledby="priority-actions-title">
        <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
          <div><p className="text-xs font-bold uppercase text-emerald-700">Control surface</p><h2 className="mt-1 text-lg font-bold" id="priority-actions-title">Priority actions</h2></div>
          <span className={`rounded-[4px] border px-2 py-1 text-xs font-bold ${actions.length ? 'border-amber-200 bg-amber-50 text-amber-800' : 'border-emerald-200 bg-emerald-50 text-emerald-800'}`}>{actions.length ? `${actions.length} OPEN` : 'ALL CLEAR'}</span>
        </div>
        {actions.length ? <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {actions.map((action) => <article className="flex min-h-36 flex-col border border-zinc-200 bg-white p-4" key={action.title}>
            <h3 className="font-bold">{action.title}</h3>
            <p className="mt-2 flex-1 text-sm leading-6 text-zinc-600">{action.detail}</p>
            <button className="mt-4 self-start border border-zinc-300 px-3 py-2 text-xs font-bold hover:border-zinc-600" onClick={() => onNavigate(action.target)} type="button">Open {action.targetLabel}</button>
          </article>)}
        </div> : <div className="flex items-start gap-3 border-l-4 border-emerald-500 bg-emerald-50 px-4 py-3 text-sm text-emerald-950"><CheckCircle2 aria-hidden="true" className="mt-0.5 shrink-0" size={18} /><p>Collection, historical coverage, model, calibration, signal, and backtest prerequisites are available. Inspect their individual evidence before interpreting any output.</p></div>}
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.5fr)_minmax(320px,0.7fr)]">
        <div>
          <SectionHeading eyebrow="Schedule" title="Tracked football events" />
          <div className="overflow-hidden border-y border-zinc-200 bg-white">
            {dashboard.events.length ? (
              dashboard.events.slice(0, 8).map((event) => (
                <EventRow key={event.id} event={event} onSelect={onSelectEvent} />
              ))
            ) : (
              <EmptyRow text="No events have been imported." />
            )}
          </div>
        </div>

        <div>
          <SectionHeading eyebrow="Integrity" title="Research readiness" />
          <div className="border-y border-zinc-200 bg-white p-5">
            <ReadinessRow label="Stored market data" ready={snapshotCount > 0} />
            <ReadinessRow label="Recent observation" ready={latestOdds !== undefined} detail={formatDateTime(latestOdds ?? null)} />
            <ReadinessRow
              label="Independent model"
              ready={dashboard.models.length > 0}
              detail={dashboard.models[0]?.version ?? "No trained version"}
            />
            <ReadinessRow
              label="Calibration evidence"
              ready={latestEvaluation?.evaluation_status === 'calibrated'}
              detail={
                latestEvaluation
                  ? `${humanizeCode(latestEvaluation.evaluation_status)} / ${metricValue(latestEvaluation.metrics, 'evaluated_events') ?? 0} matches`
                  : 'No completed run'
              }
            />
          </div>
          <div className="mt-4 border-l-4 border-amber-400 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-950">
            Market comparisons are active. Value, underdog, and staking outputs remain blocked until independent predictions and calibration evidence exist.
          </div>
        </div>
      </section>
    </div>
  )
}

function EvaluationPerformance({ evaluations }: { evaluations: EvaluationRun[] }) {
  const latest = evaluations[0]
  if (!latest) {
    return (
      <EmptyState
        title="No chronological evaluations"
        detail="Run evaluate-model for a trained version after importing timestamped historical results."
      />
    )
  }
  const brier = metricValue(latest.metrics, 'brier_score')
  const logLoss = metricValue(latest.metrics, 'log_loss')
  const calibrationError = metricValue(latest.metrics, 'expected_calibration_error')
  const evaluated = metricValue(latest.metrics, 'evaluated_events')
  const candidate = metricValue(latest.metrics, 'candidate_events')
  const uniformBrier = metricValue(latest.benchmarks.uniform ?? {}, 'brier_score')
  const marketBrier = metricValue(latest.benchmarks.market_consensus ?? {}, 'brier_score')

  return (
    <div className="space-y-7">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <SectionHeading eyebrow="Expanding-window replay" title="Chronological calibration" />
        <span className={`rounded-[4px] border px-2.5 py-1 text-xs font-bold ${evaluationStatusClass(latest.evaluation_status)}`}>
          {humanizeCode(latest.evaluation_status)}
        </span>
      </div>

      <section className="grid grid-cols-2 border border-zinc-200 bg-white lg:grid-cols-4">
        <Metric label="Evaluated matches" value={`${evaluated ?? 0} / ${candidate ?? 0}`} />
        <Metric label="1X2 Brier" value={formatScore(brier)} />
        <Metric label="Log loss" value={formatScore(logLoss)} />
        <Metric label="Calibration error" value={calibrationError === null ? '' : `${(calibrationError * 100).toFixed(1)}%`} />
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.4fr)_minmax(300px,0.6fr)]">
        <div>
          <SectionHeading eyebrow="Reliability" title="Probability buckets" />
          <div className="overflow-x-auto border-y border-zinc-200 bg-white">
            <table className="w-full min-w-[680px] text-left text-sm">
              <thead className="bg-zinc-50 text-xs uppercase text-zinc-500">
                <tr><th className="px-4 py-3">Outcome</th><th className="px-4 py-3">Probability band</th><th className="px-4 py-3 text-right">Count</th><th className="px-4 py-3 text-right">Mean forecast</th><th className="px-4 py-3 text-right">Observed</th><th className="px-4 py-3 text-right">Gap</th></tr>
              </thead>
              <tbody>
                {latest.calibration.map((bucket) => (
                  <tr key={`${bucket.selection_code}-${bucket.bucket_index}`} className="border-t border-zinc-100">
                    <td className="px-4 py-3 font-semibold">{humanizeCode(bucket.selection_code)}</td>
                    <td className="px-4 py-3 font-mono text-xs">{(bucket.lower_bound * 100).toFixed(0)}{(bucket.upper_bound * 100).toFixed(0)}%</td>
                    <td className="px-4 py-3 text-right font-mono">{bucket.count}</td>
                    <td className="px-4 py-3 text-right font-mono">{(bucket.mean_predicted * 100).toFixed(1)}%</td>
                    <td className="px-4 py-3 text-right font-mono">{(bucket.observed_frequency * 100).toFixed(1)}%</td>
                    <td className="px-4 py-3 text-right font-mono">{(bucket.absolute_error * 100).toFixed(1)} pp</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div>
          <SectionHeading eyebrow="Benchmarks" title="Proper-score comparison" />
          <div className="border-y border-zinc-200 bg-white p-5">
            <ReadinessRow label="Poisson Brier" ready detail={formatScore(brier)} />
            <ReadinessRow label="Uniform 1X2" ready={brier !== null && uniformBrier !== null && brier < uniformBrier} detail={formatScore(uniformBrier)} />
            <ReadinessRow label="Market consensus" ready={marketBrier !== null} detail={marketBrier === null ? 'No compatible historical odds' : formatScore(marketBrier)} />
            <ReadinessRow label="Evaluation fingerprint" ready detail={latest.fingerprint.slice(0, 16)} />
          </div>
          <p className="mt-3 text-xs leading-5 text-zinc-500">
            Lower Brier and log loss are better. Buckets are one-vs-rest across HOME, DRAW, and AWAY forecasts.
          </p>
        </div>
      </section>

      <section>
        <SectionHeading eyebrow="Registry" title="Completed evaluation runs" />
        <div className="overflow-x-auto border-y border-zinc-200 bg-white">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead className="bg-zinc-50 text-xs uppercase text-zinc-500"><tr><th className="px-4 py-3">Model</th><th className="px-4 py-3">Window end</th><th className="px-4 py-3">Evidence</th><th className="px-4 py-3 text-right">Brier</th><th className="px-4 py-3">Classification</th></tr></thead>
            <tbody>
              {evaluations.map((run) => (
                <tr key={run.id} className="border-t border-zinc-100">
                  <td className="px-4 py-3 font-mono text-xs">{run.model_version}</td>
                  <td className="px-4 py-3">{formatDateTime(run.evaluation_end)}</td>
                  <td className="px-4 py-3">{run.is_demo ? 'DEMO ONLY' : 'EXTERNAL HISTORY'}</td>
                  <td className="px-4 py-3 text-right font-mono">{formatScore(metricValue(run.metrics, 'brier_score'))}</td>
                  <td className="px-4 py-3">{humanizeCode(run.evaluation_status)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {latest.is_demo ? (
        <div className="border-l-4 border-amber-400 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-950">
          This run verifies the software path only. Demo results cannot validate the model or unlock value signals.
        </div>
      ) : null}
    </div>
  )
}

export function SuccessNotice({ message, onDismiss }: { message: string; onDismiss: () => void }) {
  return <div className="fixed right-4 top-20 z-50 flex max-w-sm items-start gap-3 border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-950 shadow-lg" role="status"><CheckCircle2 aria-hidden="true" className="mt-0.5 shrink-0" size={18} /><div className="flex-1"><p className="font-bold">Workflow updated</p><p className="mt-1">{message}</p></div><button aria-label="Dismiss notification" onClick={onDismiss} type="button"><X aria-hidden="true" size={17} /></button></div>
}

export function BacktestResearch({ dashboard, onChanged }: { dashboard: DashboardData; onChanged?: () => Promise<void> | void }) {
  const [modelId, setModelId] = useState(String(dashboard.models[0]?.id ?? ''))
  const [evaluationStart, setEvaluationStart] = useState(toDateTimeInput(dashboard.models[0]?.training_start))
  const [evaluationEnd, setEvaluationEnd] = useState(toDateTimeInput(dashboard.models[0]?.training_end))
  const [signalTypes, setSignalTypes] = useState<string[]>(['VALUE'])
  const [adminKey, setAdminKey] = useState('')
  const [createdRun, setCreatedRun] = useState<DashboardData['backtests'][number] | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [runError, setRunError] = useState<string | null>(null)
  const runs = createdRun ? [createdRun, ...dashboard.backtests.filter((run) => run.id !== createdRun.id)] : dashboard.backtests
  const toggleSignalType = (signalType: string) => setSignalTypes((current) => current.includes(signalType) ? current.filter((item) => item !== signalType) : [...current, signalType])
  const submitBacktest = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); setSubmitting(true); setRunError(null)
    try {
      const run = await runSignalBacktest({ model_version_id: Number(modelId), evaluation_start: new Date(evaluationStart).toISOString(), evaluation_end: new Date(evaluationEnd).toISOString(), signal_types: signalTypes }, adminKey || undefined)
      setCreatedRun(run)
      await onChanged?.()
    } catch (caught) { setRunError(caught instanceof Error ? caught.message : 'Unable to run signal backtest') } finally { setSubmitting(false) }
  }
  return (
    <div className="space-y-10">
      <section>
        <SectionHeading eyebrow="Timestamped signal replay" title="Settled strategy backtests" />
        <form className="mb-6 border-y border-zinc-200 bg-white p-5" onSubmit={(event) => void submitBacktest(event)}><div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5"><label><span className="mb-1.5 block text-xs font-semibold uppercase text-zinc-500">Model version</span><select aria-label="Backtest model" className="h-10 w-full border border-zinc-300 bg-white px-3 text-sm" required value={modelId} onChange={(event) => setModelId(event.target.value)}><option disabled value="">Select model</option>{dashboard.models.map((model) => <option key={model.id} value={model.id}>{model.version}</option>)}</select></label><label><span className="mb-1.5 block text-xs font-semibold uppercase text-zinc-500">Evaluation start</span><input aria-label="Evaluation start" className="h-10 w-full border border-zinc-300 px-3 text-sm" required type="datetime-local" value={evaluationStart} onChange={(event) => setEvaluationStart(event.target.value)} /></label><label><span className="mb-1.5 block text-xs font-semibold uppercase text-zinc-500">Evaluation end</span><input aria-label="Evaluation end" className="h-10 w-full border border-zinc-300 px-3 text-sm" required type="datetime-local" value={evaluationEnd} onChange={(event) => setEvaluationEnd(event.target.value)} /></label><fieldset><legend className="mb-1.5 text-xs font-semibold uppercase text-zinc-500">Stored classifications</legend><div className="flex h-10 items-center gap-3">{['VALUE', 'WATCH', 'PASS'].map((item) => <label key={item} className="flex items-center gap-1 text-xs font-semibold"><input checked={signalTypes.includes(item)} onChange={() => toggleSignalType(item)} type="checkbox" />{item}</label>)}</div></fieldset><label><span className="mb-1.5 block text-xs font-semibold uppercase text-zinc-500">Admin key (memory only)</span><input aria-label="Backtest admin key" autoComplete="off" className="h-10 w-full border border-zinc-300 px-3 text-sm" type="password" value={adminKey} onChange={(event) => setAdminKey(event.target.value)} /></label></div><div className="mt-4 flex items-center gap-3"><button className="rounded-[5px] bg-zinc-900 px-4 py-2 text-sm font-bold text-white disabled:opacity-50" disabled={submitting || !modelId || !evaluationStart || !evaluationEnd || !signalTypes.length} type="submit">{submitting ? 'Running replay…' : 'Run signal backtest'}</button><p className="text-xs text-zinc-500">Only predictions, prices, and signals timestamped before kickoff are eligible.</p></div>{runError ? <div className="mt-4 border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-900" role="alert">{runError}</div> : null}</form>
        {runs.length ? <><BacktestEvidenceAudit run={runs[0]!} /><div className="mt-4 space-y-4">{runs.map((run) => <BacktestRunCard key={run.id} run={run} />)}</div></> : <EmptyState title="No settled signal backtests" detail="Stored calibration runs remain below. Strategy returns require timestamp-valid signals and final results known by the evaluation cutoff." />}
      </section>
      <section>
        <EvaluationPerformance evaluations={dashboard.evaluations} />
      </section>
    </div>
  )
}

function BacktestEvidenceAudit({ run }: { run: DashboardData['backtests'][number] }) {
  const betCount = metricValue(run.metrics, 'bet_count') ?? 0
  const clvCoverage = metricValue(run.metrics, 'closing_line_value_coverage') ?? 0
  const gates = [
    ['External history', !run.is_demo, run.is_demo ? 'Demo replay only.' : 'Non-demo provenance retained.'],
    ['Settled sample', betCount > 0, `${betCount} settled bets reported.`],
    ['Observation reconciliation', run.observations.length === betCount, `${run.observations.length} detailed observation${run.observations.length === 1 ? '' : 's'} for ${betCount} reported bets.`],
    ['Closing-price coverage', clvCoverage === 1, `${(clvCoverage * 100).toFixed(1)}% explicit CLV coverage.`],
  ] as const
  const complete = gates.every(([, passed]) => passed)
  return <section aria-labelledby="backtest-evidence-title"><div className="mb-3"><p className="text-xs font-bold uppercase text-sky-700">Evidence quality</p><h3 className="mt-1 font-bold" id="backtest-evidence-title">Backtest sufficiency audit</h3></div><div className={`border-l-4 p-4 ${complete ? 'border-emerald-500 bg-emerald-50' : 'border-amber-400 bg-amber-50'}`}><p className="font-bold">{complete ? 'Run evidence is internally complete' : 'Run evidence remains incomplete'}</p><div className="mt-3 grid gap-2 md:grid-cols-2">{gates.map(([label, passed, detail]) => <div className="border border-black/10 bg-white/80 p-3 text-xs" key={label}><div className="flex justify-between gap-2"><span className="font-bold">{label}</span><span className={passed ? 'font-bold text-emerald-700' : 'font-bold text-amber-800'}>{passed ? 'PASS' : 'BLOCKED'}</span></div><p className="mt-1 text-zinc-600">{detail}</p></div>)}</div><p className="mt-3 text-xs leading-5">Completeness permits research interpretation only. ROI, profit, and CLV from one replay are not evidence of repeatable profitability.</p></div></section>
}

function BacktestRunCard({ run }: { run: DashboardData['backtests'][number] }) {
  const clvCoverage = metricValue(run.metrics, 'closing_line_value_coverage') ?? 0
  const averageClv = metricValue(run.metrics, 'average_closing_line_value')
  return <article className="border border-zinc-200 bg-white"><div className="grid gap-4 p-5 md:grid-cols-[1fr_repeat(5,110px)] md:items-center"><div><p className="font-bold">#{run.id} / {run.model_version}</p><p className="mt-1 text-xs text-zinc-500">{formatDateTime(run.evaluation_start)} to {formatDateTime(run.evaluation_end)} · {run.is_demo ? 'DEMO ONLY' : 'EXTERNAL HISTORY'} · CLV {(clvCoverage * 100).toFixed(0)}% covered</p><p className="mt-1 font-mono text-xs text-zinc-400">{run.fingerprint}</p></div><BacktestMetric label="Bets" value={String(metricValue(run.metrics, 'bet_count') ?? 0)} /><BacktestMetric label="Profit" value={formatScore(metricValue(run.metrics, 'net_profit_units'))} /><BacktestMetric label="ROI" value={formatSignedPercent(metricValue(run.metrics, 'roi') ?? 0)} /><BacktestMetric label="Drawdown" value={formatScore(metricValue(run.metrics, 'maximum_drawdown_units'))} /><BacktestMetric label="Average CLV" value={averageClv === null ? '—' : formatSignedPercent(averageClv)} /></div><div className="border-t border-zinc-200 bg-zinc-50 px-5 py-3"><span className="rounded-[4px] border border-amber-200 bg-amber-50 px-2 py-1 text-xs font-bold text-amber-800">{humanizeCode(run.evaluation_status)}</span><span className="ml-2 text-xs text-zinc-500">Created {formatDateTime(run.created_at)}</span></div>{run.observations.length ? <details className="border-t border-zinc-200"><summary className="cursor-pointer px-5 py-3 text-sm font-bold">Inspect {run.observations.length} settled observations</summary><div className="overflow-x-auto"><table className="w-full min-w-[1050px] text-left text-xs"><thead className="bg-zinc-50 uppercase text-zinc-500"><tr><th className="px-4 py-3">Event / selection</th><th className="px-4 py-3">Prediction</th><th className="px-4 py-3">Taken price</th><th className="px-4 py-3">Closing evidence</th><th className="px-4 py-3 text-right">CLV</th><th className="px-4 py-3 text-right">Model / lower</th><th className="px-4 py-3">Settlement</th><th className="px-4 py-3 text-right">Profit</th></tr></thead><tbody>{run.observations.map((item) => <tr key={item.id} className="border-t border-zinc-100"><td className="px-4 py-3">Event #{item.event_id} · {humanizeCode(item.selection_code)}</td><td className="px-4 py-3">#{item.prediction_id}<br />{formatDateTime(item.predicted_at)}</td><td className="px-4 py-3">#{item.odds_snapshot_id}<br /><span className="font-mono">{item.decimal_odds.toFixed(2)}</span></td><td className="px-4 py-3">{item.closing_odds_snapshot_id ? <>#{item.closing_odds_snapshot_id}<br /><span className="font-mono">{item.closing_decimal_odds?.toFixed(2)}</span> · {formatDateTime(item.closing_observed_at ?? null)}</> : 'Unavailable'}</td><td className="px-4 py-3 text-right font-mono">{item.closing_line_value == null ? '—' : formatSignedPercent(item.closing_line_value)}</td><td className="px-4 py-3 text-right font-mono">{(item.model_probability * 100).toFixed(1)}% / {(item.lower_probability * 100).toFixed(1)}%</td><td className="px-4 py-3">{humanizeCode(item.settlement)}<br />{formatDateTime(item.settled_at)}</td><td className="px-4 py-3 text-right font-mono">{item.profit_units >= 0 ? '+' : ''}{item.profit_units.toFixed(2)}</td></tr>)}</tbody></table></div></details> : <p className="border-t border-zinc-200 px-5 py-3 text-xs text-zinc-500">No eligible settled observations were included in this run.</p>}</article>
}

function BacktestMetric({ label, value }: { label: string; value: string }) { return <div><p className="text-xs font-semibold uppercase text-zinc-500">{label}</p><p className="mt-1 font-mono font-bold">{value}</p></div> }
function toDateTimeInput(value: string | undefined): string { return value ? new Date(value).toISOString().slice(0, 16) : '' }

export function SignalResearch({ dashboard, mode }: { dashboard: DashboardData; mode: 'value' | 'underdog' }) {
  const signals = mode === 'underdog' ? dashboard.underdogs : dashboard.signals
  const title = mode === 'underdog' ? 'Positive-EV team underdogs' : 'Immutable value recommendations'
  const valueCount = signals.filter((signal) => signal.signal_type === 'VALUE').length
  const watchCount = signals.filter((signal) => signal.signal_type === 'WATCH').length
  const averageEdge = signals.length
    ? signals.reduce((sum, signal) => sum + signal.probability_edge, 0) / signals.length
    : null

  if (!signals.length) {
    return (
      <div className="space-y-5">
        <EmptyState
          title={mode === 'underdog' ? 'No qualified underdogs' : 'No stored value signals'}
          detail="Signals appear only after a non-demo model passes chronological calibration and its prediction is joined to complete compatible pre-kickoff odds."
        />
        <div className="border-l-4 border-amber-400 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-950">
          Long odds and demo prices are never treated as value. Generate signals through the protected API after valid evidence exists.
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-7">
      <SectionHeading eyebrow={mode === 'underdog' ? 'Team outcomes only' : 'Calibrated model versus market'} title={title} />
      <section className="grid grid-cols-2 border border-zinc-200 bg-white md:grid-cols-4">
        <Metric label={mode === 'underdog' ? 'Stored signals' : 'Recommendations'} value={signals.length.toString()} />
        <Metric label="Value" value={valueCount.toString()} />
        <Metric label="Watch" value={watchCount.toString()} />
        <Metric label="Average edge" value={averageEdge === null ? '' : `${(averageEdge * 100).toFixed(1)} pp`} />
      </section>

      <div className="overflow-x-auto border-y border-zinc-200 bg-white">
        <table className="w-full min-w-[1120px] text-left text-sm">
          <thead className="bg-zinc-50 text-xs uppercase text-zinc-500">
            <tr><th className="px-4 py-3">Event / selection</th><th className="px-4 py-3">Classification</th><th className="px-4 py-3">Best price</th><th className="px-4 py-3 text-right">Model</th><th className="px-4 py-3 text-right">Market</th><th className="px-4 py-3 text-right">Edge</th><th className="px-4 py-3 text-right">EV</th><th className="px-4 py-3 text-right">Lower EV</th><th className="px-4 py-3 text-right">Confidence</th><th className="px-4 py-3">Evidence</th></tr>
          </thead>
          <tbody>
            {signals.map((signal) => (
              <SignalRow key={signal.id} dashboard={dashboard} signal={signal} />
            ))}
          </tbody>
        </table>
      </div>

      <div className="border-l-4 border-sky-500 bg-sky-50 px-4 py-3 text-sm leading-6 text-sky-950">
        Model edge, line-shopping price improvement, and bookmaker margin are separate quantities. A VALUE label is conditional on the stored price, calibration run, uncertainty bound, freshness, and movement checks.
      </div>
    </div>
  )
}

export function ArbitrageResearch({ dashboard, onChanged }: { dashboard: DashboardData; onChanged?: () => Promise<void> | void }) {
  const [eventId, setEventId] = useState(String(dashboard.events[0]?.id ?? ''))
  const [budget, setBudget] = useState('100')
  const [currency, setCurrency] = useState('EUR')
  const [staleSeconds, setStaleSeconds] = useState('300')
  const [adminKey, setAdminKey] = useState('')
  const [calculated, setCalculated] = useState<typeof dashboard.arbitrage | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [calculationError, setCalculationError] = useState<string | null>(null)
  const opportunities = calculated ?? dashboard.arbitrage
  const executable = opportunities.filter((opportunity) => opportunity.status === 'executable')
  const blocked = opportunities.filter((opportunity) => opportunity.status !== 'executable')
  const bestExecutable = executable.reduce(
    (best, opportunity) => best === null || opportunity.net_profit > best.net_profit ? opportunity : best,
    null as (typeof executable)[number] | null,
  )

  const submitCalculation = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setSubmitting(true)
    setCalculationError(null)
    try {
      const result = await calculateArbitrage({
        event_id: Number(eventId), budget: Number(budget), currency,
        odds_stale_after_seconds: Number(staleSeconds), tax_max_age_days: 365,
        constraint_max_age_minutes: 1440,
      }, adminKey || undefined)
      setCalculated(result.opportunities)
      await onChanged?.()
    } catch (caught) {
      setCalculationError(caught instanceof Error ? caught.message : 'Unable to calculate arbitrage')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-7">
      <SectionHeading eyebrow="Tax and constraint aware" title="Stored arbitrage calculations" />
      <Suspense fallback={<InlineLoading text="Loading arbitrage settings" />}><ArbitrageSettings onChanged={onChanged} /></Suspense>
      <form className="border-y border-zinc-200 bg-white p-5" onSubmit={(event) => void submitCalculation(event)}>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
          <label><span className="mb-1.5 block text-xs font-semibold uppercase text-zinc-500">Event</span><select aria-label="Arbitrage event" className="h-10 w-full border border-zinc-300 bg-white px-3 text-sm" required value={eventId} onChange={(event) => setEventId(event.target.value)}><option disabled value="">Select event</option>{dashboard.events.map((item) => <option key={item.id} value={item.id}>{item.home_team} vs {item.away_team}</option>)}</select></label>
          <label><span className="mb-1.5 block text-xs font-semibold uppercase text-zinc-500">Research budget</span><input aria-label="Research budget" className="h-10 w-full border border-zinc-300 px-3 text-sm" min="0.01" required step="0.01" type="number" value={budget} onChange={(event) => setBudget(event.target.value)} /></label>
          <label><span className="mb-1.5 block text-xs font-semibold uppercase text-zinc-500">Currency</span><input aria-label="Currency" className="h-10 w-full border border-zinc-300 px-3 text-sm uppercase" maxLength={3} minLength={3} required value={currency} onChange={(event) => setCurrency(event.target.value.toUpperCase())} /></label>
          <label><span className="mb-1.5 block text-xs font-semibold uppercase text-zinc-500">Price max age (seconds)</span><input aria-label="Price max age (seconds)" className="h-10 w-full border border-zinc-300 px-3 text-sm" min="1" required type="number" value={staleSeconds} onChange={(event) => setStaleSeconds(event.target.value)} /></label>
          <label><span className="mb-1.5 block text-xs font-semibold uppercase text-zinc-500">Admin key (memory only)</span><input aria-label="Admin key" autoComplete="off" className="h-10 w-full border border-zinc-300 px-3 text-sm" type="password" value={adminKey} onChange={(event) => setAdminKey(event.target.value)} /></label>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-3"><button className="rounded-[5px] bg-zinc-900 px-4 py-2 text-sm font-bold text-white disabled:opacity-50" disabled={submitting || !eventId} type="submit">{submitting ? 'Calculating…' : 'Calculate stored markets'}</button><p className="text-xs text-zinc-500">The key is sent only with this request and is not persisted. Local development may leave it blank.</p></div>
        {calculationError ? <div className="mt-4 border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-900" role="alert">{calculationError}</div> : null}
      </form>
      <section className="grid grid-cols-2 border border-zinc-200 bg-white md:grid-cols-4">
        <Metric label="Calculations" value={opportunities.length.toString()} />
        <Metric label="Executable" value={executable.length.toString()} />
        <Metric label="Blocked" value={blocked.length.toString()} tone={blocked.length ? 'amber' : 'default'} />
        <Metric
          label="Best net profit"
          value={bestExecutable ? formatMoney(bestExecutable.net_profit, bestExecutable.currency) : '—'}
        />
      </section>

      <div className="space-y-5">
        {!opportunities.length ? <EmptyState title="No stored arbitrage calculations" detail="Choose an event and run the protected calculation against its complete compatible market snapshots." /> : null}
        {opportunities.map((opportunity) => {
          const event = dashboard.events.find((candidate) => candidate.id === opportunity.event_id)
          return (
            <article key={opportunity.id} className="border border-zinc-200 bg-white">
              <div className="flex flex-wrap items-start justify-between gap-4 border-b border-zinc-200 p-5">
                <div>
                  <p className="text-xs font-bold uppercase text-emerald-700">{humanizeCode(opportunity.market_type)} / {humanizeCode(opportunity.period)}</p>
                  <h3 className="mt-1 text-lg font-bold">{event ? `${event.home_team} vs ${event.away_team}` : `Event ${opportunity.event_id}`}</h3>
                  <p className="mt-1 text-xs text-zinc-500">Calculated {formatDateTime(opportunity.calculated_at)} / fingerprint {opportunity.fingerprint.slice(0, 12)}</p>
                </div>
                <span className={`rounded-[4px] border px-2.5 py-1 text-xs font-bold ${arbitrageStatusClass(opportunity.status)}`}>
                  {opportunity.status.toUpperCase()}
                </span>
              </div>

              <div className="grid grid-cols-2 border-b border-zinc-200 md:grid-cols-5">
                <ArbitrageMetric label="Cash outlay" value={formatMoney(opportunity.total_cash_outlay, opportunity.currency)} />
                <ArbitrageMetric label="Minimum payout" value={formatMoney(opportunity.minimum_net_payout, opportunity.currency)} />
                <ArbitrageMetric label="Worst-case profit" value={formatMoney(opportunity.net_profit, opportunity.currency)} />
                <ArbitrageMetric label="Net ROI" value={formatSignedPercent(opportunity.net_roi)} />
                <ArbitrageMetric label="Inverse sum" value={opportunity.inverse_sum.toFixed(4)} />
              </div>
              <ArbitrageExecutionChecklist opportunity={opportunity} />

              <div className="overflow-x-auto">
                <table className="w-full min-w-[850px] text-left text-sm">
                  <thead className="bg-zinc-50 text-xs uppercase text-zinc-500">
                    <tr><th className="px-4 py-3">Outcome</th><th className="px-4 py-3">Bookmaker</th><th className="px-4 py-3 text-right">Odds</th><th className="px-4 py-3 text-right">Stake</th><th className="px-4 py-3 text-right">Costs</th><th className="px-4 py-3 text-right">Net payout</th><th className="px-4 py-3">Provenance</th></tr>
                  </thead>
                  <tbody>
                    {opportunity.legs.map((leg) => (
                      <tr key={leg.id} className="border-t border-zinc-100">
                        <td className="px-4 py-3 font-semibold">{leg.selection_name}</td>
                        <td className="px-4 py-3">{leg.bookmaker}</td>
                        <td className="px-4 py-3 text-right font-mono">{leg.decimal_odds.toFixed(2)}</td>
                        <td className="px-4 py-3 text-right font-mono">{formatMoney(leg.stake, opportunity.currency)}</td>
                        <td className="px-4 py-3 text-right font-mono">{formatMoney(leg.taxes_and_fees, opportunity.currency)}</td>
                        <td className="px-4 py-3 text-right font-mono">{formatMoney(leg.net_payout, opportunity.currency)}</td>
                        <td className="px-4 py-3 text-xs text-zinc-500">Snapshot #{leg.odds_snapshot_id} / tax #{leg.tax_profile_id ?? 'missing'} / limit #{leg.bookmaker_constraint_id ?? 'missing'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="grid gap-3 border-t border-zinc-200 bg-zinc-50 px-5 py-4 text-xs md:grid-cols-[1fr_auto] md:items-start">
                <div>
                  <p className="font-semibold text-zinc-700">Tax {humanizeCode(opportunity.tax_status)} / constraints {humanizeCode(opportunity.constraint_status)} / prices {humanizeCode(opportunity.freshness_status)}</p>
                  {opportunity.risks.map((risk) => <p key={risk} className="mt-1 text-amber-800">{risk}</p>)}
                </div>
                <p className="font-semibold text-zinc-500">Pre-acceptance calculation only</p>
              </div>
            </article>
          )
        })}
      </div>

      {!opportunities.length ? <div className="border-l-4 border-amber-400 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-950">Gross inverse-sum opportunities are insufficient. Missing or stale tax rules, stake limits, prices, or settlement compatibility must block execution.</div> : null}

      <div className="border-l-4 border-rose-500 bg-rose-50 px-4 py-3 text-sm leading-6 text-rose-950">
        “Executable” means the stored calculation passed configured checks at its cutoff. It is never a guarantee that every bookmaker leg will be accepted and honoured.
      </div>
    </div>
  )
}

function ArbitrageExecutionChecklist({ opportunity }: { opportunity: DashboardData['arbitrage'][number] }) {
  const expectedLegs = opportunity.market_type === 'MATCH_RESULT' ? 3 : ['TOTAL_GOALS', 'BOTH_TEAMS_TO_SCORE'].includes(opportunity.market_type) ? 2 : null
  const checks = [
    ['Complete outcome set', expectedLegs !== null && opportunity.legs.length === expectedLegs, expectedLegs === null ? 'Market outcome count is not independently recognized.' : `${opportunity.legs.length} of ${expectedLegs} required outcomes stored.`],
    ['Settlement identity', Boolean(opportunity.settlement_rule_key), opportunity.settlement_rule_key || 'Missing settlement rule.'],
    ['Tax evidence', opportunity.tax_status === 'verified', humanizeCode(opportunity.tax_status)],
    ['Stake constraints', opportunity.constraint_status === 'verified', humanizeCode(opportunity.constraint_status)],
    ['Stored price freshness', opportunity.freshness_status === 'fresh', humanizeCode(opportunity.freshness_status)],
    ['Worst-case net profit', opportunity.net_profit > 0, opportunity.net_profit > 0 ? 'Positive after stored taxes, fees, limits, and rounding.' : 'Not positive after stored costs.'],
  ] as const
  return <section className="border-b border-zinc-200 bg-zinc-50 p-4" aria-label="Arbitrage execution checklist"><div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">{checks.map(([label, passed, detail]) => <div className="border border-zinc-200 bg-white p-3 text-xs" key={label}><div className="flex justify-between gap-2"><span className="font-bold">{label}</span><span className={passed ? 'font-bold text-emerald-700' : 'font-bold text-amber-800'}>{passed ? 'PASS' : 'BLOCKED'}</span></div><p className="mt-1 text-zinc-600">{detail}</p></div>)}<div className="border border-rose-200 bg-rose-50 p-3 text-xs"><div className="flex justify-between gap-2"><span className="font-bold">Live price recheck</span><span className="font-bold text-rose-800">REQUIRED</span></div><p className="mt-1 text-rose-800">Reconfirm every price, limit, and accepted leg immediately before submission.</p></div></div></section>
}

function ArbitrageMetric({ label, value }: { label: string; value: string }) {
  return <div className="border-r border-b border-zinc-200 p-4 last:border-r-0 md:border-b-0"><p className="text-xs font-semibold uppercase text-zinc-500">{label}</p><p className="mt-1 font-mono text-base font-bold">{value}</p></div>
}

function formatMoney(value: number, currency: string): string {
  return `${currency} ${value.toFixed(2)}`
}

function arbitrageStatusClass(status: string): string {
  return status === 'executable'
    ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
    : 'border-amber-200 bg-amber-50 text-amber-800'
}

function SignalRow({ dashboard, signal }: { dashboard: DashboardData; signal: ValueSignal }) {
  const event = dashboard.events.find((candidate) => candidate.id === signal.event_id)
  return (
    <tr className="border-t border-zinc-100 align-top">
      <td className="px-4 py-3">
        <p className="font-semibold">{event ? `${event.home_team} vs ${event.away_team}` : `Event ${signal.event_id}`}</p>
        <p className="mt-1 text-xs text-zinc-500">{signal.selection_name} / {humanizeCode(signal.market_type)}</p>
      </td>
      <td className="px-4 py-3"><span className={`rounded-[4px] border px-2 py-1 text-xs font-bold ${signalStatusClass(signal.signal_type)}`}>{humanizeCode(signal.signal_type)}</span></td>
      <td className="px-4 py-3"><p className="font-mono font-semibold">{signal.offered_odds.toFixed(2)}</p><p className="mt-1 text-xs text-zinc-500">{signal.bookmaker}</p></td>
      <td className="px-4 py-3 text-right font-mono">{(signal.model_probability * 100).toFixed(1)}%</td>
      <td className="px-4 py-3 text-right font-mono">{(signal.market_fair_probability * 100).toFixed(1)}%</td>
      <td className="px-4 py-3 text-right font-mono">{formatSignedPercent(signal.probability_edge)}</td>
      <td className="px-4 py-3 text-right font-mono">{formatSignedPercent(signal.expected_value)}</td>
      <td className="px-4 py-3 text-right font-mono">{formatSignedPercent(signal.lower_expected_value)}</td>
      <td className="px-4 py-3 text-right font-mono">{(signal.confidence * 100).toFixed(0)}%</td>
      <td className="max-w-xs px-4 py-3 text-xs leading-5 text-zinc-600">
        <p>{signal.reasons[0] ?? 'Stored quantitative classification.'}</p>
        <p className="mt-1 text-zinc-400">Eval #{signal.evaluation_run_id} / {signal.bookmaker_count} books / {signal.odds_age_minutes.toFixed(0)}m old</p>
        {signal.risks[0] ? <p className="mt-1 text-amber-700">{signal.risks[0]}</p> : null}
      </td>
    </tr>
  )
}

function formatSignedPercent(value: number): string {
  return `${value >= 0 ? '+' : ''}${(value * 100).toFixed(1)}%`
}

function signalStatusClass(status: string): string {
  if (status === 'VALUE') return 'border-emerald-200 bg-emerald-50 text-emerald-800'
  if (status === 'PASS') return 'border-zinc-200 bg-zinc-50 text-zinc-700'
  if (status === 'INSUFFICIENT_DATA') return 'border-amber-200 bg-amber-50 text-amber-800'
  return 'border-sky-200 bg-sky-50 text-sky-800'
}

function metricValue(metrics: Record<string, unknown>, key: string): number | null {
  const value = metrics[key]
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function formatScore(value: number | null): string {
  return value === null ? '' : value.toFixed(4)
}

function evaluationStatusClass(status: string): string {
  if (status === 'calibrated') return 'border-emerald-200 bg-emerald-50 text-emerald-800'
  if (status === 'calibration_failed') return 'border-rose-200 bg-rose-50 text-rose-800'
  return 'border-amber-200 bg-amber-50 text-amber-800'
}

function EventSelector({ events, selectedEventId, onSelectEvent }: Pick<ActiveViewProps, 'selectedEventId' | 'onSelectEvent'> & { events: EventSummary[] }) {
  return (
    <label className="block max-w-xl">
      <span className="mb-1.5 block text-xs font-semibold uppercase text-zinc-500">Event</span>
      <select
        className="h-10 w-full rounded-[5px] border border-zinc-300 bg-white px-3 text-sm font-medium outline-none focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100"
        onChange={(event) => onSelectEvent(Number(event.target.value))}
        value={selectedEventId ?? ''}
      >
        {events.map((event) => (
          <option key={event.id} value={event.id}>
            {event.home_team} vs {event.away_team} - {event.competition}
          </option>
        ))}
      </select>
    </label>
  )
}

function OddsComparison(props: ActiveViewProps) {
  return (
    <div className="w-full min-w-0 max-w-[calc(100vw-2rem)] space-y-6 overflow-hidden lg:max-w-none">
      <EventSelector events={props.dashboard.events} onSelectEvent={props.onSelectEvent} selectedEventId={props.selectedEventId} />
      {props.comparisonLoading ? <InlineLoading text="Loading price comparison" /> : null}
      {!props.comparisonLoading && props.comparisonError ? <InlineError message={props.comparisonError} /> : null}
      {!props.comparisonLoading && !props.comparisonError ? props.markets.map((market) => (
        <section key={market.market_id} className="min-w-0 space-y-4">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <SectionHeading eyebrow={`${market.period} / ${market.currency}`} title={humanizeCode(market.market_type)} />
            <span className="max-w-full text-xs text-zinc-500">Proportional and power de-vig available</span>
          </div>
          <div className="grid min-w-0 gap-5 bg-white py-4 xl:grid-cols-[minmax(0,1fr)_340px]">
            <QuantPriceTable market={market} />
            <div className="min-w-0 border-l-0 border-zinc-200 px-4 xl:border-l">
              <h3 className="mb-2 text-sm font-semibold">Best available prices</h3>
              <Suspense fallback={<div className="h-64 animate-pulse bg-zinc-100" aria-label="Loading chart" />}>
                <BestPriceChart market={market} />
              </Suspense>
            </div>
          </div>
        </section>
      )) : null}
      {!props.comparisonLoading && !props.comparisonError && !props.markets.length ? <EmptyState title="No comparable prices" detail="The selected event has no complete bookmaker snapshot as of now." /> : null}
    </div>
  )
}

function Metric({ label, value, tone = 'default' }: { label: string; value: string; tone?: 'default' | 'amber' }) {
  return <div className="min-h-24 border-r border-b border-zinc-200 p-4 last:border-r-0 md:border-b-0"><p className="text-xs font-semibold uppercase text-zinc-500">{label}</p><p className={`mt-2 text-2xl font-bold ${tone === 'amber' ? 'text-amber-700' : 'text-zinc-950'}`}>{value}</p></div>
}

function SectionHeading({ eyebrow, title }: { eyebrow: string; title: string }) {
  return <div className="mb-3"><p className="text-xs font-bold uppercase text-emerald-700">{eyebrow}</p><h2 className="mt-1 text-lg font-bold">{title}</h2></div>
}

function EventRow({ event, onSelect }: { event: EventSummary; onSelect: (eventId: number) => void }) {
  const ageSeconds = event.latest_odds_at ? Math.max(0, Math.floor((DASHBOARD_OPENED_AT - new Date(event.latest_odds_at).getTime()) / 1000)) : 0
  return <button className="grid w-full gap-2 border-b border-zinc-100 px-4 py-3 text-left hover:bg-zinc-50 last:border-0 sm:grid-cols-[1fr_auto_auto] sm:items-center" onClick={() => { onSelect(event.id); navigateTo('event') }} type="button"><div><p className="font-semibold">{event.home_team} <span className="font-normal text-zinc-400">vs</span> {event.away_team}</p><p className="mt-1 text-xs text-zinc-500">{event.competition} / {formatDateTime(event.kickoff_at)}</p></div><span className="text-xs font-medium text-zinc-500">{event.is_demo ? 'DEMO' : event.status.toUpperCase()}</span>{event.latest_odds_at ? <FreshnessBadge seconds={ageSeconds} stale={ageSeconds > 300} /> : <span className="text-xs text-zinc-400">No odds</span>}</button>
}

function ReadinessRow({ label, ready, detail }: { label: string; ready: boolean; detail?: string }) {
  return <div className="flex items-center justify-between gap-4 border-b border-zinc-100 py-3 first:pt-0 last:border-0 last:pb-0"><div><p className="text-sm font-semibold">{label}</p>{detail ? <p className="mt-0.5 text-xs text-zinc-500">{detail}</p> : null}</div><span className={`rounded-[4px] border px-2 py-1 text-xs font-bold ${ready ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-amber-200 bg-amber-50 text-amber-800'}`}>{ready ? 'READY' : 'BLOCKED'}</span></div>
}

function EmptyState({ title, detail }: { title: string; detail: string }) {
  return <div className="border-y border-zinc-200 bg-white px-6 py-12 text-center"><BarChart3 aria-hidden="true" className="mx-auto text-zinc-400" size={28} /><h2 className="mt-3 font-bold">{title}</h2><p className="mx-auto mt-2 max-w-md text-sm text-zinc-500">{detail}</p></div>
}

function EmptyRow({ text }: { text: string }) {
  return <div className="px-4 py-8 text-center text-sm text-zinc-500">{text}</div>
}

function LoadingState() {
  return <div className="grid min-h-[420px] place-items-center" role="status"><div className="text-center"><RefreshCw aria-hidden="true" className="mx-auto animate-spin text-emerald-700" size={24} /><p className="mt-3 font-semibold">Loading your research workspace</p><p className="mt-1 text-sm text-zinc-600">Fetching fixtures, timestamped prices, and model evidence.</p></div></div>
}

function ConnectionError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return <div className="border border-rose-200 bg-rose-50 p-5"><div className="flex items-start gap-3"><AlertTriangle aria-hidden="true" className="mt-0.5 text-rose-700" size={20} /><div><h2 className="font-bold text-rose-950">API unavailable</h2><p className="mt-1 text-sm text-rose-800">{message}</p><button className="mt-3 rounded-[5px] bg-rose-800 px-3 py-2 text-sm font-semibold text-white hover:bg-rose-900" onClick={onRetry} type="button">Retry connection</button></div></div></div>
}

export function ResourceErrors({ errors }: { errors: DashboardData['resource_errors'] }) {
  const entries = Object.entries(errors)
  if (!entries.length) return null
  return (
    <div className="mb-5 border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950" role="status">
      <div className="flex items-start gap-3">
        <AlertTriangle aria-hidden="true" className="mt-0.5 shrink-0" size={19} />
        <div>
          <p className="font-bold">Some dashboard resources are unavailable</p>
          <p className="mt-1 leading-6">Available sections remain usable. Retry after checking: {entries.map(([resource]) => humanizeCode(resource)).join(', ')}.</p>
        </div>
      </div>
    </div>
  )
}

export function InlineLoading({ text }: { text: string }) {
  return <div className="flex items-center justify-center gap-2 px-5 py-10 text-sm text-zinc-500"><RefreshCw aria-hidden="true" className="animate-spin" size={17} />{text}</div>
}

export function InlineError({ message }: { message: string }) {
  return <div className="m-4 border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-900" role="alert"><strong>Unable to load prices.</strong> {message}<p className="mt-2 text-rose-800">The selected match is preserved. Use the refresh button in the page header to try again.</p></div>
}

export default App
