import {
  Activity,
  AlertTriangle,
  BarChart3,
  Beaker,
  BookOpen,
  CalendarDays,
  CircleDollarSign,
  Database,
  FlaskConical,
  Gauge,
  GitCompareArrows,
  LineChart,
  RefreshCw,
  ScanSearch,
  ShieldCheck,
  TrendingUp,
} from 'lucide-react'
import { lazy, Suspense, useCallback, useEffect, useState } from 'react'
import type { FormEvent } from 'react'

import { calculateArbitrage, loadComparison, loadDashboard, runSignalBacktest } from './api/client'
import { FreshnessBadge } from './components/FreshnessBadge'
import { BetBuilderLab } from './components/BetBuilderLab'
import { BankrollResearch } from './components/BankrollResearch'
import { MatchdayResearch } from './components/MatchdayResearch'
import { UnderdogScanner } from './components/UnderdogScanner'
import { ValueOpportunities } from './components/ValueOpportunities'
import { EventMarkets } from './components/EventMarkets'
import { ModelPerformance } from './components/ModelPerformance'
import { DataOperations } from './components/DataOperations'
import { ArbitrageSettings } from './components/ArbitrageSettings'
import { WorkflowReadiness } from './components/WorkflowReadiness'
import { QuantPriceTable } from './components/QuantPriceTable'
import { formatDateTime, humanizeCode } from './lib/format'
import { chooseDefaultEventId } from './lib/events'
import type { DashboardData, EvaluationRun, EventSummary, MarketComparison, ValueSignal } from './types'

type ViewKey =
  | 'overview'
  | 'matchday'
  | 'opportunities'
  | 'underdogs'
  | 'arbitrage'
  | 'event'
  | 'comparison'
  | 'builder'
  | 'models'
  | 'backtests'
  | 'bankroll'
  | 'data'
  | 'methodology'

const navigation = [
  { key: 'overview', label: 'Overview', icon: Gauge },
  { key: 'matchday', label: 'Matchday', icon: CalendarDays },
  { key: 'opportunities', label: 'Value opportunities', icon: TrendingUp },
  { key: 'underdogs', label: 'Underdog scanner', icon: ScanSearch },
  { key: 'arbitrage', label: 'Arbitrage', icon: ShieldCheck },
  { key: 'event', label: 'Event markets', icon: CalendarDays },
  { key: 'comparison', label: 'Odds comparison', icon: GitCompareArrows },
  { key: 'builder', label: 'Bet Builder Lab', icon: Beaker },
  { key: 'models', label: 'Model performance', icon: LineChart },
  { key: 'backtests', label: 'Backtesting', icon: FlaskConical },
  { key: 'bankroll', label: 'Bankroll research', icon: CircleDollarSign },
  { key: 'data', label: 'Data operations', icon: Database },
  { key: 'methodology', label: 'Methodology', icon: BookOpen },
] as const

const BestPriceChart = lazy(async () => {
  const module = await import('./components/BestPriceChart')
  return { default: module.BestPriceChart }
})

const DASHBOARD_OPENED_AT = Date.now()

function navigateTo(view: ViewKey) {
  window.location.hash = view
}

function readView(): ViewKey {
  const candidate = window.location.hash.slice(1)
  return navigation.some((item) => item.key === candidate) ? (candidate as ViewKey) : 'overview'
}

function App() {
  const [view, setView] = useState<ViewKey>(readView)
  const [dashboard, setDashboard] = useState<DashboardData | null>(null)
  const [selectedEventId, setSelectedEventId] = useState<number | null>(null)
  const [markets, setMarkets] = useState<MarketComparison[]>([])
  const [comparisonLoading, setComparisonLoading] = useState(false)
  const [comparisonError, setComparisonError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const loaded = await loadDashboard()
      setDashboard(loaded)
      setSelectedEventId((current) => current ?? chooseDefaultEventId(loaded.events))
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to reach the OddsQuant API')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    let active = true
    void loadDashboard()
      .then((loaded) => {
        if (!active) return
        setDashboard(loaded)
        setSelectedEventId(chooseDefaultEventId(loaded.events))
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
    const onHashChange = () => setView(readView())
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

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
    navigateTo(next)
    setView(next)
  }

  return (
    <div className="min-h-screen bg-[#f4f6f5] text-zinc-900">
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-64 border-r border-zinc-800 bg-[#15191e] text-zinc-100 lg:flex lg:flex-col">
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
          {navigation.map((item) => {
            const Icon = item.icon
            const active = view === item.key
            return (
              <button
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
        </nav>
        <div className="border-t border-zinc-800 p-4 text-xs leading-5 text-zinc-500">
          Research only. No automated betting.
        </div>
      </aside>

      <div className="lg:pl-64">
        <header className="sticky top-0 z-10 border-b border-zinc-200 bg-white/95 backdrop-blur">
          <div className="flex h-16 items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
            <div className="min-w-0">
              <h1 className="truncate text-lg font-bold">{navigation.find((item) => item.key === view)?.label}</h1>
              <p className="truncate text-xs text-zinc-500">Point-in-time market and model research</p>
            </div>
            <div className="flex items-center gap-2">
              <span className="hidden rounded-[4px] border border-sky-200 bg-sky-50 px-2 py-1 text-xs font-semibold text-sky-800 sm:inline-flex">
                {dashboard?.status.data_mode === 'demo_or_user_supplied' ? 'Demo / user data' : dashboard?.status.data_mode ?? 'Connecting'}
              </span>
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
          <div className="overflow-x-auto border-t border-zinc-100 px-3 py-2 lg:hidden">
            <div className="flex min-w-max gap-1">
              {navigation.map((item) => (
                <button
                  key={item.key}
                  className={`rounded-[4px] px-3 py-1.5 text-xs font-semibold ${view === item.key ? 'bg-zinc-900 text-white' : 'text-zinc-600'}`}
                  onClick={() => selectView(item.key)}
                  type="button"
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>
        </header>

        <main className="px-4 py-5 sm:px-6 lg:px-8 lg:py-7">
          {error ? <ConnectionError message={error} onRetry={() => void refresh()} /> : null}
          {!error && dashboard ? (
            <>
              <ResourceErrors errors={dashboard.resource_errors} />
              <WorkflowReadiness dashboard={dashboard} view={view} onNavigate={(target) => selectView(target as ViewKey)} />
              <ActiveView
                comparisonError={comparisonError}
                comparisonLoading={comparisonLoading}
                dashboard={dashboard}
                markets={markets}
                onSelectEvent={setSelectedEventId}
                selectedEventId={selectedEventId}
                view={view}
              />
            </>
          ) : null}
          {!error && !dashboard ? <LoadingState /> : null}
        </main>

        <footer className="border-t border-zinc-200 bg-white px-4 py-4 text-xs leading-5 text-zinc-500 sm:px-6 lg:px-8">
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
  onSelectEvent: (eventId: number) => void
}

function ActiveView(props: ActiveViewProps) {
  switch (props.view) {
    case 'overview':
      return <Overview dashboard={props.dashboard} onSelectEvent={props.onSelectEvent} />
    case 'matchday':
      return <MatchdayResearch onSelectEvent={props.onSelectEvent} />
    case 'event':
      return <EventMarkets dashboard={props.dashboard} events={props.dashboard.events} selectedEventId={props.selectedEventId} markets={props.markets} loading={props.comparisonLoading} error={props.comparisonError} onSelectEvent={props.onSelectEvent} onOpenComparison={() => navigateTo('comparison')} />
    case 'comparison':
      return <OddsComparison {...props} />
    case 'data':
      return <DataOperations dashboard={props.dashboard} />
    case 'methodology':
      return <Methodology />
    case 'opportunities':
      return <ValueOpportunities dashboard={props.dashboard} onOpenEvent={(eventId) => { props.onSelectEvent(eventId); navigateTo('event') }} />
    case 'underdogs':
      return <UnderdogScanner dashboard={props.dashboard} onOpenEvent={(eventId) => { props.onSelectEvent(eventId); navigateTo('event') }} />
    case 'arbitrage':
      return <ArbitrageResearch dashboard={props.dashboard} />
    case 'builder':
      return <BetBuilderLab events={props.dashboard.events} onSelectEvent={props.onSelectEvent} selectedEventId={props.selectedEventId} />
    case 'models':
      return <ModelPerformance dashboard={props.dashboard} />
    case 'backtests':
      return <BacktestResearch dashboard={props.dashboard} />
    case 'bankroll':
      return <BankrollResearch backtests={props.dashboard.backtests} />
  }
}

function Overview({ dashboard, onSelectEvent }: { dashboard: DashboardData; onSelectEvent: (eventId: number) => void }) {
  const snapshotCount = dashboard.providers.reduce((sum, provider) => sum + provider.snapshot_count, 0)
  const latestOdds = dashboard.events
    .map((event) => event.latest_odds_at)
    .filter((value): value is string => value !== null)
    .sort()
    .at(-1)
  const latestEvaluation = dashboard.evaluations[0]

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

export function BacktestResearch({ dashboard }: { dashboard: DashboardData }) {
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
    } catch (caught) { setRunError(caught instanceof Error ? caught.message : 'Unable to run signal backtest') } finally { setSubmitting(false) }
  }
  return (
    <div className="space-y-10">
      <section>
        <SectionHeading eyebrow="Timestamped signal replay" title="Settled strategy backtests" />
        <form className="mb-6 border-y border-zinc-200 bg-white p-5" onSubmit={(event) => void submitBacktest(event)}><div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5"><label><span className="mb-1.5 block text-xs font-semibold uppercase text-zinc-500">Model version</span><select aria-label="Backtest model" className="h-10 w-full border border-zinc-300 bg-white px-3 text-sm" required value={modelId} onChange={(event) => setModelId(event.target.value)}><option disabled value="">Select model</option>{dashboard.models.map((model) => <option key={model.id} value={model.id}>{model.version}</option>)}</select></label><label><span className="mb-1.5 block text-xs font-semibold uppercase text-zinc-500">Evaluation start</span><input aria-label="Evaluation start" className="h-10 w-full border border-zinc-300 px-3 text-sm" required type="datetime-local" value={evaluationStart} onChange={(event) => setEvaluationStart(event.target.value)} /></label><label><span className="mb-1.5 block text-xs font-semibold uppercase text-zinc-500">Evaluation end</span><input aria-label="Evaluation end" className="h-10 w-full border border-zinc-300 px-3 text-sm" required type="datetime-local" value={evaluationEnd} onChange={(event) => setEvaluationEnd(event.target.value)} /></label><fieldset><legend className="mb-1.5 text-xs font-semibold uppercase text-zinc-500">Stored classifications</legend><div className="flex h-10 items-center gap-3">{['VALUE', 'WATCH', 'PASS'].map((item) => <label key={item} className="flex items-center gap-1 text-xs font-semibold"><input checked={signalTypes.includes(item)} onChange={() => toggleSignalType(item)} type="checkbox" />{item}</label>)}</div></fieldset><label><span className="mb-1.5 block text-xs font-semibold uppercase text-zinc-500">Admin key (memory only)</span><input aria-label="Backtest admin key" autoComplete="off" className="h-10 w-full border border-zinc-300 px-3 text-sm" type="password" value={adminKey} onChange={(event) => setAdminKey(event.target.value)} /></label></div><div className="mt-4 flex items-center gap-3"><button className="rounded-[5px] bg-zinc-900 px-4 py-2 text-sm font-bold text-white disabled:opacity-50" disabled={submitting || !modelId || !evaluationStart || !evaluationEnd || !signalTypes.length} type="submit">{submitting ? 'Running replay…' : 'Run signal backtest'}</button><p className="text-xs text-zinc-500">Only predictions, prices, and signals timestamped before kickoff are eligible.</p></div>{runError ? <div className="mt-4 border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-900" role="alert">{runError}</div> : null}</form>
        {runs.length ? <div className="space-y-4">{runs.map((run) => <BacktestRunCard key={run.id} run={run} />)}</div> : <EmptyState title="No settled signal backtests" detail="Stored calibration runs remain below. Strategy returns require timestamp-valid signals and final results known by the evaluation cutoff." />}
      </section>
      <section>
        <EvaluationPerformance evaluations={dashboard.evaluations} />
      </section>
    </div>
  )
}

function BacktestRunCard({ run }: { run: DashboardData['backtests'][number] }) {
  return <article className="border border-zinc-200 bg-white"><div className="grid gap-4 p-5 md:grid-cols-[1fr_repeat(4,110px)] md:items-center"><div><p className="font-bold">#{run.id} / {run.model_version}</p><p className="mt-1 text-xs text-zinc-500">{formatDateTime(run.evaluation_start)} to {formatDateTime(run.evaluation_end)} · {run.is_demo ? 'DEMO ONLY' : 'EXTERNAL HISTORY'}</p><p className="mt-1 font-mono text-xs text-zinc-400">{run.fingerprint}</p></div><BacktestMetric label="Bets" value={String(metricValue(run.metrics, 'bet_count') ?? 0)} /><BacktestMetric label="Profit" value={formatScore(metricValue(run.metrics, 'net_profit_units'))} /><BacktestMetric label="ROI" value={formatSignedPercent(metricValue(run.metrics, 'roi') ?? 0)} /><BacktestMetric label="Drawdown" value={formatScore(metricValue(run.metrics, 'maximum_drawdown_units'))} /></div><div className="border-t border-zinc-200 bg-zinc-50 px-5 py-3"><span className="rounded-[4px] border border-amber-200 bg-amber-50 px-2 py-1 text-xs font-bold text-amber-800">{humanizeCode(run.evaluation_status)}</span><span className="ml-2 text-xs text-zinc-500">Created {formatDateTime(run.created_at)}</span></div>{run.observations.length ? <details className="border-t border-zinc-200"><summary className="cursor-pointer px-5 py-3 text-sm font-bold">Inspect {run.observations.length} settled observations</summary><div className="overflow-x-auto"><table className="w-full min-w-[900px] text-left text-xs"><thead className="bg-zinc-50 uppercase text-zinc-500"><tr><th className="px-4 py-3">Event / selection</th><th className="px-4 py-3">Prediction</th><th className="px-4 py-3">Price snapshot</th><th className="px-4 py-3 text-right">Odds</th><th className="px-4 py-3 text-right">Model / lower</th><th className="px-4 py-3">Settlement</th><th className="px-4 py-3 text-right">Profit</th></tr></thead><tbody>{run.observations.map((item) => <tr key={item.id} className="border-t border-zinc-100"><td className="px-4 py-3">Event #{item.event_id} · {humanizeCode(item.selection_code)}</td><td className="px-4 py-3">#{item.prediction_id}<br />{formatDateTime(item.predicted_at)}</td><td className="px-4 py-3">#{item.odds_snapshot_id}</td><td className="px-4 py-3 text-right font-mono">{item.decimal_odds.toFixed(2)}</td><td className="px-4 py-3 text-right font-mono">{(item.model_probability * 100).toFixed(1)}% / {(item.lower_probability * 100).toFixed(1)}%</td><td className="px-4 py-3">{humanizeCode(item.settlement)}<br />{formatDateTime(item.settled_at)}</td><td className="px-4 py-3 text-right font-mono">{item.profit_units >= 0 ? '+' : ''}{item.profit_units.toFixed(2)}</td></tr>)}</tbody></table></div></details> : <p className="border-t border-zinc-200 px-5 py-3 text-xs text-zinc-500">No eligible settled observations were included in this run.</p>}</article>
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

export function ArbitrageResearch({ dashboard }: { dashboard: DashboardData }) {
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
    } catch (caught) {
      setCalculationError(caught instanceof Error ? caught.message : 'Unable to calculate arbitrage')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-7">
      <SectionHeading eyebrow="Tax and constraint aware" title="Stored arbitrage calculations" />
      <ArbitrageSettings />
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

function Methodology() {
  const methods = [
    ['Market probability', 'Decimal prices are converted to raw implied probabilities. Complete markets are de-vigged with proportional and power methods; overlapping outcomes are never treated as independent.'],
    ['Model probability', 'Independent football models must use only evidence available before kickoff, preserve model versions, and report uncertainty rather than copying bookmaker probabilities.'],
    ['Signals', 'Model edge, line-shopping improvement, and bookmaker margin remain separate. Stale data, weak calibration, missing inputs, or uncertainty wider than the edge block a strong signal.'],
    ['Historical evaluation', 'Training and evaluation use chronological cutoffs and walk-forward tests. Final lineups, corrected results, and closing prices cannot leak into earlier predictions.'],
    ['Arbitrage', 'Only mutually exclusive and exhaustive outcomes with identical settlement rules can be combined. Taxes, fees, stake limits, rounding, void risk, and price movement must be included.'],
  ]
  return (
    <div className="max-w-5xl">
      <SectionHeading eyebrow="Statistical integrity" title="Research methodology" />
      <div className="border-y border-zinc-200 bg-white">
        {methods.map(([title, detail]) => (
          <div key={title} className="grid gap-2 border-b border-zinc-100 px-5 py-5 last:border-0 md:grid-cols-[190px_1fr]">
            <h3 className="font-semibold">{title}</h3><p className="text-sm leading-6 text-zinc-600">{detail}</p>
          </div>
        ))}
      </div>
      <div className="mt-5 flex gap-3 border border-rose-200 bg-rose-50 p-4 text-sm leading-6 text-rose-950">
        <AlertTriangle aria-hidden="true" className="mt-0.5 shrink-0" size={19} />
        <p>No prediction guarantees profit. Odds and statistical relationships change, historical performance does not ensure future performance, and this project is not affiliated with any bookmaker.</p>
      </div>
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
  return <div className="grid min-h-[420px] place-items-center"><div className="text-center"><RefreshCw aria-hidden="true" className="mx-auto animate-spin text-emerald-700" size={24} /><p className="mt-3 text-sm text-zinc-500">Loading market data</p></div></div>
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
  return <div className="m-4 border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-900"><strong>Unable to load prices.</strong> {message}</div>
}

export default App
