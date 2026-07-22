import { useMemo, useState } from 'react'
import { AlertTriangle, Filter, TrendingUp } from 'lucide-react'

import { formatDateTime, humanizeCode } from '../lib/format'
import type { DashboardData, ValueSignal } from '../types'

type ValueSort = 'LOWER_EV' | 'EDGE' | 'CONFIDENCE' | 'FRESHNESS'

export function ValueOpportunities({ dashboard, onOpenEvent }: { dashboard: DashboardData; onOpenEvent: (eventId: number) => void }) {
  const [competition, setCompetition] = useState('ALL')
  const [market, setMarket] = useState('ALL')
  const [minimumLowerEv, setMinimumLowerEv] = useState('0')
  const [minimumConfidence, setMinimumConfidence] = useState('0')
  const [sort, setSort] = useState<ValueSort>('LOWER_EV')
  const events = useMemo(() => new Map(dashboard.events.map((event) => [event.id, event])), [dashboard.events])
  const competitions = unique(dashboard.signals.map((signal) => events.get(signal.event_id)?.competition))
  const markets = unique(dashboard.signals.map((signal) => signal.market_type))
  const filtered = useMemo(() => dashboard.signals
    .filter((signal) => (competition === 'ALL' || events.get(signal.event_id)?.competition === competition)
      && (market === 'ALL' || signal.market_type === market)
      && signal.lower_expected_value >= numberOr(minimumLowerEv, 0) / 100
      && signal.confidence >= numberOr(minimumConfidence, 0) / 100)
    .sort((left, right) => sortValue(right, sort) - sortValue(left, sort) || right.expected_value - left.expected_value),
  [competition, dashboard.signals, events, market, minimumConfidence, minimumLowerEv, sort])

  if (!dashboard.signals.length) {
    return <div className="space-y-5"><EmptyValue title="No stored value opportunities" detail="VALUE recommendations appear only after a non-demo model passes chronological calibration and a prediction joins complete compatible pre-kickoff odds." /><div className="border-l-4 border-amber-400 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-950">Demo evaluations, stale prices, weak calibration, or uncertainty wider than the estimated edge cannot unlock this screen.</div></div>
  }

  const averageLowerEv = filtered.length ? filtered.reduce((sum, signal) => sum + signal.lower_expected_value, 0) / filtered.length : null
  const freshest = filtered.length ? Math.min(...filtered.map((signal) => signal.odds_age_minutes)) : null

  return <div className="space-y-7">
    <div><p className="text-xs font-bold uppercase text-emerald-700">Calibrated model versus market</p><h2 className="mt-1 text-lg font-bold">Value opportunity research</h2><p className="mt-1 max-w-2xl text-sm leading-6 text-zinc-500">Inspect immutable recommendations using the conservative probability bound, price freshness, market consensus, and exact evaluation provenance.</p></div>
    <section className="grid grid-cols-2 border border-zinc-200 bg-white md:grid-cols-4"><ValueMetric label="Recommendations" value={filtered.length.toString()} /><ValueMetric label="Average lower EV" value={averageLowerEv === null ? '—' : signedPercent(averageLowerEv)} /><ValueMetric label="Freshest price" value={freshest === null ? '—' : `${freshest.toFixed(0)}m`} /><ValueMetric label="Policy" value="VALUE only" /></section>
    <section className="border-y border-zinc-200 bg-white p-4"><div className="mb-4 flex items-center gap-2 text-sm font-bold"><Filter aria-hidden="true" size={16} />Research controls</div><div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
      <Select label="Competition" value={competition} onChange={setCompetition} options={[['ALL', 'All competitions'], ...competitions.map((value) => [value, value])]} />
      <Select label="Market" value={market} onChange={setMarket} options={[['ALL', 'All markets'], ...markets.map((value) => [value, humanizeCode(value)])]} />
      <NumberFilter label="Minimum lower EV (%)" value={minimumLowerEv} onChange={setMinimumLowerEv} />
      <NumberFilter label="Minimum confidence (%)" value={minimumConfidence} onChange={setMinimumConfidence} max="100" />
      <Select label="Rank by" value={sort} onChange={(value) => setSort(value as ValueSort)} options={[["LOWER_EV", "Conservative EV"], ["EDGE", "Probability edge"], ["CONFIDENCE", "Confidence"], ["FRESHNESS", "Freshest price"]]} />
    </div></section>
    {filtered.length ? <div className="space-y-4">{filtered.map((signal, index) => <ValueCard key={signal.id} event={events.get(signal.event_id)} rank={index + 1} signal={signal} onOpenEvent={onOpenEvent} />)}</div> : <EmptyValue title="No opportunities match these filters" detail="Reduce the conservative EV or confidence threshold, or choose a broader competition and market." />}
    <div className="border-l-4 border-sky-500 bg-sky-50 px-4 py-3 text-sm leading-6 text-sky-950">Model edge, line-shopping improvement, and bookmaker margin remain separate. Every recommendation is conditional on its stored price and cutoff.</div>
  </div>
}

function ValueCard({ event, rank, signal, onOpenEvent }: { event: DashboardData['events'][number] | undefined; rank: number; signal: ValueSignal; onOpenEvent: (eventId: number) => void }) {
  return <article className="border border-zinc-200 bg-white"><div className="grid gap-4 p-5 lg:grid-cols-[minmax(260px,1fr)_repeat(5,minmax(90px,auto))] lg:items-center">
    <div><p className="text-xs font-bold uppercase text-emerald-700">Rank #{rank} · {humanizeCode(signal.market_type)}</p><h3 className="mt-1 font-bold">{event ? `${event.home_team} vs ${event.away_team}` : `Event ${signal.event_id}`}</h3><p className="mt-1 text-sm text-zinc-600">{signal.selection_name} · <strong>{signal.offered_odds.toFixed(2)}</strong> at {signal.bookmaker}</p>{event ? <p className="mt-1 text-xs text-zinc-500">{event.competition} · {formatDateTime(event.kickoff_at)}</p> : null}</div>
    <CompactMetric label="Model" value={percent(signal.model_probability)} /><CompactMetric label="Market" value={percent(signal.market_fair_probability)} /><CompactMetric label="Edge" value={signedPercent(signal.probability_edge)} /><CompactMetric label="EV" value={signedPercent(signal.expected_value)} /><CompactMetric label="Lower EV" value={signedPercent(signal.lower_expected_value)} tone />
  </div><div className="grid gap-3 border-t border-zinc-200 bg-zinc-50 px-5 py-4 text-xs md:grid-cols-[1fr_auto] md:items-start"><div><p className="font-semibold text-zinc-700">{signal.reasons[0] ?? 'Stored calibrated recommendation.'}</p>{signal.risks[0] ? <p className="mt-1 flex gap-1.5 text-amber-800"><AlertTriangle aria-hidden="true" size={14} />{signal.risks[0]}</p> : null}<details className="mt-2 text-zinc-500"><summary className="cursor-pointer font-semibold">Full evidence</summary><p className="mt-1">Confidence {percent(signal.confidence)} · lower probability {percent(signal.lower_probability)} · calibration error {percent(signal.calibration_error)}</p><p>{signal.bookmaker_count} books · {signal.odds_age_minutes.toFixed(0)}m old · move {signedPercent(signal.odds_move_ratio)} · eval #{signal.evaluation_run_id}</p><p>Prediction #{signal.prediction_id} · snapshot #{signal.odds_snapshot_id} · generated {formatDateTime(signal.generated_at)}</p></details></div><button className="rounded-[5px] border border-zinc-300 bg-white px-3 py-2 font-bold hover:bg-zinc-100" onClick={() => onOpenEvent(signal.event_id)} type="button">Open event</button></div>
  </article>
}

function Select({ label, value, options, onChange }: { label: string; value: string; options: string[][]; onChange: (value: string) => void }) { return <label><span className="mb-1.5 block text-xs font-semibold uppercase text-zinc-500">{label}</span><select aria-label={label} className="h-10 w-full border border-zinc-300 bg-white px-3 text-sm" value={value} onChange={(event) => onChange(event.target.value)}>{options.map(([key, text]) => <option key={key} value={key}>{text}</option>)}</select></label> }
function NumberFilter({ label, value, onChange, max }: { label: string; value: string; onChange: (value: string) => void; max?: string }) { return <label><span className="mb-1.5 block text-xs font-semibold uppercase text-zinc-500">{label}</span><input aria-label={label} className="h-10 w-full border border-zinc-300 px-3 text-sm" max={max} step="0.5" type="number" value={value} onChange={(event) => onChange(event.target.value)} /></label> }
function ValueMetric({ label, value }: { label: string; value: string }) { return <div className="border-r border-b border-zinc-200 p-4"><p className="text-xs font-semibold uppercase text-zinc-500">{label}</p><p className="mt-2 text-xl font-bold">{value}</p></div> }
function CompactMetric({ label, value, tone = false }: { label: string; value: string; tone?: boolean }) { return <div><p className="text-xs font-semibold uppercase text-zinc-500">{label}</p><p className={`mt-1 font-mono font-bold ${tone ? 'text-emerald-700' : ''}`}>{value}</p></div> }
function EmptyValue({ title, detail }: { title: string; detail: string }) { return <div className="border-y border-zinc-200 bg-white px-6 py-12 text-center"><TrendingUp aria-hidden="true" className="mx-auto text-zinc-400" size={28} /><h2 className="mt-3 font-bold">{title}</h2><p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-zinc-500">{detail}</p></div> }
function unique(values: Array<string | undefined>): string[] { return Array.from(new Set(values.filter((value): value is string => Boolean(value)))).sort() }
function numberOr(value: string, fallback: number): number { const parsed = Number(value); return Number.isFinite(parsed) ? parsed : fallback }
function sortValue(signal: ValueSignal, sort: ValueSort): number { if (sort === 'EDGE') return signal.probability_edge; if (sort === 'CONFIDENCE') return signal.confidence; if (sort === 'FRESHNESS') return -signal.odds_age_minutes; return signal.lower_expected_value }
function percent(value: number): string { return `${(value * 100).toFixed(1)}%` }
function signedPercent(value: number): string { return `${value >= 0 ? '+' : ''}${(value * 100).toFixed(1)}%` }
