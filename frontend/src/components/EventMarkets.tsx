import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, CalendarDays, GitCompareArrows, RefreshCw } from 'lucide-react'

import { loadPredictions } from '../api/client'
import { formatDateTime, humanizeCode } from '../lib/format'
import type { DashboardData, EventSummary, MarketComparison, ModelOutput } from '../types'

interface EventMarketsProps {
  dashboard: DashboardData
  events: EventSummary[]
  selectedEventId: number | null
  markets: MarketComparison[]
  loading: boolean
  error: string | null
  onSelectEvent: (eventId: number) => void
  onOpenComparison: () => void
}

export function EventMarkets({ dashboard, events, selectedEventId, markets, loading, error, onSelectEvent, onOpenComparison }: EventMarketsProps) {
  const event = events.find((candidate) => candidate.id === selectedEventId)
  const [predictions, setPredictions] = useState<ModelOutput[]>([])
  const [predictionLoading, setPredictionLoading] = useState(false)
  const [predictionError, setPredictionError] = useState<string | null>(null)

  useEffect(() => {
    if (selectedEventId === null) return
    let active = true
    void Promise.resolve().then(() => {
      if (active) { setPredictionLoading(true); setPredictionError(null) }
      return loadPredictions(selectedEventId)
    }).then((result) => { if (active) setPredictions(result) }).catch((caught: unknown) => {
      if (active) { setPredictions([]); setPredictionError(caught instanceof Error ? caught.message : 'Unable to load prediction evidence') }
    }).finally(() => { if (active) setPredictionLoading(false) })
    return () => { active = false }
  }, [selectedEventId])

  const signals = dashboard.signals.filter((signal) => signal.event_id === selectedEventId)
  const bookmakerCount = useMemo(() => new Set(markets.flatMap((market) => market.snapshots.map((snapshot) => snapshot.bookmaker_id))).size, [markets])
  const latestPrediction = predictions[0]

  return <div className="space-y-7">
    <label className="block max-w-xl"><span className="mb-1.5 block text-xs font-semibold uppercase text-zinc-500">Event</span><select aria-label="Event" className="h-10 w-full rounded-[5px] border border-zinc-300 bg-white px-3 text-sm font-medium" value={selectedEventId ?? ''} onChange={(item) => onSelectEvent(Number(item.target.value))}>{events.map((item) => <option key={item.id} value={item.id}>{item.home_team} vs {item.away_team} — {item.competition}</option>)}</select></label>
    {!event ? <EventEmpty title="No event selected" detail="Import an event and coherent odds snapshot to inspect its research record." /> : <>
      <section className="border border-zinc-200 bg-white"><div className="flex flex-wrap items-start justify-between gap-4 p-5"><div><p className="text-xs font-bold uppercase text-emerald-700">{event.competition} · {event.season}</p><h2 className="mt-1 text-xl font-bold">{event.home_team} vs {event.away_team}</h2><p className="mt-1 text-sm text-zinc-500">{formatDateTime(event.kickoff_at)} · {event.country}</p></div><div className="flex gap-2"><span className="rounded-[4px] border border-zinc-300 px-2 py-1 text-xs font-bold">{event.is_demo ? 'DEMO EVENT' : event.status.toUpperCase()}</span><button className="flex items-center gap-2 rounded-[5px] bg-zinc-900 px-3 py-2 text-xs font-bold text-white" onClick={onOpenComparison} type="button"><GitCompareArrows aria-hidden="true" size={15} />Open comparison</button></div></div>
        <div className="grid grid-cols-2 border-t border-zinc-200 md:grid-cols-4"><EventMetric label="Markets" value={markets.length.toString()} /><EventMetric label="Bookmakers" value={bookmakerCount.toString()} /><EventMetric label="Predictions" value={predictions.length.toString()} /><EventMetric label="Qualified value" value={signals.length.toString()} /></div>
      </section>

      <section className="grid gap-6 xl:grid-cols-2"><div><Heading eyebrow="Independent model" title="Latest prediction evidence" />{predictionLoading ? <EventLoading text="Loading predictions" /> : predictionError ? <EventWarning text={predictionError} /> : latestPrediction ? <div className="border-y border-zinc-200 bg-white p-5"><div className="grid grid-cols-2 gap-4 sm:grid-cols-4"><SmallMetric label="Home xG" value={latestPrediction.home_lambda.toFixed(2)} /><SmallMetric label="Away xG" value={latestPrediction.away_lambda.toFixed(2)} /><SmallMetric label="Sample" value={latestPrediction.sample_size.toString()} /><SmallMetric label="Evidence" value={humanizeCode(latestPrediction.evidence_class)} /></div><div className="mt-4 border-t border-zinc-100 pt-4 text-xs leading-5 text-zinc-500"><p>Model {latestPrediction.model_version} · output #{latestPrediction.id}</p><p>Predicted {formatDateTime(latestPrediction.predicted_at)} · inputs through {formatDateTime(latestPrediction.inputs_as_of)}</p></div></div> : <EventEmpty title="No pre-kickoff prediction" detail="Train a versioned model and persist a prediction before kickoff to populate this evidence layer." />}</div>
      <div><Heading eyebrow="Gated policy" title="Qualified value signals" />{signals.length ? <div className="border-y border-zinc-200 bg-white">{signals.map((signal) => <div key={signal.id} className="grid grid-cols-[1fr_auto] gap-3 border-b border-zinc-100 p-4 last:border-0"><div><p className="font-semibold">{signal.selection_name} · {signal.bookmaker} {signal.offered_odds.toFixed(2)}</p><p className="mt-1 text-xs text-zinc-500">Model {(signal.model_probability * 100).toFixed(1)}% · market {(signal.market_fair_probability * 100).toFixed(1)}% · lower EV {signedPercent(signal.lower_expected_value)}</p></div><span className="self-start rounded-[4px] border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-bold text-emerald-800">{signal.signal_type}</span></div>)}</div> : <EventEmpty title="No qualified value" detail="Market prices remain visible, but no independently calibrated VALUE recommendation exists for this event." />}</div></section>

      <section><Heading eyebrow="Coherent snapshots" title="Market and bookmaker coverage" />{loading ? <EventLoading text="Loading event markets" /> : error ? <EventWarning text={error} /> : markets.length ? <div className="space-y-5">{markets.map((market) => <MarketPanel key={market.market_id} market={market} />)}</div> : <EventEmpty title="No complete markets" detail="No complete compatible bookmaker snapshots are available for this event." />}</section>
    </>}
  </div>
}

function MarketPanel({ market }: { market: MarketComparison }) {
  return <article className="border border-zinc-200 bg-white"><div className="flex flex-wrap items-start justify-between gap-3 border-b border-zinc-200 p-5"><div><p className="text-xs font-bold uppercase text-emerald-700">{humanizeCode(market.period)} · {market.currency}</p><h3 className="mt-1 font-bold">{humanizeCode(market.market_type)}{market.line === null ? '' : ` · ${market.line}`}</h3><p className="mt-1 text-xs text-zinc-500">{market.settlement_rule_key}</p></div><span className="text-xs font-semibold text-zinc-500">{market.snapshots.length} bookmaker snapshots</span></div><div className="overflow-x-auto"><table className="w-full min-w-[760px] text-left text-sm"><thead className="bg-zinc-50 text-xs uppercase text-zinc-500"><tr><th className="px-4 py-3">Bookmaker</th>{market.best_prices.map((price) => <th key={price.selection_code} className="px-4 py-3 text-right">{price.selection_name}</th>)}<th className="px-4 py-3 text-right">Margin</th><th className="px-4 py-3">Observed</th></tr></thead><tbody>{market.snapshots.map((snapshot) => <tr key={snapshot.snapshot_id} className="border-t border-zinc-100"><td className="px-4 py-3"><p className="font-semibold">{snapshot.bookmaker}</p><p className="text-xs text-zinc-500">{snapshot.is_demo ? 'DEMO' : snapshot.provider}</p></td>{market.best_prices.map((best) => { const price = snapshot.prices.find((item) => item.selection_code === best.selection_code); return <td key={best.selection_code} className="px-4 py-3 text-right font-mono">{price ? price.decimal_odds.toFixed(2) : '—'}{best.bookmaker === snapshot.bookmaker ? <span className="ml-1 text-xs font-bold text-emerald-700">BEST</span> : null}</td> })}<td className="px-4 py-3 text-right font-mono">{(snapshot.bookmaker_margin * 100).toFixed(1)}%</td><td className="px-4 py-3 text-xs"><p>{formatDateTime(snapshot.observed_at)}</p><p className={snapshot.is_stale ? 'text-amber-700' : 'text-emerald-700'}>{snapshot.is_stale ? 'STALE' : 'FRESH'} · {snapshot.freshness_seconds}s</p></td></tr>)}</tbody></table></div></article>
}

function Heading({ eyebrow, title }: { eyebrow: string; title: string }) { return <div className="mb-3"><p className="text-xs font-bold uppercase text-emerald-700">{eyebrow}</p><h2 className="mt-1 text-lg font-bold">{title}</h2></div> }
function EventMetric({ label, value }: { label: string; value: string }) { return <div className="border-r border-zinc-200 p-4"><p className="text-xs font-semibold uppercase text-zinc-500">{label}</p><p className="mt-2 text-2xl font-bold">{value}</p></div> }
function SmallMetric({ label, value }: { label: string; value: string }) { return <div><p className="text-xs font-semibold uppercase text-zinc-500">{label}</p><p className="mt-1 font-mono font-bold">{value}</p></div> }
function EventEmpty({ title, detail }: { title: string; detail: string }) { return <div className="border-y border-zinc-200 bg-white px-5 py-9 text-center"><CalendarDays aria-hidden="true" className="mx-auto text-zinc-400" size={24} /><h3 className="mt-2 font-bold">{title}</h3><p className="mx-auto mt-1 max-w-md text-sm leading-6 text-zinc-500">{detail}</p></div> }
function EventLoading({ text }: { text: string }) { return <div className="flex items-center justify-center gap-2 border-y border-zinc-200 bg-white px-5 py-10 text-sm text-zinc-500"><RefreshCw aria-hidden="true" className="animate-spin" size={16} />{text}</div> }
function EventWarning({ text }: { text: string }) { return <div className="flex gap-2 border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900"><AlertTriangle aria-hidden="true" size={18} />{text}</div> }
function signedPercent(value: number): string { return `${value >= 0 ? '+' : ''}${(value * 100).toFixed(1)}%` }
